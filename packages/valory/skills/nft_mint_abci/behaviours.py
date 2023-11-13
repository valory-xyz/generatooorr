# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""This package contains round behaviours of NftMintAbciApp."""

import json
from abc import ABC
from typing import Dict, Generator, List, Optional, Set, Type, cast

from aea.helpers.cid import to_v1
from multibase import multibase
from multicodec import multicodec

from packages.valory.contracts.blockchain_shorts.contract import (
    BlockchainShortsContract,
)
from packages.valory.contracts.gnosis_safe.contract import SafeOperation, GnosisSafeContract
from packages.valory.contracts.multisend.contract import (
    MultiSendContract,
    MultiSendOperation,
)
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.base import AbstractRound, get_name
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.abstract_round_abci.io_.store import SupportedFiletype
from packages.valory.skills.nft_mint_abci.models import Params
from packages.valory.skills.nft_mint_abci.payloads import (
    NftMintPayload,
    VerifyMintPayload,
)
from packages.valory.skills.nft_mint_abci.rounds import (
    NftMintAbciApp,
    NftMintRound,
    SynchronizedData,
    VerifyMintRound,
)
from packages.valory.skills.transaction_settlement_abci.payload_tools import (
    hash_payload_to_hex,
)


SAFE_TX_GAS = 0
ETHER_VALUE = 0


class NftMintAbciBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the common apps' skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)

    @staticmethod
    def to_multihash(hash_string: str) -> str:
        """To multihash string."""
        # Decode the Base32 CID to bytes
        cid_bytes = multibase.decode(hash_string)
        # Remove the multicodec prefix (0x01) from the bytes
        multihash_bytes = multicodec.remove_prefix(cid_bytes)
        # Convert the multihash bytes to a hexadecimal string
        hex_multihash = multihash_bytes.hex()
        return hex_multihash[6:]


class MintNftBehaviour(NftMintAbciBaseBehaviour):
    """MintNftBehaviour"""

    matching_round: Type[AbstractRound] = NftMintRound

    def _prepare_mint_mstx(self, owner: str, metadata: bytes) -> Generator:
        """Prepare a multisend tx for `create`"""
        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,
            contract_address=self.params.blockchain_shorts_contract,
            contract_id=str(BlockchainShortsContract.contract_id),
            contract_callable="get_mint_data",
            owner=owner,
            ipfs_hash=metadata,
        )
        if response.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.warning(
                f"get_ask_question_tx_data unsuccessful!: {response}"
            )
            return None
        return {
            "to": self.params.blockchain_shorts_contract,
            "data": response.state.body["data"],
            "value": ETHER_VALUE,
        }

    def _publish_metadata(self, image: str, video: str) -> Generator:
        """Publish metadata to IPFS."""
        metadata = {
            "name": "Blockchain Short",
            "description": "NFT Mint for blockchain shorts.",
            "image": f"ipfs://{image}",
            "attributes": [{"trait_type": "version", "value": "0.1.0"}],
            "animation_url": f"ipfs://{video}",
        }
        ipfs_hash = yield from self.send_to_ipfs(
            filename="./metadata.json",
            obj=metadata,
            filetype=SupportedFiletype.JSON,
        )
        return ipfs_hash

    def async_act(self) -> Generator:
        """Get a list of the new tokens."""
        mech_response = self.synchronized_data.mech_responses[0]
        self.context.logger.info(f"mech_response: {mech_response}")
        data = json.loads(mech_response.result)
        owner = self.synchronized_data.requests[mech_response.nonce]
        ipfs_hash = yield from self._publish_metadata(
            image=data["image"],
            video=data["video"],
        )
        metadata_str = self.to_multihash(to_v1(ipfs_hash))
        metadata = bytes.fromhex(metadata_str)
        mint_tx = yield from self._prepare_mint_mstx(
            owner=owner,
            metadata=metadata,
        )
        if mint_tx is None:
            return
        tx_hash = yield from self._to_multisend(
            transactions=[
                mint_tx,
            ]
        )
        if tx_hash is None:
            return
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            payload = NftMintPayload(
                sender=self.context.agent_address,
                content=json.dumps(
                    dict(
                        tx_hash=tx_hash,
                        metadata_hash=ipfs_hash,
                    ),
                    sort_keys=True,
                ),
            )
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()
        self.set_done()

    def _to_multisend(
        self, transactions: List[Dict]
    ) -> Generator[None, None, Optional[str]]:
        """Transform payload to MultiSend."""
        multi_send_txs = []
        for transaction in transactions:
            transaction = {
                "operation": transaction.get("operation", MultiSendOperation.CALL),
                "to": transaction["to"],
                "value": transaction["value"],
                "data": transaction.get("data", b""),
            }
            multi_send_txs.append(transaction)

        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.params.multisend_address,
            contract_id=str(MultiSendContract.contract_id),
            contract_callable="get_tx_data",
            multi_send_txs=multi_send_txs,
        )
        if response.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(
                f"Couldn't compile the multisend tx. "
                f"Expected performative {ContractApiMessage.Performative.RAW_TRANSACTION.value}, "  # type: ignore
                f"received {response.performative.value}."
            )
            return None

        # strip "0x" from the response
        multisend_data_str = cast(str, response.raw_transaction.body["data"])[2:]
        tx_data = bytes.fromhex(multisend_data_str)
        tx_hash = yield from self._get_safe_tx_hash(
            tx_data,
        )
        if tx_hash is None:
            return None

        payload_data = hash_payload_to_hex(
            safe_tx_hash=tx_hash,
            ether_value=ETHER_VALUE,
            safe_tx_gas=SAFE_TX_GAS,
            operation=SafeOperation.DELEGATE_CALL.value,
            to_address=self.params.multisend_address,
            data=tx_data,
        )
        return payload_data

    def _get_safe_tx_hash(self, data: bytes) -> Generator[None, None, Optional[str]]:
        """
        Prepares and returns the safe tx hash.

        This hash will be signed later by the agents, and submitted to the safe contract.
        Note that this is the transaction that the safe will execute, with the provided data.

        :param data: the safe tx data.
        :return: the tx hash
        """
        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=self.synchronized_data.safe_contract_address,
            contract_id=str(GnosisSafeContract.contract_id),
            contract_callable="get_raw_safe_transaction_hash",
            to_address=self.params.multisend_address,  # we send the tx to the multisend address
            value=ETHER_VALUE,
            data=data,
            safe_tx_gas=SAFE_TX_GAS,
            operation=SafeOperation.DELEGATE_CALL.value,
        )

        if response.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                f"Couldn't get safe hash. "
                f"Expected response performative {ContractApiMessage.Performative.STATE.value}, "  # type: ignore
                f"received {response.performative.value}."
            )
            return None

        # strip "0x" from the response hash
        tx_hash = cast(str, response.state.body["tx_hash"])[2:]
        return tx_hash


class VerifyMintBehaviour(NftMintAbciBaseBehaviour):
    """VerifyMintBehaviour"""

    matching_round: Type[AbstractRound] = VerifyMintRound

    def _get_token_id(
        self,
        tx_hash: str,
        metadata_hash: str,
    ) -> Generator[None, None, Optional[int]]:
        """Get token ID"""
        # TODO: FIX
        # metadata_str = self.to_multihash(to_v1(metadata_hash))
        # metadata = bytes.fromhex(metadata_str)
        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,
            contract_address=self.params.blockchain_shorts_contract,
            contract_id=str(BlockchainShortsContract.contract_id),
            contract_callable="get_token_id_from_hash",
            tx_hash=tx_hash,
            metadata_hash=metadata_hash,
        )
        if response.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.warning(
                f"get_token_id_from_hash unsuccessful!: {response}"
            )
            return None
        return response.state.body["token_id"]

    def async_act(self) -> Generator:
        """Verify NFT mint."""
        token_id = yield from self._get_token_id(
            tx_hash=self.synchronized_data.final_tx_hash,
            metadata_hash=self.synchronized_data.metadata_hash,
        )
        if token_id is None:
            return
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            payload = VerifyMintPayload(
                sender=self.context.agent_address,
                token_id=token_id,
            )
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()


class NftMintAbciRoundBehaviour(AbstractRoundBehaviour):
    """NftMintAbciRoundBehaviour"""

    initial_behaviour_cls = MintNftBehaviour
    abci_app_cls = NftMintAbciApp
    behaviours: Set[Type[BaseBehaviour]] = [
        MintNftBehaviour,
        VerifyMintBehaviour,
    ]

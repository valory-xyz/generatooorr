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
from typing import Generator, Set, Type, cast, List, Dict, Optional

from packages.valory.contracts.gnosis_safe.contract import (
    SafeOperation,
)
from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.mech_interact_abci.states.base import (
    MechInteractionResponse,
)
from packages.valory.skills.nft_mint_abci.models import Params
from packages.valory.skills.nft_mint_abci.payloads import NftMintPayload
from packages.valory.skills.nft_mint_abci.rounds import (
    NftMintAbciApp,
    NftMintRound,
    SynchronizedData,
)
from packages.valory.contracts.blockchain_shorts.contract import (
    BlockchainShortsContract,
)
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.base import get_name
from packages.valory.skills.transaction_settlement_abci.payload_tools import (
    hash_payload_to_hex,
)
from packages.valory.contracts.multisend.contract import (
    MultiSendContract,
    MultiSendOperation,
)
from packages.valory.skills.abstract_round_abci.io_.store import SupportedFiletype

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


class MintNftBehaviour(NftMintAbciBaseBehaviour):
    """MintNftBehaviour"""

    matching_round: Type[AbstractRound] = NftMintRound

    def _prepare_mint_mstx(self, owner: str, ipfs_hash: str) -> Generator:
        """Prepare a multisend tx for `create`"""
        response = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,
            contract_address=self.params.conditional_tokens_contract,
            contract_id=str(BlockchainShortsContract.contract_id),
            contract_callable=get_name(BlockchainShortsContract.get_mint_data),
            owner=owner,
            ipfs_hash=ipfs_hash,
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
        data = json.loads(mech_response.data)
        owner = self.synchronized_data.requests[mech_response.nonce]
        ipfs_hash = yield from self._publish_metadata(
            image=data["image"],
            video=data["video"],
        )
        mint_tx = yield from self._prepare_mint_mstx(
            owner=owner,
            ipfs_hash=ipfs_hash,
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
            payload = NftMintPayload(sender=self.context.agent_address, content=tx_hash)
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
            self.params.multisend_address,
            tx_data,
            operation=SafeOperation.DELEGATE_CALL.value,
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


class VerifyMintBehaviour(NftMintAbciBaseBehaviour):
    """VerifyMintBehaviour"""
    

class NftMintAbciRoundBehaviour(AbstractRoundBehaviour):
    """NftMintAbciRoundBehaviour"""

    initial_behaviour_cls = MintNftBehaviour
    abci_app_cls = NftMintAbciApp
    behaviours: Set[Type[BaseBehaviour]] = [
        MintNftBehaviour,
    ]
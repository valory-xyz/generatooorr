# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2024 Valory AG
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

"""This module contains the base behaviour for the 'decision_maker_abci' skill."""

import dataclasses
import json
from abc import ABC
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Generator, List, Optional, cast

from aea.configurations.data_types import PublicId

from packages.valory.contracts.erc20.contract import ERC20TokenContract as ERC20
from packages.valory.contracts.gnosis_safe.contract import (
    GnosisSafeContract,
    SafeOperation,
)
from packages.valory.contracts.multisend.contract import MultiSendContract
from packages.valory.contracts.transfer_nft_condition.contract import (
    TransferNftCondition,
)
from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.base import BaseTxPayload
from packages.valory.skills.abstract_round_abci.behaviour_utils import TimeoutException, BaseBehaviour
from packages.valory.skills.subscription_abci.models import (
    Params,
    MultisendBatch,
    SharedState,
)
from packages.valory.skills.subscription_abci.rounds import SynchronizedData
from packages.valory.skills.subscription_abci.utils.nevermined import (
    no_did_prefixed,
    zero_x_transformer,
)
from packages.valory.skills.transaction_settlement_abci.payload_tools import (
    hash_payload_to_hex,
)
from packages.valory.skills.transaction_settlement_abci.rounds import TX_HASH_LENGTH

WaitableConditionType = Generator[None, None, bool]


# setting the safe gas to 0 means that all available gas will be used
# which is what we want in most cases
# more info here: https://safe-docs.dev.gnosisdev.com/safe/docs/contracts_tx_execution/
SAFE_GAS = 0
CID_PREFIX = "f01701220"
WXDAI = "0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d"
BET_AMOUNT_FIELD = "bet_amount"
SUPPORTED_STRATEGY_LOG_LEVELS = ("info", "warning", "error")
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


def remove_fraction_wei(amount: int, fraction: float) -> int:
    """Removes the given fraction from the given integer amount and returns the value as an integer."""
    if 0 <= fraction <= 1:
        keep_percentage = 1 - fraction
        return int(amount * keep_percentage)
    raise ValueError(f"The given fraction {fraction!r} is not in the range [0, 1].")


class BaseSubscriptionBehaviour(BaseBehaviour, ABC):
    """Base class for subscription behaviours."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize `BaseSubscriptionBehaviour`."""
        super().__init__(**kwargs)
        self.token_balance = 0
        self.wallet_balance = 0
        self.multisend_batches: List[MultisendBatch] = []
        self.multisend_data = b""
        self._safe_tx_hash = ""
        self.balance: int = 0

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, self.context.params)

    @property
    def subscription_params(self) -> Dict[str, Any]:
        """Get the subscription params."""
        return self.params.mech_to_subscription_params

    @property
    def did(self) -> str:
        """Get the did."""
        subscription_params = self.subscription_params
        return subscription_params["did"]

    @property
    def token_address(self) -> str:
        """Get the token address."""
        subscription_params = self.subscription_params
        return subscription_params["token_address"]

    @property
    def escrow_payment_condition_address(self) -> str:
        """Get the escrow payment address."""
        subscription_params = self.subscription_params
        return subscription_params["escrow_payment_condition_address"]

    @property
    def lock_payment_condition_address(self) -> str:
        """Get the lock payment address."""
        subscription_params = self.subscription_params
        return subscription_params["lock_payment_condition_address"]

    @property
    def transfer_nft_condition_address(self) -> str:
        """Get the transfer nft condition address."""
        subscription_params = self.subscription_params
        return subscription_params["transfer_nft_condition_address"]

    @property
    def order_address(self) -> str:
        """Get the order address."""
        subscription_params = self.subscription_params
        return subscription_params["order_address"]

    @property
    def purchase_amount(self) -> int:
        """Get the purchase amount."""
        subscription_params = self.subscription_params
        return int(subscription_params["nft_amount"])

    @property
    def price(self) -> int:
        """Get the price."""
        subscription_params = self.subscription_params
        return int(subscription_params["price"])

    @property
    def payment_token(self) -> str:
        """Get the payment token."""
        subscription_params = self.subscription_params
        return subscription_params["payment_token"]

    @property
    def is_xdai(self) -> bool:
        """
        Check if the payment token is xDAI.

        When the payment token for the subscription is xdai (the native token of the chain),
        nevermined sets the payment address to the zeroAddress.

        :return: True if the payment token is xDAI, False otherwise.
        """
        return self.payment_token == ZERO_ADDRESS

    @property
    def base_url(self) -> str:
        """Get the base url."""
        subscription_params = self.subscription_params
        return subscription_params["base_url"]

    def _resolve_did(self) -> Generator[None, None, Optional[Dict[str, Any]]]:
        """Resolve and parse the did."""
        did_url = f"{self.base_url}/{self.did}"
        response = yield from self.get_http_response(
            method="GET",
            url=did_url,
            headers={"accept": "application/json"},
        )
        if response.status_code != 200:
            self.context.logger.error(
                f"Could not retrieve data from did url {did_url}. "
                f"Received status code {response.status_code}."
            )
            return None
        try:
            data = json.loads(response.body)
        except (ValueError, TypeError) as e:
            self.context.logger.error(
                f"Could not parse response from nervermined api, "
                f"the following error was encountered {type(e).__name__}: {e}"
            )
            return None

        return data

    def _get_nft_balance(
        self, token: str, address: str, did: str
    ) -> Generator[None, None, bool]:
        """Prepare an approval tx."""
        result = yield from self.contract_interact(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=token,
            contract_public_id=TransferNftCondition.contract_id,
            contract_callable="balance_of",
            data_key="data",
            placeholder="balance",
            address=address,
            did=did,
        )
        return result

    def _has_positive_nft_balance(self) -> Generator[None, None, bool]:
        """Check if the agent has a non-zero balance of the NFT."""
        result = yield from self._get_nft_balance(
            self.token_address,
            self.synchronized_data.safe_contract_address,
            zero_x_transformer(no_did_prefixed(self.did)),
        )
        if not result:
            self.context.logger.warning("Failed to get balance")
            return False

        return self.balance > 0

    def check_balance(self) -> WaitableConditionType:
        """Check the safe's balance."""
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.payment_token,
            contract_id=str(ERC20.contract_id),
            contract_callable="check_balance",
            account=self.synchronized_data.safe_contract_address,
        )
        if response_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(
                f"Could not calculate the balance of the safe: {response_msg}"
            )
            return False

        token = response_msg.raw_transaction.body.get("token", None)
        wallet = response_msg.raw_transaction.body.get("wallet", None)
        if token is None or wallet is None:
            self.context.logger.error(
                f"Something went wrong while trying to get the balance of the safe: {response_msg}"
            )
            return False

        self.token_balance = int(token)
        self.wallet_balance = int(wallet)

        return True

    def _propagate_contract_messages(self, response_msg: ContractApiMessage) -> bool:
        """Propagate the contract's message to the logger, if exists.

        Contracts can only return one message at a time.

        :param response_msg: the response message from the contract method.
        :return: whether a message has been propagated.
        """
        for level in ("info", "warning", "error"):
            msg = response_msg.raw_transaction.body.get(level, None)
            if msg is not None:
                logger = getattr(self.context.logger, level)
                logger(msg)
                return True
        return False

    def contract_interact(
        self,
        performative: ContractApiMessage.Performative,
        contract_address: str,
        contract_public_id: PublicId,
        contract_callable: str,
        data_key: str,
        placeholder: str,
        **kwargs: Any,
    ) -> WaitableConditionType:
        """Interact with a contract."""
        contract_id = str(contract_public_id)
        response_msg = yield from self.get_contract_api_response(
            performative,
            contract_address,
            contract_id,
            contract_callable,
            **kwargs,
        )
        if response_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.default_error(contract_id, contract_callable, response_msg)
            return False

        propagated = self._propagate_contract_messages(response_msg)
        data = response_msg.raw_transaction.body.get(data_key, None)
        if data is None:
            if not propagated:
                self.default_error(contract_id, contract_callable, response_msg)
            return False

        setattr(self, placeholder, data)
        return True

    def default_error(
        self, contract_id: str, contract_callable: str, response_msg: ContractApiMessage
    ) -> None:
        """Return a default contract interaction error message."""
        self.context.logger.error(
            f"Could not successfully interact with the {contract_id} contract "
            f"using {contract_callable!r}: {response_msg}"
        )

    @property
    def shared_state(self) -> SharedState:
        """Get the shared state."""
        return cast(SharedState, self.context.state)

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return SynchronizedData(super().synchronized_data.db)

    @property
    def synced_timestamp(self) -> int:
        """Return the synchronized timestamp across the agents."""
        return int(self.round_sequence.last_round_transition_timestamp.timestamp())

    @property
    def safe_tx_hash(self) -> str:
        """Get the safe_tx_hash."""
        return self._safe_tx_hash

    @safe_tx_hash.setter
    def safe_tx_hash(self, safe_hash: str) -> None:
        """Set the safe_tx_hash."""
        length = len(safe_hash)
        if length != TX_HASH_LENGTH:
            raise ValueError(
                f"Incorrect length {length} != {TX_HASH_LENGTH} detected "
                f"when trying to assign a safe transaction hash: {safe_hash}"
            )
        self._safe_tx_hash = safe_hash[2:]

    @property
    def multi_send_txs(self) -> List[dict]:
        """Get the multisend transactions as a list of dictionaries."""
        return [dataclasses.asdict(batch) for batch in self.multisend_batches]

    @property
    def txs_value(self) -> int:
        """Get the total value of the transactions."""
        return sum(batch.value for batch in self.multisend_batches)

    @property
    def tx_hex(self) -> Optional[str]:
        """Serialize the safe tx to a hex string."""
        if self.safe_tx_hash == "":
            self.context.logger.error(
                "Cannot prepare a transaction without a transaction hash."
            )
            return None
        return hash_payload_to_hex(
            self.safe_tx_hash,
            self.txs_value,
            SAFE_GAS,
            self.params.multisend_address,
            self.multisend_data,
            SafeOperation.DELEGATE_CALL.value,
        )

    @property
    def is_first_period(self) -> bool:
        """Return whether it is the first period of the service."""
        return self.synchronized_data.period_count == 0

    @staticmethod
    def wei_to_native(wei: int) -> float:
        """Convert WEI to native token."""
        return wei / 10**18

    def _build_multisend_data(
        self,
    ) -> WaitableConditionType:
        """Get the multisend tx."""
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.params.multisend_address,
            contract_id=str(MultiSendContract.contract_id),
            contract_callable="get_tx_data",
            multi_send_txs=self.multi_send_txs,
        )
        expected_performative = ContractApiMessage.Performative.RAW_TRANSACTION
        if response_msg.performative != expected_performative:
            self.context.logger.error(
                f"Couldn't compile the multisend tx. "
                f"Expected response performative {expected_performative.value}, "  # type: ignore
                f"received {response_msg.performative.value}: {response_msg}"
            )
            return False

        multisend_data_str = response_msg.raw_transaction.body.get("data", None)
        if multisend_data_str is None:
            self.context.logger.error(
                f"Something went wrong while trying to prepare the multisend data: {response_msg}"
            )
            return False

        # strip "0x" from the response
        multisend_data_str = str(response_msg.raw_transaction.body["data"])[2:]
        self.multisend_data = bytes.fromhex(multisend_data_str)
        return True

    def _build_multisend_safe_tx_hash(self) -> WaitableConditionType:
        """Prepares and returns the safe tx hash for a multisend tx."""
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
            contract_address=self.synchronized_data.safe_contract_address,
            contract_id=str(GnosisSafeContract.contract_id),
            contract_callable="get_raw_safe_transaction_hash",
            to_address=self.params.multisend_address,
            value=self.txs_value,
            data=self.multisend_data,
            safe_tx_gas=SAFE_GAS,
            operation=SafeOperation.DELEGATE_CALL.value,
        )

        if response_msg.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(
                "Couldn't get safe tx hash. Expected response performative "
                f"{ContractApiMessage.Performative.STATE.value}, "  # type: ignore
                f"received {response_msg.performative.value}: {response_msg}."
            )
            return False

        tx_hash = response_msg.state.body.get("tx_hash", None)
        if tx_hash is None or len(tx_hash) != TX_HASH_LENGTH:
            self.context.logger.error(
                "Something went wrong while trying to get the buy transaction's hash. "
                f"Invalid hash {tx_hash!r} was returned."
            )
            return False

        # strip "0x" from the response hash
        self.safe_tx_hash = tx_hash
        return True

    def wait_for_condition_with_sleep(
        self,
        condition_gen: Callable[[], WaitableConditionType],
        timeout: Optional[float] = None,
    ) -> Generator[None, None, None]:
        """Wait for a condition to happen and sleep in-between checks.

        This is a modified version of the base `wait_for_condition` method which:
            1. accepts a generator that creates the condition instead of a callable
            2. sleeps in-between checks

        :param condition_gen: a generator of the condition to wait for
        :param timeout: the maximum amount of time to wait
        :yield: None
        """

        deadline = (
            datetime.now() + timedelta(0, timeout)
            if timeout is not None
            else datetime.max
        )

        while True:
            condition_satisfied = yield from condition_gen()
            if condition_satisfied:
                break
            if timeout is not None and datetime.now() > deadline:
                raise TimeoutException()
            self.context.logger.info(f"Retrying in {self.params.sleep_time} seconds.")
            yield from self.sleep(self.params.sleep_time)

    def finish_behaviour(self, payload: BaseTxPayload) -> Generator:
        """Finish the behaviour."""
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2022-2024 Valory AG
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
"""This package contains the rounds of TxSettlementMultiplexerAbci."""

from enum import Enum
from typing import Dict, Optional, Set, Tuple, cast

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AppState,
    BaseSynchronizedData,
    CollectSameUntilThresholdRound,
    DegenerateRound,
)
from packages.valory.skills.mech_interact_abci.states.request import (
    MechTxSubmitterRound,
)
from packages.valory.skills.nft_mint_abci.rounds import NftMintRound
from packages.valory.skills.subscription_abci.rounds import SubscriptionRound

_NO_TX_ROUND = "no_tx"


class Event(Enum):
    """Multiplexing events."""

    DONE = "done"
    MECH_TX = "mech_tx"
    NFT_TX = "nft_tx"
    SUBSCRIPTION_TX = "subscription_tx"
    FAILED_MECH_TX = "failed_mech_tx"
    FAILED_NFT_TX = "failed_nft_tx"
    FAILED_SUBSCRIPTION_TX = "failed_subscription_tx"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def tx_submitter(self) -> str:
        """Get the round that submitted a tx to transaction_settlement_abci."""
        return cast(str, self.db.get_strict("tx_submitter"))


class TxMultiplexerRound(CollectSameUntilThresholdRound):
    """A round that will be called after tx settlement is done."""

    payload_class = _NO_TX_ROUND
    payload_attribute = _NO_TX_ROUND
    synchronized_data_class = SynchronizedData

    round_id_to_event: Dict[str, Event] = {
        MechTxSubmitterRound.auto_round_id(): Event.MECH_TX,
        NftMintRound.auto_round_id(): Event.NFT_TX,
        SubscriptionRound.auto_round_id(): Event.SUBSCRIPTION_TX,
    }

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """
        The end block.

        This is a dummy round, no consensus is necessary here.
        There is no need to send a tx through, nor to check for majority.
        We simply use this round to check which round submitted the tx,
        and move to the next state in accordance to that.
        """
        sync_data = cast(SynchronizedData, self.synchronized_data)
        return sync_data, self.round_id_to_event[sync_data.tx_submitter]


class TxMultiplexerFailedRound(CollectSameUntilThresholdRound):
    """A round that will be called after tx settlement has failed."""

    payload_class = _NO_TX_ROUND
    payload_attribute = _NO_TX_ROUND
    synchronized_data_class = SynchronizedData

    round_id_to_event: Dict[str, Event] = {
        MechTxSubmitterRound.auto_round_id(): Event.FAILED_MECH_TX,
        NftMintRound.auto_round_id(): Event.FAILED_NFT_TX,
        SubscriptionRound.auto_round_id(): Event.FAILED_SUBSCRIPTION_TX,
    }

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """
        The end block.

        This is a dummy round, no consensus is necessary here.
        There is no need to send a tx through, nor to check for majority.
        We simply use this round to check which round submitted the tx,
        and move to the next state in accordance to that.
        """
        sync_data = cast(SynchronizedData, self.synchronized_data)
        return sync_data, self.round_id_to_event[sync_data.tx_submitter]


class FinishedMechTxRound(DegenerateRound):
    """Finished mech tx round."""


class FinishedNFTMintTxRound(DegenerateRound):
    """Finished nft mint round."""


class FinishedSubscriptionTxRound(DegenerateRound):
    """Finished subscription purchase round."""


class FinishedWithFailedMechTxRound(DegenerateRound):
    """Finished with failed tx round."""


class FinishedWithFailedNFTMintTxRound(DegenerateRound):
    """Finished with failed nft mint round."""


class FinishedWithFailedSubscriptionTxRound(DegenerateRound):
    """Finished with failed subscription purchase round."""


class TxSettlementMultiplexerAbci(AbciApp[Event]):
    """ABCI app to multiplex the transaction settlement skill."""

    initial_round_cls: AppState = TxMultiplexerRound
    initial_states: Set[AppState] = {TxMultiplexerRound, TxMultiplexerFailedRound}
    transition_function: AbciAppTransitionFunction = {
        TxMultiplexerRound: {
            Event.MECH_TX: FinishedMechTxRound,
            Event.NFT_TX: FinishedNFTMintTxRound,
            Event.SUBSCRIPTION_TX: FinishedSubscriptionTxRound,
        },
        TxMultiplexerFailedRound: {
            Event.FAILED_MECH_TX: FinishedWithFailedMechTxRound,
            Event.FAILED_NFT_TX: FinishedWithFailedNFTMintTxRound,
            Event.FAILED_SUBSCRIPTION_TX: FinishedWithFailedSubscriptionTxRound,
        },
        FinishedWithFailedMechTxRound: {},
        FinishedWithFailedNFTMintTxRound: {},
        FinishedSubscriptionTxRound: {},
        FinishedMechTxRound: {},
        FinishedNFTMintTxRound: {},
        FinishedWithFailedSubscriptionTxRound: {},
    }
    final_states: Set[AppState] = {
        FinishedMechTxRound,
        FinishedNFTMintTxRound,
        FinishedWithFailedMechTxRound,
        FinishedWithFailedNFTMintTxRound,
        FinishedSubscriptionTxRound,
        FinishedWithFailedSubscriptionTxRound,
    }
    db_pre_conditions: Dict[AppState, Set[str]] = {
        TxMultiplexerRound: set(),
        TxMultiplexerFailedRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedMechTxRound: set(),
        FinishedNFTMintTxRound: set(),
        FinishedWithFailedMechTxRound: set(),
        FinishedWithFailedNFTMintTxRound: set(),
        FinishedSubscriptionTxRound: set(),
        FinishedWithFailedSubscriptionTxRound: set(),
    }

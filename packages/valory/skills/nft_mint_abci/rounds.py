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

"""This package contains the rounds of NftMintAbciApp."""

import json
from abc import ABC
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set, Tuple, cast

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AppState,
    BaseSynchronizedData,
    CollectSameUntilThresholdRound,
    DegenerateRound,
    EventToTimeout,
)
from packages.valory.skills.mech_interact_abci.states.base import (
    MechInteractionResponse,
)
from packages.valory.skills.nft_mint_abci.payloads import NftMintPayload
from packages.valory.skills.abstract_round_abci.base import get_name


MAX_TOKEN_EVENT_RETRIES = 3


class Event(Enum):
    """NftMintAbciApp Events"""

    NO_MAJORITY = "no_majority"
    DONE = "done"
    ROUND_TIMEOUT = "round_timeout"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def most_voted_tx_hash(self) -> str:
        """Get the most_voted_tx_hash."""
        return cast(str, self.db.get_strict("most_voted_tx_hash"))

    @property
    def mech_responses(self) -> List[MechInteractionResponse]:
        """Get the mech responses."""
        serialized = self.db.get("mech_responses", "[]")
        responses = json.loads(serialized)
        return [MechInteractionResponse(**response_item) for response_item in responses]


class NftMintRound(CollectSameUntilThresholdRound):
    """NftMintRound"""

    payload_class = NftMintPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = "content"

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """End block."""
        # TODO: incomplete implementation
        if self.threshold_reached and any(
            [val is not None for val in self.most_voted_payload_values]
        ):
            return (
                self.synchronized_data.update(
                    synchronized_data_class=self.synchronized_data_class,
                    **{
                        get_name(
                            SynchronizedData.most_voted_tx_hash
                        ): self.most_voted_payload
                    },
                ),
                Event.DONE,
            )
        return None

class VerifyMintRound(CollectSameUntilThresholdRound):
    """VerifyMintRound"""

    payload_class = NftMintPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY
    collection_key = "content"

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """End block."""
        # TODO: incomplete implementation
        if self.threshold_reached and any(
            [val is not None for val in self.most_voted_payload_values]
        ):
            return (
                self.synchronized_data.update(
                    synchronized_data_class=self.synchronized_data_class,
                    **{
                        get_name(
                            SynchronizedData.most_voted_tx_hash
                        ): self.most_voted_payload
                    },
                ),
                Event.DONE,
            )
        return None

class FinishedNftMintRound(DegenerateRound, ABC):
    """FinishedNftMintRound"""

class FinishedVerifyMintRound(DegenerateRound, ABC):
    """FinishedVerifyMintRound"""


class NftMintAbciApp(AbciApp[Event]):
    """NftMintAbciApp"""

    initial_round_cls: AppState = NftMintRound
    initial_states: Set[AppState] = {NftMintRound, VerifyMintRound}
    transition_function: AbciAppTransitionFunction = {
        NftMintRound: {
            Event.DONE: FinishedNftMintRound,
            Event.NO_MAJORITY: NftMintRound,
            Event.ROUND_TIMEOUT: NftMintRound,
        },
        FinishedNftMintRound: {},
        VerifyMintRound: {
            Event.DONE: FinishedVerifyMintRound,
            Event.NO_MAJORITY: VerifyMintRound,
            Event.ROUND_TIMEOUT: VerifyMintRound,
        },
        FinishedVerifyMintRound: {}
    }
    final_states: Set[AppState] = {
        FinishedNftMintRound,
        FinishedVerifyMintRound,
    }
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    db_pre_conditions: Dict[AppState, Set[str]] = {
        NftMintRound: set(),
        VerifyMintRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedNftMintRound: set(),
        FinishedVerifyMintRound: set()
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset([])

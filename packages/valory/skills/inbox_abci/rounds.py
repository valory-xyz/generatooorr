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

"""This package contains the rounds of InboxAbciApp."""

import json
from abc import ABC
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AppState,
    BaseSynchronizedData,
    CollectSameUntilThresholdRound,
    DegenerateRound,
    EventToTimeout,
    get_name,
)
from packages.valory.skills.inbox_abci.payloads import InboxPayload


MAX_TOKEN_EVENT_RETRIES = 3


class Event(Enum):
    """InboxAbciApp Events"""

    NO_MAJORITY = "no_majority"
    DONE = "done"
    ROUND_TIMEOUT = "round_timeout"
    NO_REQUEST = "no_request"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def mech_requests(self) -> List:
        """Get the mech requests."""
        serialized = self.db.get("mech_requests", "[]")
        # TOFIX: Match this with SynchronizedData.mech_requests in mech_interact_abci
        return json.loads(serialized)

    @property
    def requests(self) -> Dict:
        """Get the mech requests."""
        return self.db.get("requests", {})


class WaitRound(CollectSameUntilThresholdRound):
    """Wait for request."""

    no_request = {"no_request": True}
    payload_class = InboxPayload
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            payload = json.loads(
                self.most_voted_payload,
            )
            # If no requeest - WaitRound.no_request # noqa: E800
            # Else - {"address": "...", "prompt": "...", "tool": "...", "nonce": ...} # noqa: E800
            if payload == WaitRound.no_request:
                return self.synchronized_data, Event.NO_REQUEST

            address = payload.pop("address")
            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=SynchronizedData,
                **{
                    get_name(SynchronizedData.mech_requests): json.dumps([payload]),
                    get_name(SynchronizedData.requests): {payload["nonce"]: address},
                }
            )
            return (synchronized_data, Event.DONE)
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedInboxWaitingRound(DegenerateRound, ABC):
    """FinishedTokenTrackRound"""

class FinishedWithoutRequestRound(DegenerateRound, ABC):
    """FinishedWithoutRequestRound"""


class InboxAbciApp(AbciApp[Event]):
    """InboxAbciApp"""

    initial_round_cls: AppState = WaitRound
    initial_states: Set[AppState] = {WaitRound}
    transition_function: AbciAppTransitionFunction = {
        WaitRound: {
            Event.DONE: FinishedInboxWaitingRound,
            Event.NO_REQUEST: FinishedWithoutRequestRound,
            Event.NO_MAJORITY: WaitRound,
            Event.ROUND_TIMEOUT: WaitRound,
        },
        FinishedInboxWaitingRound: {},
        FinishedWithoutRequestRound: {},
    }
    final_states: Set[AppState] = {
        FinishedInboxWaitingRound,
        FinishedWithoutRequestRound,
    }
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    db_pre_conditions: Dict[AppState, Set[str]] = {
        WaitRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedInboxWaitingRound: set(),
        FinishedWithoutRequestRound: set(),
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset([])

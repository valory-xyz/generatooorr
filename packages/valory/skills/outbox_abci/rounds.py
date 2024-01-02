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

"""This package contains the rounds of OutboxAbciApp."""
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
    EventToTimeout, get_name,
)
from packages.valory.skills.mech_interact_abci.states.base import (
    MechInteractionResponse,
)
from packages.valory.skills.outbox_abci.payloads import PushNotificationPayload


MAX_TOKEN_EVENT_RETRIES = 3


class Event(Enum):
    """OutboxAbciApp Events"""

    NO_MAJORITY = "no_majority"
    DONE = "done"
    ROUND_TIMEOUT = "round_timeout"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def token_id(self) -> str:
        """Get the verified tx hash."""
        return cast(str, self.db.get_strict("token_id"))

    @property
    def requests(self) -> Dict:
        """Get the mech requests."""
        return self.db.get("requests", {})

    @property
    def mech_responses(self) -> List[MechInteractionResponse]:
        """Get the mech responses."""
        serialized = self.db.get("mech_responses", "[]")
        responses = json.loads(serialized)
        return [MechInteractionResponse(**response_item) for response_item in responses]


class PushNotificationRound(CollectSameUntilThresholdRound):
    """PushNotificationRound"""

    payload_class = PushNotificationPayload
    synchronized_data_class = SynchronizedData
    ERROR_PAYLOAD = {"error": True}

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            return self.synchronized_data, Event.DONE
        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedPushNotificationRound(DegenerateRound, ABC):
    """FinishedPushNotificationRound"""


class OutboxAbciApp(AbciApp[Event]):
    """OutboxAbciApp"""

    initial_round_cls: AppState = PushNotificationRound
    initial_states: Set[AppState] = {PushNotificationRound}
    transition_function: AbciAppTransitionFunction = {
        PushNotificationRound: {
            Event.DONE: FinishedPushNotificationRound,
            Event.NO_MAJORITY: PushNotificationRound,
            Event.ROUND_TIMEOUT: PushNotificationRound,
        },
        FinishedPushNotificationRound: {},
    }
    final_states: Set[AppState] = {
        FinishedPushNotificationRound,
    }
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    db_pre_conditions: Dict[AppState, Set[str]] = {
        PushNotificationRound: {
            get_name(SynchronizedData.token_id),
        },
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedPushNotificationRound: set(),
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset([])

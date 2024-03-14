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
    DegenerateRound,
    EventToTimeout, CollectSameUntilThresholdRound, get_name, DeserializedCollection, CollectionRound, VotingRound,
)
from packages.valory.skills.subscription_abci.payloads import SubscriptionPayload, ClaimPayload
from packages.valory.skills.transaction_settlement_abci.rounds import (
    SynchronizedData as TxSettlementSyncedData,
)

MAX_TOKEN_EVENT_RETRIES = 3


class Event(Enum):
    """InboxAbciApp Events"""

    NO_MAJORITY = "no_majority"
    DONE = "done"
    ROUND_TIMEOUT = "round_timeout"
    NO_REQUEST = "no_request"
    NO_SUBSCRIPTION = "no_subscription"
    NONE = "none"
    SUBSCRIPTION_ERROR = "subscription_error"


class SynchronizedData(TxSettlementSyncedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    def _get_deserialized(self, key: str) -> DeserializedCollection:
        """Strictly get a collection and return it deserialized."""
        serialized = self.db.get_strict(key)
        return CollectionRound.deserialize_collection(serialized)

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

    @property
    def tx_submitter(self) -> str:
        """Get the tx submitter."""
        return self.db.get("tx_submitter", "")

    @property
    def participant_to_tx_prep(self) -> DeserializedCollection:
        """Get the participants to bet-placement."""
        return self._get_deserialized("participant_to_tx_prep")

    @property
    def agreement_id(self) -> str:
        """Get the agreement id."""
        return self.db.get("agreement_id", "")


class TxPreparationRound(CollectSameUntilThresholdRound):
    """A round for preparing a transaction."""

    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    none_event = Event.NONE
    no_majority_event = Event.NO_MAJORITY
    selection_key: Tuple[str, ...] = (
        get_name(SynchronizedData.tx_submitter),
        get_name(SynchronizedData.most_voted_tx_hash),
    )
    collection_key = get_name(SynchronizedData.participant_to_tx_prep)
    payload_class = SubscriptionPayload


class SubscriptionRound(TxPreparationRound):
    """A round in which the agents prepare a tx to initiate a request to a mech to determine the answer to a bet."""

    payload_class = SubscriptionPayload
    none_event = Event.NO_SUBSCRIPTION

    NO_TX_PAYLOAD = "no_tx"
    ERROR_PAYLOAD = "error"

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """Process the end of the block."""
        if self.threshold_reached:
            tx_hash = self.most_voted_payload_values[1]
            if tx_hash == self.ERROR_PAYLOAD:
                return self.synchronized_data, Event.SUBSCRIPTION_ERROR

            if tx_hash == self.NO_TX_PAYLOAD:
                return self.synchronized_data, Event.NO_SUBSCRIPTION

        update = super().end_block()
        if update is None:
            return None

        sync_data, event = update
        agreement_id = self.most_voted_payload_values[2]
        sync_data = sync_data.update(
            agreement_id=agreement_id,
        )
        return sync_data, event


class ClaimRound(VotingRound):
    """A round for preparing a transaction."""

    payload_class = ClaimPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    negative_event = Event.SUBSCRIPTION_ERROR
    no_majority_event = Event.NO_MAJORITY
    collection_key = get_name(SynchronizedData.participant_to_votes)


class FinishedSubscriptionRound(DegenerateRound, ABC):
    """FinishedSubscriptionRound"""


class FinishedWithoutSubscriptionRound(DegenerateRound, ABC):
    """FinishedWithoutSubscriptionRound"""


class FinishedClaimingRound(DegenerateRound, ABC):
    """FinishedClaimingRound"""


class SubscriptionAbciApp(AbciApp[Event]):
    """InboxAbciApp"""

    initial_round_cls: AppState = SubscriptionRound
    initial_states: Set[AppState] = {SubscriptionRound, ClaimRound}
    transition_function: AbciAppTransitionFunction = {
        SubscriptionRound: {
            Event.DONE: FinishedSubscriptionRound,
            Event.NO_SUBSCRIPTION: FinishedWithoutSubscriptionRound,
            Event.NONE: SubscriptionRound,
            Event.SUBSCRIPTION_ERROR: SubscriptionRound,
            Event.NO_MAJORITY: SubscriptionRound,
            Event.ROUND_TIMEOUT: SubscriptionRound,
        },
        ClaimRound: {
            Event.DONE: FinishedClaimingRound,
            Event.SUBSCRIPTION_ERROR: ClaimRound,
            Event.NO_MAJORITY: ClaimRound,
            Event.ROUND_TIMEOUT: ClaimRound,
        },
        FinishedSubscriptionRound: {},
        FinishedWithoutSubscriptionRound: {},
        FinishedClaimingRound: {},
    }
    final_states: Set[AppState] = {
        FinishedSubscriptionRound,
        FinishedWithoutSubscriptionRound,
        FinishedClaimingRound,
    }
    event_to_timeout: EventToTimeout = {
        Event.ROUND_TIMEOUT: 30.0,
    }
    db_pre_conditions: Dict[AppState, Set[str]] = {
        SubscriptionRound: set(),
        ClaimRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedSubscriptionRound: {
            get_name(SynchronizedData.agreement_id),
            get_name(SynchronizedData.participant_to_tx_prep),
            get_name(SynchronizedData.tx_submitter),
            get_name(SynchronizedData.most_voted_tx_hash)
        },
        FinishedWithoutSubscriptionRound: set(),
        FinishedClaimingRound: set(),
    }
    cross_period_persisted_keys: FrozenSet[str] = frozenset([])

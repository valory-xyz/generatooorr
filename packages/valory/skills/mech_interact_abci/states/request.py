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

"""This module contains the request state of the mech interaction abci app."""

from enum import Enum
from typing import Optional, Tuple

from packages.valory.skills.abstract_round_abci.base import (
    BaseSynchronizedData,
    CollectSameUntilThresholdRound,
    get_name,
)
from packages.valory.skills.mech_interact_abci.payloads import MechRequestPayload
from packages.valory.skills.mech_interact_abci.states.base import (
    Event,
    MechInteractionRound,
    SynchronizedData,
)


_NO_TX_ROUND = "no_tx"


class MechRequestRound(MechInteractionRound):
    """A round for performing requests to a Mech."""

    payload_class = MechRequestPayload

    selection_key = (
        get_name(SynchronizedData.most_voted_tx_hash),
        get_name(SynchronizedData.mech_price),
        get_name(SynchronizedData.mech_requests),
        get_name(SynchronizedData.mech_responses),
    )
    collection_key = get_name(SynchronizedData.participant_to_requests)
    none_event = Event.SKIP_REQUEST


class MechTxSubmitterRound(CollectSameUntilThresholdRound):
    """Mech TX multiplexer."""

    payload_class = _NO_TX_ROUND
    payload_attribute = _NO_TX_ROUND
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Enum]]:
        """
        The end block.

        This is a dummy round, no consensus is necessary here.
        There is no need to send a tx through, nor to check for majority.
        We simply use this round to check which round submitted the tx,
        and move to the next state in accordance to that.
        """
        return (
            self.synchronized_data.update(
                synchronized_data_class=self.synchronized_data_class,
                tx_submitter=self.auto_round_id(),
            ),
            Event.DONE,
        )

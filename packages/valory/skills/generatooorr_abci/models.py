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

"""This module contains the shared state for the abci skill of GeneratooorrAbciApp."""

from packages.valory.skills.abstract_round_abci.models import ApiSpecs
from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.abstract_round_abci.models import (
    SharedState as BaseSharedState,
)
from packages.valory.skills.generatooorr_abci.composition import GeneratooorrAbciApp
from packages.valory.skills.inbox_abci.models import Params as BaseInboxAbciParams
from packages.valory.skills.mech_interact_abci.models import (
    MechResponseSpecs as BaseMechResponseSpecs,
)
from packages.valory.skills.mech_interact_abci.models import (
    Params as BaseMechInteractAbciParams,
)
from packages.valory.skills.mech_interact_abci.rounds import Event as MechInteractEvent
from packages.valory.skills.outbox_abci.models import Params as BaseOutboxAbciParams
from packages.valory.skills.reset_pause_abci.rounds import Event as ResetPauseEvent
from packages.valory.skills.termination_abci.models import (
    TerminationParams as BaseTerminationParams,
)
from packages.valory.skills.transaction_settlement_abci.models import (
    TransactionParams as BaseTransactionParams,
)


MechInteractAbciParams = BaseMechInteractAbciParams
InboxAbciParams = BaseInboxAbciParams
OutboxAbciParams = BaseOutboxAbciParams
TerminationParams = BaseTerminationParams
TransactionParams = BaseTransactionParams

Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool
MechResponseSpecs = BaseMechResponseSpecs

MARGIN = 5
MULTIPLIER = 2


class RandomnessApi(ApiSpecs):
    """A model that wraps ApiSpecs for randomness api specifications."""


class SharedState(BaseSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = GeneratooorrAbciApp

    def setup(self) -> None:
        """Set up."""
        super().setup()
        GeneratooorrAbciApp.event_to_timeout[
            ResetPauseEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds
        GeneratooorrAbciApp.event_to_timeout[
            ResetPauseEvent.RESET_AND_PAUSE_TIMEOUT
        ] = (self.context.params.reset_pause_duration + MARGIN)
        GeneratooorrAbciApp.event_to_timeout[
            MechInteractEvent.ROUND_TIMEOUT
        ] = self.context.params.round_timeout_seconds


class Params(
    MechInteractAbciParams,
    InboxAbciParams,
    OutboxAbciParams,
    TerminationParams,
    TransactionParams,
):
    """A model to represent params for multiple abci apps."""

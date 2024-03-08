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

"""This module contains the shared state for the abci skill of InboxAbciApp."""
from dataclasses import dataclass
from typing import Any

from hexbytes import HexBytes

from packages.valory.contracts.multisend.contract import MultiSendOperation
from packages.valory.skills.abstract_round_abci.models import BaseParams
from packages.valory.skills.abstract_round_abci.models import (
    BenchmarkTool as BaseBenchmarkTool,
)
from packages.valory.skills.abstract_round_abci.models import Requests as BaseRequests
from packages.valory.skills.abstract_round_abci.models import (
    SharedState as BaseSharedState,
)
from packages.valory.skills.inbox_abci.rounds import InboxAbciApp


@dataclass
class MultisendBatch:
    """A structure representing a single transaction of a multisend."""

    to: str
    data: HexBytes
    value: int = 0
    operation: MultiSendOperation = MultiSendOperation.CALL


class SharedState(BaseSharedState):
    """Keep the current shared state of the skill."""

    abci_app_cls = InboxAbciApp


class Params(BaseParams):
    """Parameters."""

    inbox_auth: str
    farcaster_auth: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize parameters."""
        self.inbox_auth = self._ensure("inbox_auth", kwargs=kwargs, type_=str)
        self.farcaster_auth = self._ensure("farcaster_auth", kwargs=kwargs, type_=str)
        super().__init__(*args, **kwargs)


Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool

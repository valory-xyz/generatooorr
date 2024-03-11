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
from typing import Any, Dict, Iterable

from aea.exceptions import enforce
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


def _raise_incorrect_config(key: str, values: Any) -> None:
    """Raise a `ValueError` for incorrect configuration of a nested_list workaround."""
    raise ValueError(
        f"The given configuration for {key!r} is incorrectly formatted: {values}!"
        "The value is expected to be a list of lists that can be represented as a dictionary."
    )


def nested_list_todict_workaround(
    kwargs: Dict,
    key: str,
) -> Dict:
    """Get a nested list from the kwargs and convert it to a dictionary."""
    values = list(kwargs.get(key, []))
    if len(values) == 0:
        raise ValueError(f"No {key!r} specified in agent's configurations: {kwargs}!")
    if any(not issubclass(type(nested_values), Iterable) for nested_values in values):
        _raise_incorrect_config(key, values)
    if any(len(nested_values) % 2 == 1 for nested_values in values):
        _raise_incorrect_config(key, values)
    return {value[0]: value[1] for value in values}


class Params(BaseParams):
    """Parameters."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize parameters."""
        self.multisend_address = kwargs.get("multisend_address", None)
        enforce(
            self.multisend_address is not None,
            "multisend_address must be set!",
        )
        self.mech_agent_address
        self.use_nevermined = self._ensure("use_nevermined", kwargs, type_=bool)
        self.mech_to_subscription_params: Dict[
            str, Any
        ] = nested_list_todict_workaround(
            kwargs,
            "mech_to_subscription_params",
        )
        super().__init__(*args, **kwargs)


Requests = BaseRequests
BenchmarkTool = BaseBenchmarkTool

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

"""This package contains round behaviours of InboxAbciApp."""

import json
from abc import ABC
from typing import Generator, Set, Type, cast

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.inbox_abci.handlers import InBox
from packages.valory.skills.inbox_abci.models import Params
from packages.valory.skills.inbox_abci.payloads import InboxPayload
from packages.valory.skills.inbox_abci.rounds import (
    InboxAbciApp,
    SynchronizedData,
    WaitRound,
)


class InboxAbciBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the common apps' skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)

    @property
    def inbox(self) -> InBox:
        """Return the params."""
        return cast(InBox, self.context.state.inbox)


class WaitBehaviour(InboxAbciBaseBehaviour):
    """WaitBehaviour"""

    matching_round: Type[AbstractRound] = WaitRound

    def async_act(self) -> Generator:
        """Get a list of the new tokens."""
        request = self.inbox.get()
        if request is None:
            request = WaitRound.no_request
            yield from self.sleep(1)
        self.context.logger.info(f"Received request -> {request}")
        with self.context.benchmark_tool.measure(
            self.behaviour_id,
        ).consensus():
            payload = InboxPayload(
                sender=self.context.agent_address, content=json.dumps(request)
            )
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()
        self.set_done()


class InboxAbciRoundBehaviour(AbstractRoundBehaviour):
    """InboxAbciRoundBehaviour"""

    initial_behaviour_cls = WaitBehaviour
    abci_app_cls = InboxAbciApp
    behaviours: Set[Type[BaseBehaviour]] = [
        WaitBehaviour,
    ]

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

"""This package contains round behaviours of OutboxAbciApp."""

import json
from abc import ABC
from typing import Dict, Generator, Optional, Set, Tuple, Type, cast

from packages.valory.protocols.contract_api import ContractApiMessage
from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour, BaseBehaviour)
from packages.valory.skills.mech_interact_abci.states.base import \
    MechInteractionResponse
from packages.valory.skills.outbox_abci.models import Params, SharedState
from packages.valory.skills.outbox_abci.payloads import TokenTrackPayload
from packages.valory.skills.outbox_abci.rounds import (OutboxAbciApp,
                                                       PushNotificationRound,
                                                       SynchronizedData)


class OutboxAbciBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the common apps' skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)


class PushNotificationBehaviour(OutboxAbciBaseBehaviour):
    """PushNotificationBehaviour"""

    matching_round: Type[AbstractRound] = PushNotificationRound

    def _push_from_response(self, response: MechInteractionResponse) -> Generator:
        """
        Push notification from mech interaction response.

        https://docs.walletconnect.com/web3inbox/sending-notifications?send-client=curl
        """
        self.context.logger.info(f"Pushing notification for {response}")
        # notification_response = yield from self.get_http_response(
        #     method="post",
        #     url=f"https://notify.walletconnect.com/{self.params.w3_inbox_project_id}/notify",  # TODO: Define w3_inbox_project_id as param
        #     headers={
        #         "Content-Type": "application/json",
        #         "Authorization": f"Bearer {self.params.w3_notify_api_key}'",
        #     },
        #     content=json.dumps(
        #         {
        #             "notification": {
        #                 "type": "...",  # Notification type ID copied from Cloud
        #                 "title": "Request processed",
        #                 "body": response.data,  # TODO: Notification format
        #             },
        #             "accounts": ["eip155:1:0x"],  # CAIP-10 account ID
        #         }
        #     ),
        # )
        # self.context.logger.info(notification_response)

    def async_act(self) -> Generator:
        """Get a list of the new tokens."""
        for response in self.synchronized_data.mech_responses:
            data = json.loads(response.data)
            response_data = {
                "id": self.context.state.inbox.next_id,
                **data,
            }
            self.context.state.inbox.add_response(response_data)
            yield from self._push_from_response(response=response)
        with self.context.benchmark_tool.measure(
            self.behaviour_id,
        ).consensus():
            payload = {"status": True}
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class OutboxAbciRoundBehaviour(AbstractRoundBehaviour):
    """OutboxAbciRoundBehaviour"""

    initial_behaviour_cls = PushNotificationBehaviour
    abci_app_cls = OutboxAbciApp
    behaviours: Set[Type[BaseBehaviour]] = [
        PushNotificationBehaviour,
    ]

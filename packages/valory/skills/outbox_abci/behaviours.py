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
from typing import Generator, Set, Type, cast

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.outbox_abci.models import Params
from packages.valory.skills.outbox_abci.payloads import PushNotificationPayload
from packages.valory.skills.outbox_abci.rounds import (
    OutboxAbciApp,
    PushNotificationRound,
    SynchronizedData,
)


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
    retry_count: int = 0

    # TODO: this won't work for more than one agent as then all of them will send the same notification.

    def _push_from_response(self, retry: int) -> Generator:
        """
        Push notification from mech interaction response.

        https://docs.walletconnect.com/web3inbox/sending-notifications?send-client=curl
        """
        response = self.synchronized_data.mech_responses[0]
        data = json.loads(response.data)
        data["id"] = self.context.state.inbox.next_id
        self.context.state.inbox.add_response(data)
        address = self.synchronized_data.requests[response.nonce]
        self.context.logger.info(
            f"Pushing notification for address {address} with noncee {response.nonce}"
        )
        notification_response = yield from self.get_http_response(
            method="post",
            url=f"https://notify.walletconnect.com/{self.params.w3_inbox_project_id}/notify",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.params.w3_notification_api_key}",
            },
            content=json.dumps(
                {
                    "notification": {
                        "type": f"{self.params.w3_notification_type}",
                        "title": "Another short? WTF!",
                        "body": f"Your recently requested short has arrived! Minted NFT with token ID {self.synchronized_data.token_id}",
                    },
                    "accounts": [f"eip155:1:{address}"],
                }
            ).encode("utf-8"),
        )
        self.context.logger.info(f"Notification response for {address} and token {self.synchronized_data.token_id}: {notification_response}")
        try:
            response = json.loads(notification_response)
            if "sent" in response and len(response["sent"]) > 0:
                return True, retry
        return False, retry

    def async_act(self) -> Generator:
        """Get a list of the new tokens."""
        success, retry = yield from self._push_from_response(self.retry_count)
        if not success and retry < self.retry_count:
            retry += 1
            return
        if not success and retry >= self.retry_count:
            self.logger.error("Retries exceeded, not retrying notification!")
        with self.context.benchmark_tool.measure(
            self.behaviour_id,
        ).consensus():
            payload = PushNotificationPayload(
                sender=self.context.agent_address, success=status
            )
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

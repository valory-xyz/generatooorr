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

"""This module contains the handlers for the skill of InboxAbciApp."""

import json
import re
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple, cast
from urllib.parse import urlparse
from uuid import uuid4

from aea.protocols.base import Message
from typing_extensions import TypedDict

from packages.valory.connections.http_server.connection import \
    PUBLIC_ID as HTTP_SERVER_PUBLIC_ID
from packages.valory.protocols.http.message import HttpMessage
from packages.valory.skills.abstract_round_abci.handlers import \
    ABCIRoundHandler as BaseABCIRoundHandler
from packages.valory.skills.abstract_round_abci.handlers import \
    ContractApiHandler as BaseContractApiHandler
from packages.valory.skills.abstract_round_abci.handlers import \
    HttpHandler as BaseHttpHandler
from packages.valory.skills.abstract_round_abci.handlers import \
    IpfsHandler as BaseIpfsHandler
from packages.valory.skills.abstract_round_abci.handlers import \
    LedgerApiHandler as BaseLedgerApiHandler
from packages.valory.skills.abstract_round_abci.handlers import \
    SigningHandler as BaseSigningHandler
from packages.valory.skills.abstract_round_abci.handlers import \
    TendermintHandler as BaseTendermintHandler
from packages.valory.skills.inbox_abci.dialogues import (HttpDialogue,
                                                         HttpDialogues)
from packages.valory.skills.inbox_abci.models import SharedState
from packages.valory.skills.inbox_abci.rounds import SynchronizedData

ABCIRoundHandler = BaseABCIRoundHandler
SigningHandler = BaseSigningHandler
LedgerApiHandler = BaseLedgerApiHandler
ContractApiHandler = BaseContractApiHandler
TendermintHandler = BaseTendermintHandler
IpfsHandler = BaseIpfsHandler

JSON_MIME_TYPE_HEADER = "Content-Type: application/json\n"
CODE_TO_MESSAGE = {
    200: "Ok",
    404: "Not Found",
    400: "Bad Request",
}


class HttpResponseCode(Enum):
    """Http response codes."""

    OK = 200
    NOT_FOUND = 404
    BAD_REQUEST = 400

    @property
    def message(self) -> str:
        """HTTP message for the code."""
        return CODE_TO_MESSAGE[self.value]


class HttpMethod(Enum):
    """Http methods"""

    GET = "get"
    HEAD = "head"
    POST = "post"


class TypedResponse(TypedDict):
    """Typed response dict."""

    code: HttpResponseCode
    data: Dict
    headers: Optional[str]


class HttpApplication:
    """Http Server class."""

    def __init__(self, inbox: "InBox") -> None:
        """Initialize object."""
        self.inbox = inbox

    def handle(self,message: HttpMessage) -> TypedResponse:
        """Handle incoming request."""
        url_meta = urlparse(message.url)
        handler: Callable[[HttpMessage, HttpDialogue], TypedResponse] = getattr(
            self, message.method + url_meta.path.replace("/", "_"), self._respond_404
        )
        return handler(message)

    def post_generate(self, message: HttpMessage) -> TypedResponse:
        """Handle POST /generate"""
        self.inbox.put(json.loads(message.body.decode()))
        return TypedResponse(
            code=HttpResponseCode.OK,
            data={"status": "CREATED", "id": "0x"},
            headers=JSON_MIME_TYPE_HEADER,
        )

    def get_responses(self, message: HttpMessage) -> TypedResponse:
        """Handle GET /responses"""
        return TypedResponse(
            code=HttpResponseCode.OK,
            data={"data": self.inbox.get_responses()},
            headers=JSON_MIME_TYPE_HEADER,
        )

    def _respond_404(self, message: HttpMessage) -> TypedResponse:
        """Send an OK response with the provided data"""
        return TypedResponse(
            code=HttpResponseCode.NOT_FOUND,
            data={
                "error": f"No route implementation found for {message.method.upper()} {urlparse(message.url).path}"
            },
        )


class InBox:
    """InBox for requests."""

    _queue: List[Dict]
    _processed: List[Dict]

    def __init__(self) -> None:
        """Initialize object."""
        self._queue = []
        self._processed = []

    def get(self) -> Optional[Dict]:
        """Get request from inbox."""
        if len(self._queue) == 0:
            return None
        return self._queue.pop(0)

    def put(self, request: Dict) -> None:
        """Put request into inbox."""
        request["nonce"] = uuid4().hex
        self._queue.append(request)

    def add_response(self, response: Dict) -> None:
        """Add response to processed list."""
        self._processed.append(response)
    
    def get_responses(self) -> List[Dict]:
        """Return the available responses."""
        return self._processed

class HttpHandler(BaseHttpHandler):
    """This implements the echo handler."""

    SUPPORTED_PROTOCOL = HttpMessage.protocol_id

    app: HttpApplication

    def setup(self) -> None:
        """Setup class."""
        super().setup()
        self.context.state.inbox = InBox()
        self.app = HttpApplication(inbox=self.context.state.inbox)

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return SynchronizedData(
            db=self.context.state.round_sequence.latest_synchronized_data.db
        )

    def handle(self, message: Message) -> None:
        """
        Implement the reaction to an envelope.

        :param message: the message
        """
        message = cast(HttpMessage, message)

        # Check if this is a request sent from the http_server skill
        if (
            message.performative != HttpMessage.Performative.REQUEST
            or message.sender != str(HTTP_SERVER_PUBLIC_ID.without_hash())
        ):
            super().handle(message)
            return

        # Retrieve dialogues
        dialogues = cast(HttpDialogues, self.context.http_dialogues)
        dialogue = cast(HttpDialogue, dialogues.update(message))

        # Invalid message
        if dialogue is None:
            self.context.logger.info(
                "Received invalid http message={}, unidentified dialogue.".format(
                    message
                )
            )
            return

        # Handle message
        self.context.logger.info(
            "Received http request with method={}, url={} and body={!r}".format(
                message.method,
                message.url,
                message.body,
            )
        )
        response = self.app.handle(message=message)
        http_response = dialogue.reply(
            performative=HttpMessage.Performative.RESPONSE,
            target_message=message,
            version=message.version,
            status_code=response["code"].value,
            status_text=response["code"].message,
            headers=response.get("headers", "") + message.headers,
            body=json.dumps(response["data"]).encode("utf-8"),
        )

        # Send response
        self.context.logger.info("Responding with: {}".format(http_response))
        self.context.outbox.put_message(message=http_response)

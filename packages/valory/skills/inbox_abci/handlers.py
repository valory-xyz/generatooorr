# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023-2024 Valory AG
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
import os
from enum import Enum
from logging import Logger
from typing import Any, Callable, Dict, List, Optional, cast
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from aea.protocols.base import Message
from typing_extensions import TypedDict

from packages.valory.connections.http_server.connection import (
    PUBLIC_ID as HTTP_SERVER_PUBLIC_ID,
)
from packages.valory.protocols.http.message import HttpMessage
from packages.valory.skills.abstract_round_abci.handlers import (
    ABCIRoundHandler as BaseABCIRoundHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    ContractApiHandler as BaseContractApiHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    HttpHandler as BaseHttpHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    IpfsHandler as BaseIpfsHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    LedgerApiHandler as BaseLedgerApiHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    SigningHandler as BaseSigningHandler,
)
from packages.valory.skills.abstract_round_abci.handlers import (
    TendermintHandler as BaseTendermintHandler,
)
from packages.valory.skills.inbox_abci.dialogues import HttpDialogue, HttpDialogues
from packages.valory.skills.inbox_abci.rounds import SynchronizedData


ABCIRoundHandler = BaseABCIRoundHandler
SigningHandler = BaseSigningHandler
LedgerApiHandler = BaseLedgerApiHandler
ContractApiHandler = BaseContractApiHandler
TendermintHandler = BaseTendermintHandler
IpfsHandler = BaseIpfsHandler


JSON_MIME_HEADER = {"Content-Type": "application/json"}
RESPONSE_HEADERS = {
    "Server": "Generatooorr/0.1.0.rc01",
    "Connection": "Closed",
    "Access-Control-Allow-Origin": "*",
}
CODE_TO_MESSAGE = {
    200: "Ok",
    404: "Not Found",
    400: "Bad Request",
    401: "Unauthorized",
}

REQUEST_TIME = 30 * 60  # 30 minutes in seconds


class HttpResponseCode(Enum):
    """Http response codes."""

    OK = 200
    NOT_FOUND = 404
    BAD_REQUEST = 400
    UNAUTHORIZED = 401

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
    data: Optional[Dict]


class HttpApplication:
    """Http Server class."""

    authenticated_handlers = ["post_restore"]

    def __init__(self, inbox: "InBox", auth: str) -> None:
        """Initialize object."""
        self.inbox = inbox
        self.auth = auth

    def handle(self, message: HttpMessage) -> TypedResponse:
        """Handle incoming request."""
        url_meta = urlparse(message.url)
        handler_func = message.method + url_meta.path.replace("/", "_")
        if message.method == "post":
            headers = dict(
                map(
                    lambda x: x.split(": ", maxsplit=1),
                    message.headers.strip().split("\n"),
                )
            )
            if (
                headers.get("Authorization", "") != self.auth
                and handler_func in self.authenticated_handlers
            ):
                return TypedResponse(
                    code=HttpResponseCode.UNAUTHORIZED,
                    data={"status": "REJECTED", "message": "Invalid authentication"},
                )
        handler: Callable[[HttpMessage, HttpDialogue], TypedResponse] = getattr(
            self, handler_func, self._respond_404
        )
        return handler(message)

    def post_generate(self, message: HttpMessage) -> TypedResponse:
        """Handle POST /generate"""
        self.inbox.put(json.loads(message.body.decode()))
        return TypedResponse(
            code=HttpResponseCode.OK,
            data={"status": "CREATED", "id": "0x"},
        )

    def post_restore(self, message: HttpMessage) -> TypedResponse:
        """Handle /restore"""
        self.inbox.restore(json.loads(message.body.decode()))
        return TypedResponse(
            code=HttpResponseCode.OK,
            data={"status": "OK", "id": "0x"},
        )

    def get_responses(self, message: HttpMessage) -> TypedResponse:
        """Handle GET /responses with optional pagination."""
        # Parse query parameters from the URL
        query_params = parse_qs(urlparse(message.url).query)

        # Get all responses
        all_responses = self.inbox.get_responses()

        # Check for sorting parameters
        sort_key = query_params.get("sortBy", ["id"])[0]
        sort_order = query_params.get("sortOrder", ["desc"])[0]
        id_ = query_params.get("id", None)
        if id_ is not None:
            id_ = id_[0]
            all_responses = list(
                filter(lambda x: str(x.get("id", "")) == id_, all_responses)
            )

        # Apply sorting if sort_key is provided
        try:
            if sort_key:
                all_responses.sort(
                    key=lambda x: x.get(sort_key, None), reverse=(sort_order == "desc")
                )
        except Exception as e:
            return TypedResponse(
                code=HttpResponseCode.BAD_REQUEST,
                data={
                    "status": "ERROR",
                    "message": "Invalid sorting key",
                    "error": str(e),
                },
            )

        # Check if pageNum and limit are provided
        if "pageNum" in query_params and "limit" in query_params:
            # Convert pageNum and limit to integers
            page_size = int(query_params["pageNum"][0])
            limit = int(query_params["limit"][0])

            # Calculate the number of pages and current page
            num_pages = max(1, (len(all_responses) + limit - 1) // limit)
            current_page = max(1, page_size)

            # Calculate the start and end indices for slicing
            start_index = (current_page - 1) * limit
            end_index = start_index + limit

            # Slice the responses based on calculated indices
            paginated_responses = all_responses[start_index:end_index]

            return TypedResponse(
                code=HttpResponseCode.OK,
                data={
                    "data": paginated_responses,
                    "currentPage": current_page,
                    "numPages": num_pages,
                },
            )
        else:
            # Return all responses if pageNum and limit are not provided
            return TypedResponse(
                code=HttpResponseCode.OK,
                data={"data": all_responses},
            )

    def get_queue_time(self, message: HttpMessage) -> TypedResponse:
        """Get queue time"""
        queue = len(self.inbox._queue) + 1
        time = queue * REQUEST_TIME
        return TypedResponse(
            code=HttpResponseCode.OK,
            data={
                "queue_time_in_seconds": time,
            },
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

    def __init__(self, logger: Logger, db: Optional[str] = None) -> None:
        """Initialize object."""
        self.logger = logger
        self._db = db or "/logs/db.json"
        self._deserialize_state()

    def _serialize_state(self, state: Dict[str, Any]) -> None:
        """Serialize the state to the db."""
        with open(self._db, "w") as file:
            json.dump(state, file)

    def _deserialize_state(self) -> None:
        """Deserialize the state from the db."""
        self._processed = []
        self._queue = []
        self._processing_req = None

        if not os.path.exists(self._db):
            # if the file exists, load the state from it
            self.logger.warning(
                f"File {self._db} doesn't exist. Starting with empty state."
            )
            return

        with open(self._db, "r") as file:
            try:
                file_json = json.load(file)
                self._processed = file_json["processed"]
                # if a request was being processed, add it back to the front of the queue
                self._processing_req = file_json.get("processing", None)
                if self._processing_req is not None:
                    self._queue.append(self._processing_req)
                self._queue = self._queue + file_json.get("queue", [])
            except (json.decoder.JSONDecodeError, KeyError) as e:
                self.logger.error(
                    f"Error deserializing state: {e}. Starting with empty state."
                )

    def get(self) -> Optional[Dict]:
        """Get request from inbox."""
        if len(self._queue) == 0:
            return None
        self._processing_req = self._queue.pop(0)
        return self._processing_req

    def put(self, request: Dict) -> None:
        """Put request into inbox."""
        request["nonce"] = uuid4().hex
        self._queue.append(request)

    def add_response(self, response: Dict) -> None:
        """Add response to processed list."""
        self._processed.append(response)
        self._processing_req = None
        state = {
            "queue": self._queue,
            "processed": self._processed,
            "processing": self._processing_req,
        }
        self._serialize_state(state)

    def get_responses(self) -> List[Dict]:
        """Return the available responses."""
        return self._processed

    def restore(self, processed: List) -> None:
        """Restore responses"""
        self._processed = processed

    @property
    def next_id(self) -> int:
        """Get the next response id"""
        return len(self._processed) + 1


class HttpHandler(BaseHttpHandler):
    """This implements the echo handler."""

    SUPPORTED_PROTOCOL = HttpMessage.protocol_id

    app: HttpApplication

    def setup(self) -> None:
        """Setup class."""
        super().setup()
        self.context.state.inbox = InBox(logger=self.context.logger)
        self.app = HttpApplication(
            inbox=self.context.state.inbox,
            auth=self.context.params.inbox_auth,
        )

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return SynchronizedData(
            db=self.context.state.round_sequence.latest_synchronized_data.db
        )

    @staticmethod
    def response_headers(extra: Optional[Dict[str, str]] = None) -> str:
        """Generate response headers string"""
        header_str = ""
        extra = extra or {}
        for key, val in {**RESPONSE_HEADERS, **extra}.items():
            header_str += f"{key}: {val}\n"
        return header_str

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
        body = b""
        extra = {}
        data = response.get("data", {})
        if len(data) > 0:
            body = json.dumps(data).encode("utf-8")
            extra = JSON_MIME_HEADER.copy()
        headers = self.response_headers(extra=extra)
        status = response["code"]
        http_response = dialogue.reply(
            performative=HttpMessage.Performative.RESPONSE,
            target_message=message,
            version=message.version,
            status_code=status.value,
            status_text=status.message,
            headers=headers,
            body=body,
        )

        # Send response
        self.context.logger.info("Responding with: {}".format(http_response))
        self.context.outbox.put_message(message=http_response)

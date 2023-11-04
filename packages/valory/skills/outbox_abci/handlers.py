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

"""This module contains the handlers for the skill of OutboxAbciApp."""

import json
import re
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, Optional, Tuple, cast
from urllib.parse import urlparse

from aea.protocols.base import Message

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
from packages.valory.skills.outbox_abci.dialogues import (HttpDialogue,
                                                          HttpDialogues)
from packages.valory.skills.outbox_abci.models import SharedState
from packages.valory.skills.outbox_abci.rounds import SynchronizedData

ABCIRoundHandler = BaseABCIRoundHandler
SigningHandler = BaseSigningHandler
LedgerApiHandler = BaseLedgerApiHandler
ContractApiHandler = BaseContractApiHandler
TendermintHandler = BaseTendermintHandler
IpfsHandler = BaseIpfsHandler
HttpHandler = BaseHttpHandler

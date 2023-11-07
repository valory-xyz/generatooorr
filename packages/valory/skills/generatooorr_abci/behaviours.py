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

"""This package contains round behaviours of ContributionSkillAbci."""

from abc import ABC
from typing import Generator, Set, Type, cast

from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.generatooorr_abci.composition import GeneratooorrAbciApp
from packages.valory.skills.generatooorr_abci.tx_multiplexer import (
    SynchronizedData,
    TxMultiplexerRound,
    TxSettlementMultiplexerAbci,
)
from packages.valory.skills.inbox_abci.behaviours import InboxAbciRoundBehaviour
from packages.valory.skills.mech_interact_abci.behaviours.round_behaviour import (
    MechInteractRoundBehaviour,
)
from packages.valory.skills.nft_mint_abci.behaviours import NftMintAbciRoundBehaviour
from packages.valory.skills.outbox_abci.behaviours import OutboxAbciRoundBehaviour
from packages.valory.skills.registration_abci.behaviours import (
    AgentRegistrationRoundBehaviour,
    RegistrationStartupBehaviour,
)
from packages.valory.skills.reset_pause_abci.behaviours import (
    ResetPauseABCIConsensusBehaviour,
)
from packages.valory.skills.transaction_settlement_abci.behaviours import (
    TransactionSettlementRoundBehaviour,
)


class TxMultiplexerBehaviour(BaseBehaviour, ABC):
    """
    The post transaction settlement behaviour.

    This behaviour is executed after a tx is settled,
    via the transaction_settlement_abci.
    """

    matching_round = TxMultiplexerRound

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    def async_act(self) -> Generator:
        """Simply log that a tx is settled and wait for round end."""
        self.context.logger.info(
            f"The transaction submitted by {self.synchronized_data.tx_submitter} was successfully settled."
        )
        yield from self.wait_until_round_end()
        self.set_done()


class TxMultiplexerRoundBehaviour(AbstractRoundBehaviour):
    """The post tx settlement full behaviour."""

    initial_behaviour_cls = TxMultiplexerBehaviour
    abci_app_cls = TxSettlementMultiplexerAbci
    behaviours: Set[Type[BaseBehaviour]] = {
        TxMultiplexerBehaviour,
    }


class GeneratooorrConsensusBehaviour(AbstractRoundBehaviour):
    """Class to define the behaviours this AbciApp has."""

    initial_behaviour_cls = RegistrationStartupBehaviour
    abci_app_cls = GeneratooorrAbciApp
    behaviours: Set[Type[BaseBehaviour]] = {
        *AgentRegistrationRoundBehaviour.behaviours,
        *InboxAbciRoundBehaviour.behaviours,
        *MechInteractRoundBehaviour.behaviours,
        *TransactionSettlementRoundBehaviour.behaviours,
        *OutboxAbciRoundBehaviour.behaviours,
        *NftMintAbciRoundBehaviour.behaviours,
        *TxMultiplexerRoundBehaviour.behaviours,
        *ResetPauseABCIConsensusBehaviour.behaviours,
    }

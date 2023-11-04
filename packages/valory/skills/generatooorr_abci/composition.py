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

"""This package contains round behaviours of GeneratooorrAbciApp."""


import packages.valory.skills.inbox_abci.rounds as InboxAbci
import packages.valory.skills.mech_interact_abci.rounds as MechInteractAbci
import packages.valory.skills.mech_interact_abci.states.final_states as MechFinalStates
import packages.valory.skills.mech_interact_abci.states.request as MechRequestStates
import packages.valory.skills.mech_interact_abci.states.response as MechResponseStates
import packages.valory.skills.outbox_abci.rounds as OutboxAbci
import packages.valory.skills.registration_abci.rounds as RegistrationAbci
import packages.valory.skills.reset_pause_abci.rounds as ResetAndPauseAbci
import packages.valory.skills.transaction_settlement_abci.rounds as TxSettlementAbci
from packages.valory.skills.abstract_round_abci.abci_app_chain import (
    AbciAppTransitionMapping, chain)

abci_app_transition_mapping: AbciAppTransitionMapping = {
    RegistrationAbci.FinishedRegistrationRound: InboxAbci.WaitRound,
    InboxAbci.FinishedInboxWaitingRound: MechRequestStates.MechRequestRound,
    MechFinalStates.FinishedMechRequestRound: TxSettlementAbci.RandomnessTransactionSubmissionRound,
    TxSettlementAbci.FinishedTransactionSubmissionRound: MechResponseStates.MechResponseRound,
    TxSettlementAbci.FailedRound: MechRequestStates.MechRequestRound,
    MechFinalStates.FinishedMechResponseRound: OutboxAbci.PushNotificationRound,
    ResetAndPauseAbci.FinishedResetAndPauseRound: InboxAbci.WaitRound,
    ResetAndPauseAbci.FinishedResetAndPauseErrorRound: ResetAndPauseAbci.ResetAndPauseRound,
}


GeneratooorrAbciApp = chain(
    (
        RegistrationAbci.AgentRegistrationAbciApp,
        InboxAbci.InboxAbciApp,
        MechInteractAbci.MechInteractAbciApp,
        TxSettlementAbci.TransactionSubmissionAbciApp,
        OutboxAbci.OutboxAbciApp,
        ResetAndPauseAbci.ResetPauseAbciApp,
    ),
    abci_app_transition_mapping,
)

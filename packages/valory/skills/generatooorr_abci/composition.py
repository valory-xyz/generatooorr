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

"""This package contains round behaviours of GeneratooorrAbciApp."""


import packages.valory.skills.generatooorr_abci.tx_multiplexer as TxMultiplexerAbci
import packages.valory.skills.inbox_abci.rounds as InboxAbci
import packages.valory.skills.mech_interact_abci.rounds as MechInteractAbci
import packages.valory.skills.mech_interact_abci.states.final_states as MechFinalStates
import packages.valory.skills.mech_interact_abci.states.request as MechRequestStates
import packages.valory.skills.mech_interact_abci.states.response as MechResponseStates
import packages.valory.skills.nft_mint_abci.rounds as NftMintAbci
import packages.valory.skills.outbox_abci.rounds as OutboxAbci
import packages.valory.skills.registration_abci.rounds as RegistrationAbci
import packages.valory.skills.reset_pause_abci.rounds as ResetAndPauseAbci
import packages.valory.skills.transaction_settlement_abci.rounds as TxSettlementAbci
import packages.valory.skills.farcaster_write_abci.rounds as FarcasterWriteAbci
import packages.valory.skills.subscription_abci.rounds as SubscriptionAbci
from packages.valory.skills.abstract_round_abci.abci_app_chain import (
    AbciAppTransitionMapping,
    chain,
)
from packages.valory.skills.abstract_round_abci.base import BackgroundAppConfig
from packages.valory.skills.termination_abci.rounds import (
    BackgroundRound,
    Event,
    TerminationAbciApp,
)


abci_app_transition_mapping: AbciAppTransitionMapping = {
    RegistrationAbci.FinishedRegistrationRound: InboxAbci.WaitRound,
    InboxAbci.FinishedInboxWaitingRound: SubscriptionAbci.SubscriptionRound,
    InboxAbci.FinishedWithoutRequestRound: ResetAndPauseAbci.ResetAndPauseRound,
    SubscriptionAbci.FinishedSubscriptionRound: TxSettlementAbci.RandomnessTransactionSubmissionRound,
    SubscriptionAbci.FinishedWithoutSubscriptionRound: MechRequestStates.MechRequestRound,
    SubscriptionAbci.FinishedClaimingRound: MechRequestStates.MechRequestRound,
    TxMultiplexerAbci.FinishedSubscriptionTxRound: SubscriptionAbci.ClaimRound,
    TxMultiplexerAbci.FinishedWithFailedSubscriptionTxRound: SubscriptionAbci.SubscriptionRound,
    MechFinalStates.FinishedMechTxSubmitterRound: TxSettlementAbci.RandomnessTransactionSubmissionRound,
    TxMultiplexerAbci.FinishedMechTxRound: MechResponseStates.MechResponseRound,
    MechFinalStates.FinishedMechResponseRound: NftMintAbci.NftMintRound,
    NftMintAbci.FinishedNftMintRound: TxSettlementAbci.RandomnessTransactionSubmissionRound,
    NftMintAbci.FinishedWithErrorRound: ResetAndPauseAbci.ResetAndPauseRound,
    TxMultiplexerAbci.FinishedNFTMintTxRound: NftMintAbci.VerifyMintRound,
    TxSettlementAbci.FinishedTransactionSubmissionRound: TxMultiplexerAbci.TxMultiplexerRound,
    TxSettlementAbci.FailedRound: TxMultiplexerAbci.TxMultiplexerFailedRound,
    TxMultiplexerAbci.FinishedWithFailedMechTxRound: MechRequestStates.MechRequestRound,
    TxMultiplexerAbci.FinishedWithFailedNFTMintTxRound: NftMintAbci.NftMintRound,
    NftMintAbci.FinishedVerifyMintRound: OutboxAbci.PushNotificationRound,
    OutboxAbci.FinishedPushNotificationRound: FarcasterWriteAbci.RandomnessFarcasterRound,
    FarcasterWriteAbci.FinishedFarcasterWriteRound: ResetAndPauseAbci.ResetAndPauseRound,
    ResetAndPauseAbci.FinishedResetAndPauseRound: InboxAbci.WaitRound,
    ResetAndPauseAbci.FinishedResetAndPauseErrorRound: ResetAndPauseAbci.ResetAndPauseRound,
}

termination_config = BackgroundAppConfig(
    round_cls=BackgroundRound,
    start_event=Event.TERMINATE,
    abci_app=TerminationAbciApp,
)

GeneratooorrAbciApp = chain(
    (
        RegistrationAbci.AgentRegistrationAbciApp,
        InboxAbci.InboxAbciApp,
        MechInteractAbci.MechInteractAbciApp,
        TxSettlementAbci.TransactionSubmissionAbciApp,
        OutboxAbci.OutboxAbciApp,
        ResetAndPauseAbci.ResetPauseAbciApp,
        TxMultiplexerAbci.TxSettlementMultiplexerAbci,
        FarcasterWriteAbci.FarcasterWriteAbciApp,
        SubscriptionAbci.SubscriptionAbciApp,
        NftMintAbci.NftMintAbciApp,
    ),
    abci_app_transition_mapping,
).add_background_app(termination_config)

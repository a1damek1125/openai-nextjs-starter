"""Case lifecycle state machine — executable form of docs/finalis-ai/03.

The transition table below transcribes 03 §4 exactly, including the two global
edges (escalation interrupt, closure edge). A consistency test validates this
module against docs/finalis-ai/state-machine.finalis.json when that file exists.
"""
from __future__ import annotations

from enum import Enum


class CaseState(str, Enum):
    NEW_CONTACT = "NEW_CONTACT"
    INTAKE_IN_PROGRESS = "INTAKE_IN_PROGRESS"
    QUALIFIED = "QUALIFIED"
    WAITING_FOR_CLIENT_INFO = "WAITING_FOR_CLIENT_INFO"
    WAITING_FOR_DOCUMENTS = "WAITING_FOR_DOCUMENTS"
    DOCUMENT_ANALYSIS = "DOCUMENT_ANALYSIS"
    QUOTE_PREPARATION = "QUOTE_PREPARATION"
    OFFER_SENT = "OFFER_SENT"
    FOLLOW_UP_ACTIVE = "FOLLOW_UP_ACTIVE"
    NEGOTIATION = "NEGOTIATION"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    SCHEDULED = "SCHEDULED"
    WON = "WON"
    LOST = "LOST"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"
    RECOVERY_LATER = "RECOVERY_LATER"


TERMINAL_STATES = {CaseState.COMPLETED, CaseState.ABANDONED}
CLOSED_REOPENABLE_STATES = {CaseState.WON, CaseState.LOST}
PARKED_STATES = {CaseState.RECOVERY_LATER}
# FINAL states (case-graph spec): closure outcomes. Leaving any of them
# requires explicit human override — except the scheduled RECOVERY_LATER wake,
# which the Completion Loop performs with trigger=scheduled_wake.
FINAL_STATES = (TERMINAL_STATES | CLOSED_REOPENABLE_STATES | PARKED_STATES)
ACTIVE_STATES = set(CaseState) - FINAL_STATES

# docs/finalis-ai/03 §4 — explicit per-state transitions.
TRANSITIONS: dict[CaseState, set[CaseState]] = {
    CaseState.NEW_CONTACT: {
        CaseState.INTAKE_IN_PROGRESS,
        CaseState.SCHEDULED,
        CaseState.HUMAN_REVIEW_REQUIRED,
        CaseState.ABANDONED,
    },
    CaseState.INTAKE_IN_PROGRESS: {
        CaseState.QUALIFIED,
        CaseState.WAITING_FOR_CLIENT_INFO,
        CaseState.WAITING_FOR_DOCUMENTS,
        CaseState.HUMAN_REVIEW_REQUIRED,
        CaseState.ABANDONED,
    },
    CaseState.QUALIFIED: {
        CaseState.WAITING_FOR_DOCUMENTS,
        CaseState.WAITING_FOR_CLIENT_INFO,
        CaseState.QUOTE_PREPARATION,
        CaseState.SCHEDULED,
        CaseState.HUMAN_REVIEW_REQUIRED,
    },
    CaseState.WAITING_FOR_CLIENT_INFO: {
        CaseState.INTAKE_IN_PROGRESS,
        CaseState.QUALIFIED,
        CaseState.WAITING_FOR_DOCUMENTS,
        CaseState.FOLLOW_UP_ACTIVE,
        CaseState.RECOVERY_LATER,
        CaseState.ABANDONED,
        CaseState.HUMAN_REVIEW_REQUIRED,
    },
    CaseState.WAITING_FOR_DOCUMENTS: {
        CaseState.DOCUMENT_ANALYSIS,
        CaseState.FOLLOW_UP_ACTIVE,
        CaseState.RECOVERY_LATER,
        CaseState.ABANDONED,
        CaseState.HUMAN_REVIEW_REQUIRED,
    },
    CaseState.DOCUMENT_ANALYSIS: {
        CaseState.QUOTE_PREPARATION,
        CaseState.NEGOTIATION,
        CaseState.WAITING_FOR_DOCUMENTS,
        CaseState.HUMAN_REVIEW_REQUIRED,
    },
    CaseState.QUOTE_PREPARATION: {
        CaseState.OFFER_SENT,
        CaseState.WAITING_FOR_CLIENT_INFO,
        CaseState.HUMAN_REVIEW_REQUIRED,
    },
    CaseState.OFFER_SENT: {
        CaseState.FOLLOW_UP_ACTIVE,
        CaseState.NEGOTIATION,
        CaseState.WON,
        CaseState.LOST,
        CaseState.SCHEDULED,
        CaseState.RECOVERY_LATER,
    },
    CaseState.FOLLOW_UP_ACTIVE: {
        CaseState.NEGOTIATION,
        CaseState.OFFER_SENT,
        CaseState.WAITING_FOR_CLIENT_INFO,
        CaseState.WAITING_FOR_DOCUMENTS,
        CaseState.WON,
        CaseState.LOST,
        CaseState.SCHEDULED,
        CaseState.RECOVERY_LATER,
        CaseState.HUMAN_REVIEW_REQUIRED,
    },
    CaseState.NEGOTIATION: {
        CaseState.WON,
        CaseState.LOST,
        CaseState.OFFER_SENT,
        CaseState.FOLLOW_UP_ACTIVE,
        CaseState.RECOVERY_LATER,
        CaseState.HUMAN_REVIEW_REQUIRED,
    },
    # HUMAN_REVIEW_REQUIRED → any non-final state (per human decision) + all
    # final closure outcomes.
    CaseState.HUMAN_REVIEW_REQUIRED: (
        (ACTIVE_STATES - {CaseState.HUMAN_REVIEW_REQUIRED})
        | FINAL_STATES
    ),
    CaseState.SCHEDULED: {
        CaseState.COMPLETED,
        CaseState.WON,
        CaseState.DOCUMENT_ANALYSIS,
        CaseState.FOLLOW_UP_ACTIVE,
        CaseState.LOST,
    },
    CaseState.WON: {
        CaseState.SCHEDULED,
        CaseState.COMPLETED,
        CaseState.RECOVERY_LATER,
    },
    CaseState.LOST: {
        CaseState.RECOVERY_LATER,
        CaseState.ABANDONED,
    },
    CaseState.RECOVERY_LATER: {CaseState.FOLLOW_UP_ACTIVE},
    CaseState.COMPLETED: set(),
    CaseState.ABANDONED: set(),
}


class IllegalTransition(Exception):
    pass


def is_legal(
    from_state: CaseState,
    to_state: CaseState,
    *,
    escalation_interrupt: bool = False,
    hard_opt_out: bool = False,
    followup_exhausted: bool = False,
    human_override: bool = False,
    scheduled_wake: bool = False,
) -> bool:
    """True if the transition is allowed (03 §4 + case-graph final-state rule).

    Final-state rule: no FINAL state (WON/LOST/COMPLETED/ABANDONED/
    RECOVERY_LATER) may transition without explicit `human_override` — with
    one documented exception: the Completion Loop's scheduled wake
    RECOVERY_LATER → FOLLOW_UP_ACTIVE (`scheduled_wake=True`).
    """
    # Global interrupt edge: any active state → HUMAN_REVIEW_REQUIRED.
    if (
        escalation_interrupt
        and from_state in ACTIVE_STATES
        and to_state is CaseState.HUMAN_REVIEW_REQUIRED
    ):
        return True
    # Global closure edge: any non-terminal state → ABANDONED/LOST on hard
    # opt-out or follow-up exhaustion.
    if (
        (hard_opt_out or followup_exhausted)
        and from_state not in TERMINAL_STATES
        and to_state in {CaseState.ABANDONED, CaseState.LOST}
    ):
        return True
    if to_state not in TRANSITIONS[from_state]:
        return False
    if from_state in FINAL_STATES:
        wake_ok = (scheduled_wake
                   and from_state is CaseState.RECOVERY_LATER
                   and to_state is CaseState.FOLLOW_UP_ACTIVE)
        return human_override or wake_ok
    return True


def transition(case, to_state: CaseState, *, actor: str, reason: str,
               audit_log, escalation_interrupt: bool = False,
               hard_opt_out: bool = False,
               followup_exhausted: bool = False,
               human_override: bool = False,
               scheduled_wake: bool = False) -> None:
    """Apply a transition, enforcing 03 §2 invariants and writing an AuditEvent."""
    from_state = case.state
    if not is_legal(
        from_state,
        to_state,
        escalation_interrupt=escalation_interrupt,
        hard_opt_out=hard_opt_out,
        followup_exhausted=followup_exhausted,
        human_override=human_override,
        scheduled_wake=scheduled_wake,
    ):
        raise IllegalTransition(f"{from_state.value} -> {to_state.value}")

    case.state = to_state
    # Invariant 2: entering HUMAN_REVIEW_REQUIRED caps autonomy at Level 2.
    if to_state is CaseState.HUMAN_REVIEW_REQUIRED:
        case.autonomy_frozen_at = 2
    elif from_state is CaseState.HUMAN_REVIEW_REQUIRED:
        case.autonomy_frozen_at = None
    # Invariant 6: hard opt-out suppresses all future outbound permanently.
    if hard_opt_out:
        case.opted_out = True
    # Terminal/parked states drop the next action; active states must get one
    # from the completion loop immediately after (enforced by its invariant check).
    if to_state in TERMINAL_STATES | CLOSED_REOPENABLE_STATES:
        case.next_best_action = None
        case.next_action_due_at = None

    audit_log.append(
        event_type="case.state_changed",
        case_id=case.id,
        actor=actor,
        payload={
            "from_state": from_state.value,
            "to_state": to_state.value,
            "reason": reason,
        },
    )

"""Governed Work State Machine (SP0006 §13.1, D-0006-04). Deterministic, fail-
closed: an invalid transition is rejected; AMBIGUOUS/CONFLICTED cannot run;
EXPIRED/CANCELLED/SUPERSEDED/QUARANTINED cannot resume; OUTCOME_PRODUCED is not
VERIFIED_COMPLETE; PARTIALLY_VERIFIED retains unresolved predicates.
"""
from __future__ import annotations

from .model import (Finding, P1, INVALID_STATE_TRANSITION, WORK_STATES,
                    NON_EXECUTABLE_STATES, EXECUTABLE_STATES)

# allowed transitions (from -> {to}). Fail-closed: anything not listed is invalid.
TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"NORMALIZING", "EXPIRED", "SUPERSEDED", "CANCEL_REQUESTED"},
    "NORMALIZING": {"AMBIGUOUS", "CONFLICTED", "ADMITTED", "CANCEL_REQUESTED"},
    "AMBIGUOUS": {"NORMALIZING", "CANCEL_REQUESTED", "EXPIRED"},   # never RUNNING
    "CONFLICTED": {"NORMALIZING", "CANCEL_REQUESTED", "EXPIRED"},  # never RUNNING
    "ADMITTED": {"PLANNING", "CANCEL_REQUESTED", "EXPIRED", "SUPERSEDED"},
    "PLANNING": {"PLAN_READY", "AMBIGUOUS", "CONFLICTED", "CANCEL_REQUESTED"},
    "PLAN_READY": {"DELEGATION_READY", "PAUSED_FOR_DRIFT", "CANCEL_REQUESTED",
                   "SUPERSEDED"},
    "DELEGATION_READY": {"DELEGATED", "PAUSED_FOR_DRIFT", "CANCEL_REQUESTED"},
    "DELEGATED": {"SHADOW_EXECUTION", "RUNNING", "AWAITING_APPROVAL",
                  "PAUSED_FOR_DRIFT", "CANCEL_REQUESTED"},
    "SHADOW_EXECUTION": {"RUNNING", "AWAITING_APPROVAL", "PAUSED_FOR_DRIFT",
                         "COMMIT_READY", "CANCEL_REQUESTED", "FAILED"},
    "RUNNING": {"AWAITING_APPROVAL", "COMMIT_READY", "PAUSED_FOR_DRIFT",
                "OUTCOME_PRODUCED", "FAILED", "CANCEL_REQUESTED"},
    "PAUSED_FOR_DRIFT": {"RUNNING", "PLANNING", "CANCEL_REQUESTED",
                         "FAILED"},   # requires deterministic revalidation
    "AWAITING_APPROVAL": {"COMMIT_READY", "RUNNING", "PAUSED_FOR_DRIFT",
                          "FAILED", "CANCEL_REQUESTED"},
    "COMMIT_READY": {"OUTCOME_PRODUCED", "FAILED", "CANCEL_REQUESTED"},
    "OUTCOME_PRODUCED": {"OUTCOME_VERIFYING", "FAILED"},   # NOT verified yet
    "OUTCOME_VERIFYING": {"VERIFIED_COMPLETE", "PARTIALLY_VERIFIED", "FAILED"},
    "PARTIALLY_VERIFIED": {"OUTCOME_VERIFYING", "FAILED", "SUPERSEDED"},
    "VERIFIED_COMPLETE": {"SUPERSEDED"},   # may be superseded by a defeater rev
    "CANCEL_REQUESTED": {"CANCELLED"},     # only after the barrier completes
    "CANCELLED": set(),
    "EXPIRED": set(),
    "QUARANTINED": set(),                  # cannot self-release
    "SUPERSEDED": set(),
    "FAILED": {"SUPERSEDED"},
}


def valid_transition(src: str, dst: str) -> bool:
    return dst in TRANSITIONS.get(src, set())


def validate_transition(src: str, dst: str) -> list[Finding]:
    out: list[Finding] = []
    if src not in WORK_STATES:
        out.append(Finding(INVALID_STATE_TRANSITION, P1, src,
                           f"unknown source state {src!r}", {}))
        return out
    if dst not in WORK_STATES:
        out.append(Finding(INVALID_STATE_TRANSITION, P1, dst,
                           f"unknown target state {dst!r}", {}))
        return out
    if not valid_transition(src, dst):
        out.append(Finding(INVALID_STATE_TRANSITION, P1, f"{src}->{dst}",
                           f"forbidden transition {src} -> {dst} (fail-closed)",
                           {}))
    return out


def validate_run(states: list[str]) -> list[Finding]:
    """Validate a whole state trajectory; also enforce the never-run and never-
    resume rules explicitly."""
    out: list[Finding] = []
    for a, b in zip(states, states[1:]):
        out.extend(validate_transition(a, b))
        if a in NON_EXECUTABLE_STATES and b in EXECUTABLE_STATES:
            out.append(Finding(INVALID_STATE_TRANSITION, P1, f"{a}->{b}",
                               f"{a} cannot enter executable state {b}", {}))
    return out


def can_run(state: str) -> bool:
    return state not in NON_EXECUTABLE_STATES

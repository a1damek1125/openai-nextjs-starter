"""Cancellation Barrier + Quarantine + In-Flight / Unknown-Outcome Reconciliation
(SP0006 §9.11, §11.11, D-0006-52..55, INV-0006-33..36).

Cancellation is a BARRIER PROTOCOL, not an instantaneous stop. On CANCEL_REQUESTED
the barrier MUST, in order (D-0006-52): (1) block new actions, (2) identify
in-flight actions, (3) revoke eligible leases, (4) invalidate unused approvals,
(5) reconcile UNKNOWN outcomes, (6) record irreversible completed effects — only
THEN may the work reach CANCELLED. Cancellation cannot erase completed irreversible
effects (D-0006-53). An UNKNOWN outcome is distinct from a failure; blindly
retrying a non-idempotent effect is prohibited (D-0006-55, INV-0006-36). A
quarantine can never self-release (D-0006-54).
"""
from __future__ import annotations

from .model import (Finding, P1, CANCEL_BARRIER_STATES,
                    CANCELLATION_BARRIER_INCOMPLETE,
                    UNKNOWN_OUTCOME_RECONCILIATION_REQUIRED)

(_OPEN, _NEW_ACTIONS_BLOCKED, _LEASES_REVOKING, _IN_FLIGHT_RECONCILING,
 _SAFE_TERMINATION_CONFIRMED, _CLOSED) = CANCEL_BARRIER_STATES


def new_action_allowed(barrier_state: str) -> bool:
    """New actions are permitted only while the barrier is still OPEN; once
    NEW_ACTIONS_BLOCKED (or any later state) is reached, no new action may start
    (AC-0006-153, INV-0006-33)."""
    return barrier_state == _OPEN


def _classified(action: dict) -> bool:
    """An in-flight action is reconciled once its disposition is known."""
    disp = action.get("classification") or action.get("disposition")
    return bool(disp) and str(disp).upper() not in ("UNKNOWN", "PENDING", "")


def _reconciled(unknown: dict) -> bool:
    return bool(unknown.get("reconciled")) or \
        str(unknown.get("reconciliation_state", "")).upper() == "RECONCILED"


def run_barrier(state: dict) -> dict:
    """Walk the cancellation barrier states over the supplied surface. `can_cancel`
    becomes True only when the barrier reaches SAFE_TERMINATION_CONFIRMED with all
    unknown outcomes reconciled and all in-flight actions classified (D-0006-52)."""
    in_flight = list(state.get("in_flight", []) or [])
    leases = list(state.get("leases", []) or [])
    approvals = list(state.get("approvals", []) or [])
    unknowns = list(state.get("unknown_outcomes", []) or [])
    irreversible = list(state.get("irreversible_effects", []) or [])

    # (1) block new actions
    barrier_state = _NEW_ACTIONS_BLOCKED
    new_actions_blocked = True

    # (2) identify in-flight actions / (3) revoke eligible leases
    barrier_state = _LEASES_REVOKING
    revoked_leases = [l.get("lease_id") for l in leases
                      if l.get("revocable", True) and
                      str(l.get("revocation_state", "")).upper() != "REVOKED"]
    # (4) invalidate unused approvals
    invalidated_approvals = [a.get("approval_id") for a in approvals
                             if not a.get("consumed")]

    # (5) reconcile UNKNOWN outcomes / (6) record irreversible completed effects
    barrier_state = _IN_FLIGHT_RECONCILING
    reconciled_unknowns = [u.get("outcome_id") for u in unknowns
                           if _reconciled(u)]
    recorded_irreversible = [e.get("effect_id") for e in irreversible]

    all_unknowns_reconciled = all(_reconciled(u) for u in unknowns)
    all_in_flight_classified = all(_classified(a) for a in in_flight)

    can_cancel = all_unknowns_reconciled and all_in_flight_classified
    if can_cancel:
        barrier_state = _SAFE_TERMINATION_CONFIRMED

    return {
        "barrier_state": barrier_state,
        "new_actions_blocked": new_actions_blocked,
        "revoked_leases": revoked_leases,
        "invalidated_approvals": invalidated_approvals,
        "reconciled_unknowns": reconciled_unknowns,
        "recorded_irreversible": recorded_irreversible,
        "can_cancel": can_cancel,
    }


def barrier_findings(state: dict) -> list[Finding]:
    """Findings raised when a cancellation attempts to reach CANCELLED before the
    barrier has fully drained (D-0006-52). Attempting CANCELLED while any unknown
    outcome is unreconciled or any in-flight action is unclassified is a
    CANCELLATION_BARRIER_INCOMPLETE (P1); each unreconciled unknown additionally
    raises UNKNOWN_OUTCOME_RECONCILIATION_REQUIRED (P1)."""
    out: list[Finding] = []
    subject = state.get("work_order_id", "-")
    unknowns = list(state.get("unknown_outcomes", []) or [])
    in_flight = list(state.get("in_flight", []) or [])

    unreconciled = [u for u in unknowns if not _reconciled(u)]
    unclassified = [a for a in in_flight if not _classified(a)]

    if unreconciled or unclassified:
        out.append(Finding(
            CANCELLATION_BARRIER_INCOMPLETE, P1, subject,
            "cancellation cannot complete: "
            f"{len(unreconciled)} unreconciled unknown outcome(s), "
            f"{len(unclassified)} unclassified in-flight action(s) (D-0006-52)",
            {"unreconciled_unknowns": [u.get("outcome_id") for u in unreconciled],
             "unclassified_in_flight": [a.get("action_id") for a in unclassified]}))

    for u in unreconciled:
        out.append(Finding(
            UNKNOWN_OUTCOME_RECONCILIATION_REQUIRED, P1,
            u.get("outcome_id", subject),
            "unknown outcome must be reconciled before cancellation completes "
            "(INV-0006-35)", {"outcome_id": u.get("outcome_id")}))
    return out


def quarantine_release_allowed(q: dict) -> bool:
    """A quarantine can never self-release (D-0006-54). Release requires an
    authorized independent release decision whose approver is distinct from the
    quarantined subject and from whoever requested/imposed the quarantine
    (AC-0006-159)."""
    decision = q.get("independent_release_decision")
    if not isinstance(decision, dict):
        return False
    if not decision.get("authorized"):
        return False
    approver = decision.get("approver") or decision.get("approver_id")
    if not approver:
        return False
    forbidden = {q.get("subject"), q.get("subject_id"),
                 q.get("quarantined_identity"), q.get("requested_by"),
                 q.get("imposed_by")}
    return approver not in forbidden


def unknown_outcome_findings(unknowns: list[dict]) -> list[Finding]:
    """An UNKNOWN outcome is distinct from a failure (INV-0006-36). Blindly
    retrying a NON-IDEMPOTENT effect whose outcome is unknown is prohibited: it
    must be reconciled first (D-0006-55)."""
    out: list[Finding] = []
    for u in unknowns or []:
        oid = u.get("outcome_id", "-")
        if u.get("effect_idempotent") is False and u.get("retry_requested"):
            out.append(Finding(
                UNKNOWN_OUTCOME_RECONCILIATION_REQUIRED, P1, oid,
                "blind retry of a non-idempotent effect with an unknown outcome "
                "is prohibited; reconcile before retry (D-0006-55, INV-0006-36)",
                {"outcome_id": oid, "effect_idempotent": False,
                 "retry_requested": True}))
    return out

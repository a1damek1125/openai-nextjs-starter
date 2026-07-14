"""Dashboard semantics for the lifecycle vector — business language only.

Never show "won" as finished while money or delivery is open.
"""
from __future__ import annotations

from .completion import CaseFacts, can_complete
from .playbooks import VerticalPlaybook
from .vector import LifecycleVector, SupportState, TransactionState


def lifecycle_alerts(cases: list[tuple[str, CaseFacts, VerticalPlaybook]]
                     ) -> list[dict]:
    """[(case_id, facts, playbook)] → dashboard rows with plain-language
    status + why-blocked + what-next. Sorted: money first."""
    rows = []
    for case_id, facts, pb in cases:
        v = facts.vector
        view = v.derived_outcome_view()
        entry = {"case_id": case_id, "view": view,
                 "message": v.business_language(),
                 "blocked_reasons": [], "next_best_action": None,
                 "priority": 3}
        if view in ("WON_NOT_FULFILLED", "WON_PAID_NOT_DELIVERED"):
            check = can_complete(facts, pb)
            entry["blocked_reasons"] = check.blocked_reasons
            entry["next_best_action"] = check.next_best_action
            entry["priority"] = 1 if v.transaction in (
                TransactionState.PAYMENT_OVERDUE,
                TransactionState.PAYMENT_FAILED) else 2
        if v.support is SupportState.COMPLAINT_OPEN:
            entry["upsell_blocked"] = True
            entry["message"] += " Upsell blocked by open complaint."
        rows.append(entry)
    rows.sort(key=lambda r: r["priority"])
    return rows

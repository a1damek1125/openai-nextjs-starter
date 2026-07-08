"""The formal completion rule + hard blockers + active-case invariant.

can_complete() is code, not prose: every condition returns its own blocked
reason and a next best action, and hard blockers override every score.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .outcomes import Outcome, validate_outcome
from .playbooks import VerticalPlaybook
from .vector import (DEAL_POSITIVE, FULFILLED_STATES, PAID_STATES,
                     FulfillmentState, LifecycleVector, SupportState,
                     TransactionState)


@dataclass
class CaseFacts:
    """Everything the completion rule needs, explicit and testable."""
    vector: LifecycleVector
    missing_hard_required: list[str] = field(default_factory=list)
    missing_blocking_items: list[str] = field(default_factory=list)
    documents_missing: list[str] = field(default_factory=list)
    documents_waived: bool = False
    pending_high_risk_approvals: int = 0
    closure_evidence_id: Optional[str] = None
    contract_signed: bool = False
    completion_confirmed: bool = False


@dataclass
class CompletionCheck:
    ok: bool
    blocked_reasons: list[str]
    missing_conditions: list[str]
    next_best_action: Optional[str]


HARD_BLOCKERS = [
    ("opted_out", lambda f: f.vector.opted_out,
     "client opted out — no automatic action"),
    ("consent_missing", lambda f: not f.vector.consent_valid,
     "mandatory consent missing"),
    ("complaint_open", lambda f:
     f.vector.support is SupportState.COMPLAINT_OPEN,
     "unresolved complaint blocks closure"),
    ("high_risk_approval_pending", lambda f:
     f.pending_high_risk_approvals > 0,
     "high-risk human approval pending"),
    ("hard_required_missing", lambda f: bool(f.missing_hard_required),
     "hard-required information missing"),
]


def hard_blockers(facts: CaseFacts) -> list[str]:
    return [msg for _n, pred, msg in HARD_BLOCKERS if pred(facts)]


def can_complete(facts: CaseFacts, pb: VerticalPlaybook) -> CompletionCheck:
    """A case may become WON_COMPLETED only if EVERY condition holds."""
    blocked: list[str] = []
    missing: list[str] = []
    nba: Optional[str] = None
    v = facts.vector

    # Hard blockers first — they override everything.
    hb = hard_blockers(facts)
    if hb:
        blocked.extend(hb)
        nba = "request_human_review" if \
            facts.pending_high_risk_approvals else "resolve_blocker"

    # 1. Deal must be positive.
    if v.deal not in DEAL_POSITIVE:
        blocked.append("deal not accepted/won")
        missing.append("deal_state in {ACCEPTED_BY_CLIENT, WON}")
        nba = nba or "progress_deal"
    # 2/3. Information + documents.
    if facts.missing_blocking_items:
        blocked.append("blocking missing items open: "
                       + ", ".join(facts.missing_blocking_items))
        missing.append("resolve blocking missing items")
        nba = nba or "ask_for_missing_info"
    if facts.documents_missing and not facts.documents_waived:
        blocked.append("required documents missing: "
                       + ", ".join(facts.documents_missing))
        missing.append("attach or waive required documents")
        nba = nba or "send_document_request"
    # 4/5. Invoice + payment.
    if pb.invoice_required and v.transaction in (
            TransactionState.INVOICE_REQUIRED,
            TransactionState.INVOICE_DRAFTED):
        blocked.append("invoice not issued")
        missing.append("issue invoice (human approval)")
        nba = nba or "request_invoice_issue_approval"
    if pb.payment_required and v.transaction not in PAID_STATES:
        blocked.append(f"payment not settled ({v.transaction.value})")
        missing.append("payment PAID or WAIVED_BY_HUMAN")
        nba = nba or ("retry_payment" if v.transaction is
                      TransactionState.PAYMENT_FAILED else "await_payment")
    # 6. Fulfillment.
    if pb.fulfillment_required and v.fulfillment not in FULFILLED_STATES:
        blocked.append(f"fulfillment not completed "
                       f"({v.fulfillment.value})")
        missing.append("fulfillment COMPLETED/DELIVERED")
        nba = nba or ("schedule_fulfillment" if v.fulfillment is
                      FulfillmentState.REQUIRED else "progress_fulfillment")
    # Playbook extras.
    if pb.contract_required and not facts.contract_signed:
        blocked.append("signed contract required")
        missing.append("contract signed")
        nba = nba or "request_contract_signature"
    if pb.completion_confirmation_required and not facts.completion_confirmed:
        blocked.append("completion confirmation required")
        missing.append("customer/tenant confirmation")
        nba = nba or "request_completion_confirmation"
    # 10. Evidence.
    if facts.closure_evidence_id is None:
        blocked.append("closure evidence missing")
        missing.append("evidence bundle for closure")
        nba = nba or "attach_closure_evidence"

    return CompletionCheck(ok=not blocked, blocked_reasons=blocked,
                           missing_conditions=missing,
                           next_best_action=None if not blocked else nba)


# --- Active-case invariant ---------------------------------------------------
@dataclass
class ActiveCaseStatus:
    next_action: Optional[str] = None
    blocked_reason: Optional[str] = None
    waiting_condition: Optional[str] = None
    human_review_required: bool = False


def active_case_invariant(status: ActiveCaseStatus) -> bool:
    """No active case may silently sit with nothing to do and no reason."""
    return bool(status.next_action or status.blocked_reason
                or status.waiting_condition or status.human_review_required)


def close_case(facts: CaseFacts, pb: VerticalPlaybook,
               outcome: Outcome, audit) -> str:
    """Close with full validation: outcome invariant + (for completion) the
    formal rule. Returns the derived view. Writes audit events."""
    validate_outcome(outcome)
    if outcome.outcome_type in ("WON", "COMPLETED"):
        check = can_complete(facts, pb)
        if outcome.outcome_type == "COMPLETED" and not check.ok:
            audit.append(event_type="CASE_COMPLETION_BLOCKED", actor="system",
                         payload={"reasons": check.blocked_reasons,
                                  "next_best_action": check.next_best_action,
                                  "playbook_version": pb.version})
            raise ValueError("completion blocked: "
                             + "; ".join(check.blocked_reasons))
    view = facts.vector.derived_outcome_view() or outcome.outcome_type
    audit.append(event_type="OUTCOME_REASON_SET", actor=outcome.decided_by,
                 payload={"outcome_type": outcome.outcome_type,
                          "reason": outcome.outcome_reason,
                          "category": outcome.outcome_reason_category,
                          "evidence": outcome.evidence_reference_id,
                          "view": view, "playbook_version": pb.version})
    return view

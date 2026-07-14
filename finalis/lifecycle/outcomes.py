"""Outcome model + reason taxonomies + the no-silent-closure invariant."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

OUTCOME_TYPES = {"WON", "LOST", "COMPLETED", "CANCELLED", "DISQUALIFIED",
                 "ABANDONED", "RECOVERY_LATER", "DUPLICATE", "SPAM", "TEST",
                 "INVALID_REQUEST"}

REASON_TAXONOMY: dict[str, set[str]] = {
    "WON": {"client_accepted_offer", "invoice_paid", "contract_signed",
            "deposit_paid", "service_scheduled", "human_confirmed_win",
            "purchase_completed", "renewal_completed", "upsell_accepted",
            "cross_sell_accepted"},
    "LOST": {"price_too_high", "competitor_chosen", "no_budget",
             "timing_not_right", "no_response", "client_changed_mind",
             "service_not_available", "outside_service_area",
             "product_unavailable", "trust_issue", "slow_response",
             "offer_unclear", "scope_mismatch", "missing_documents",
             "client_refused_required_information",
             "internal_capacity_issue", "legal_compliance_blocker",
             "duplicate_inquiry", "spam_test_inquiry", "unknown_reason"},
    "CANCELLED": {"client_cancelled_after_acceptance", "payment_failed",
                  "supplier_unavailable", "service_not_deliverable",
                  "technical_infeasibility", "mutual_cancellation",
                  "human_override"},
    "DISQUALIFIED": {"not_target_industry", "not_target_location",
                     "too_low_value", "impossible_request",
                     "illegal_unsafe_request", "missing_mandatory_data",
                     "outside_company_services"},
    "RECOVERY_LATER": {"timing_later", "client_needs_budget",
                       "client_comparing_offers", "project_postponed",
                       "seasonal_opportunity", "contact_later_requested"},
    "ABANDONED": {"no_response", "unreachable", "client_went_silent"},
}

# Outcomes that MUST carry a reason — no silent closure, ever.
REASON_REQUIRED = {"LOST", "CANCELLED", "DISQUALIFIED", "ABANDONED",
                   "RECOVERY_LATER"}


class OutcomeValidationError(Exception):
    pass


@dataclass
class Outcome:
    outcome_type: str
    outcome_reason: Optional[str] = None
    outcome_reason_category: Optional[str] = None
    evidence_reference_id: Optional[str] = None
    human_override: bool = False
    decided_by: str = "system"
    decided_at: Optional[str] = None
    confidence: float = 1.0
    reversible: bool = False
    recovery_eligible: bool = False
    next_customer_lifecycle_action: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


def validate_outcome(outcome: Outcome) -> None:
    """The outcome-reason invariant. Raises on any silent closure."""
    if outcome.outcome_type not in OUTCOME_TYPES:
        raise OutcomeValidationError(
            f"unknown outcome type {outcome.outcome_type}")
    if outcome.outcome_type in REASON_REQUIRED:
        if not outcome.outcome_reason:
            raise OutcomeValidationError(
                f"{outcome.outcome_type} requires outcome_reason")
        if not outcome.outcome_reason_category:
            raise OutcomeValidationError(
                f"{outcome.outcome_type} requires outcome_reason_category")
        taxonomy = REASON_TAXONOMY.get(outcome.outcome_type, set())
        if outcome.outcome_reason not in taxonomy:
            raise OutcomeValidationError(
                f"reason '{outcome.outcome_reason}' not in the "
                f"{outcome.outcome_type} taxonomy")
        if outcome.evidence_reference_id is None \
                and not outcome.human_override:
            raise OutcomeValidationError(
                f"{outcome.outcome_type} requires evidence_reference "
                "or human_override")


def outcome_reason_confidence(*, evidence_quality: float,
                              source_reliability: float,
                              explicitness: float, recency: float,
                              consistency: float) -> float:
    """Multiplicative confidence in [0,1]; low => reason_candidate only."""
    def c(x: float) -> float:
        return max(0.0, min(1.0, x))
    return (c(evidence_quality) * c(source_reliability) * c(explicitness)
            * c(recency) * c(consistency))

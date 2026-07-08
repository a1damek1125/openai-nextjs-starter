"""Decision tables (DMN-style) + lifecycle scoring models.

Every table has a complete rule set for the important combinations and the
safe default fallback: REQUIRE_HUMAN_REVIEW. Ambiguity never auto-executes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .playbooks import VerticalPlaybook
from .vector import (LifecycleVector, SupportState, TransactionState)

ALLOW = "ALLOW"
BLOCK = "BLOCK"
REQUIRE_HUMAN_REVIEW = "REQUIRE_HUMAN_REVIEW"


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# --- Decision tables ------------------------------------------------------------
def can_ai_send(action: str, pb: VerticalPlaybook,
                vector: LifecycleVector) -> str:
    if vector.opted_out or not vector.consent_valid:
        return BLOCK
    if action in pb.prohibited_ai_actions:
        return BLOCK
    if action in pb.allowed_ai_actions:
        return ALLOW
    return REQUIRE_HUMAN_REVIEW          # unknown action → safe default


def requires_human_approval(decision_type: str, pb: VerticalPlaybook,
                            *, high_value: bool = False,
                            low_confidence: bool = False,
                            angry_client: bool = False) -> bool:
    if decision_type in pb.human_approval_rules:
        return True
    if low_confidence or angry_client:
        return True
    if decision_type == "close_lost" and high_value:
        return True
    return False


def upsell_allowed(vector: LifecycleVector, pb: VerticalPlaybook,
                   *, days_since_completion: float,
                   consent: bool = True) -> str:
    rules = pb.upsell_rules
    if vector.opted_out or not consent:
        return BLOCK
    if rules.get("blocked_by_complaint") and \
            vector.support is SupportState.COMPLAINT_OPEN:
        return BLOCK
    if rules.get("blocked_by_overdue_payment") and \
            vector.transaction is TransactionState.PAYMENT_OVERDUE:
        return BLOCK
    if not vector.fulfillment_settled():
        return BLOCK                     # never upsell before value delivered
    if days_since_completion < rules.get("cooldown_days", 14):
        return BLOCK
    if rules.get("high_value_requires_human"):
        return REQUIRE_HUMAN_REVIEW      # human signs off; AI proposes
    return ALLOW


def recovery_eligible(outcome_reason: str, pb: VerticalPlaybook,
                      vector: LifecycleVector, *,
                      angry_client: bool = False,
                      explicit_refusal: bool = False) -> bool:
    if vector.opted_out or not vector.consent_valid:
        return False
    if angry_client or explicit_refusal:
        return False
    return outcome_reason in pb.recovery_rules.get("eligible_reasons", [])


def followup_allowed(vector: LifecycleVector, *, attempts: int,
                     max_attempts: int) -> str:
    if vector.opted_out:
        return BLOCK
    if attempts >= max_attempts:
        return BLOCK
    return ALLOW


def outcome_reason_required(outcome_type: str) -> bool:
    from .outcomes import REASON_REQUIRED
    return outcome_type in REASON_REQUIRED


# --- Scoring models ----------------------------------------------------------------
def case_readiness_score(missing: list[tuple[float, bool]]) -> float:
    """1 − min(1, Σ wᵢ·mᵢ). `missing` = [(weight, is_missing)]."""
    burden = min(1.0, sum(w for w, m in missing if m))
    return _clamp(1.0 - burden)


def deal_win_probability(*, stage_base: float, responsiveness: float = 0,
                         completeness: float = 0, fit: float = 0,
                         urgency: float = 0, price_objection: float = 0,
                         no_response: float = 0, risk: float = 0) -> float:
    """HEURISTIC estimate (not a trained prediction — say so in any UI)."""
    return _clamp(stage_base + 0.1 * responsiveness + 0.1 * completeness
                  + 0.05 * fit + 0.05 * urgency - 0.15 * price_objection
                  - 0.15 * no_response - 0.1 * risk)


def expected_deal_value(p_win: float, deal_value: float,
                        gross_margin_factor: Optional[float] = None
                        ) -> tuple[float, bool]:
    """Returns (value, margin_is_assumption)."""
    assumed = gross_margin_factor is None
    return (_clamp(p_win) * max(0.0, deal_value)
            * (1.0 if assumed else gross_margin_factor), assumed)


def recovery_score(*, deal_value_score: float, service_fit: float,
                   positive_relationship: float, timing_later: float,
                   prior_engagement: float, margin_potential: float,
                   strategic_value: float, explicit_refusal: bool = False,
                   opted_out: bool = False,
                   angry_client: bool = False) -> float:
    if opted_out:
        return 0.0
    score = (0.25 * _clamp(deal_value_score) + 0.20 * _clamp(service_fit)
             + 0.15 * _clamp(positive_relationship)
             + 0.15 * _clamp(timing_later)
             + 0.10 * _clamp(prior_engagement)
             + 0.10 * _clamp(margin_potential)
             + 0.05 * _clamp(strategic_value))
    if explicit_refusal:
        score -= 0.5
    if angry_client:
        score -= 0.5
    return _clamp(score)


def upsell_score(*, need_fit: float, satisfaction: float,
                 product_adjacency: float, timing_fit: float,
                 clv_score: float, response_propensity: float,
                 margin_potential: float, complaint_open: bool = False,
                 payment_overdue: bool = False,
                 annoyance_risk: float = 0.0) -> float:
    if complaint_open or payment_overdue:
        return 0.0                        # hard blockers, not penalties
    score = (0.25 * _clamp(need_fit) + 0.20 * _clamp(satisfaction)
             + 0.15 * _clamp(product_adjacency) + 0.15 * _clamp(timing_fit)
             + 0.10 * _clamp(clv_score)
             + 0.10 * _clamp(response_propensity)
             + 0.05 * _clamp(margin_potential) - _clamp(annoyance_risk))
    return _clamp(score)


def clv_placeholder(*, average_order_value: Optional[float],
                    purchase_frequency_per_year: Optional[float],
                    gross_margin: Optional[float],
                    expected_retention_years: Optional[float],
                    service_cost: float = 0.0) -> tuple[float, str]:
    """Returns (clv, confidence_label). Partial data → low confidence."""
    inputs = [average_order_value, purchase_frequency_per_year,
              gross_margin, expected_retention_years]
    known = [x for x in inputs if x is not None]
    if len(known) < 4:
        partial = 1.0
        for x in known:
            partial *= x
        return (max(0.0, partial - service_cost), "low")
    clv = (average_order_value * purchase_frequency_per_year
           * gross_margin * expected_retention_years - service_cost)
    return (max(0.0, clv), "medium")


def churn_risk(*, days_since_positive: float, complaint: float,
               no_response: float, payment_issue: float,
               low_satisfaction: float, competitor: float,
               declining_engagement: float) -> float:
    days_score = _clamp(days_since_positive / 180.0)
    return _clamp(0.25 * days_score + 0.20 * _clamp(complaint)
                  + 0.15 * _clamp(no_response)
                  + 0.15 * _clamp(payment_issue)
                  + 0.10 * _clamp(low_satisfaction)
                  + 0.10 * _clamp(competitor)
                  + 0.05 * _clamp(declining_engagement))

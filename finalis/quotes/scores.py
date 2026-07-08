"""Quote scores — clamped 0..1, weights per the Q-A specification.

Scores inform gates and auto-send thresholds; they NEVER override hard
blockers (enforced in gates.py and engine.py, tested).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


@dataclass
class QuoteThresholds:
    """Tenant-configurable knobs. Defaults are conservative."""
    target_margin: Decimal = Decimal("0.35")
    margin_floor: Decimal = Decimal("0.10")        # absolute floor
    max_auto_discount: Decimal = Decimal("200")    # per-unit, currency
    cumulative_discount_cap: Decimal = Decimal("0.15")   # of subtotal
    high_value_threshold: Decimal = Decimal("20000")
    risk_review_threshold: float = 0.60
    min_price_confidence: float = 0.60
    min_evidence_coverage: float = 0.60
    min_clarity: float = 0.60
    volatility_review_threshold: float = 0.70
    base_valid_days: int = 30
    volatile_valid_days: int = 7
    cost_stale_after_days: int = 90


def quote_risk_score(*, low_margin_risk: float, evidence_gap_risk: float,
                     delivery_risk: float, legal_terms_risk: float,
                     tax_risk: float, customer_complaint_risk: float,
                     scope_ambiguity_risk: float, expiration_risk: float,
                     price_override_risk: float) -> float:
    return _clamp(0.20 * _clamp(low_margin_risk)
                  + 0.15 * _clamp(evidence_gap_risk)
                  + 0.15 * _clamp(delivery_risk)
                  + 0.10 * _clamp(legal_terms_risk)
                  + 0.10 * _clamp(tax_risk)
                  + 0.10 * _clamp(customer_complaint_risk)
                  + 0.10 * _clamp(scope_ambiguity_risk)
                  + 0.05 * _clamp(expiration_risk)
                  + 0.05 * _clamp(price_override_risk))


def price_confidence_score(*, price_book_coverage: float,
                           cost_known_coverage: float,
                           similar_case_evidence: float,
                           scope_certainty: float,
                           labor_estimate_confidence: float,
                           material_estimate_confidence: float,
                           tax_rule_confidence: float) -> float:
    return _clamp(0.25 * _clamp(price_book_coverage)
                  + 0.20 * _clamp(cost_known_coverage)
                  + 0.15 * _clamp(similar_case_evidence)
                  + 0.15 * _clamp(scope_certainty)
                  + 0.10 * _clamp(labor_estimate_confidence)
                  + 0.10 * _clamp(material_estimate_confidence)
                  + 0.05 * _clamp(tax_rule_confidence))


def evidence_coverage_score(*, required_facts_covered: float,
                            source_reliability: float,
                            evidence_recency: float,
                            scope_consistency: float,
                            human_verified_facts: float,
                            pricing_data_coverage: float) -> float:
    return _clamp(0.30 * _clamp(required_facts_covered)
                  + 0.20 * _clamp(source_reliability)
                  + 0.15 * _clamp(evidence_recency)
                  + 0.15 * _clamp(scope_consistency)
                  + 0.10 * _clamp(human_verified_facts)
                  + 0.10 * _clamp(pricing_data_coverage))


def quote_clarity_score(*, scope_clarity: float, price_clarity: float,
                        terms_clarity: float, exclusions_clarity: float,
                        payment_clarity: float, timeline_clarity: float,
                        acceptance_instructions_clarity: float) -> float:
    return _clamp(0.25 * _clamp(scope_clarity)
                  + 0.20 * _clamp(price_clarity)
                  + 0.15 * _clamp(terms_clarity)
                  + 0.15 * _clamp(exclusions_clarity)
                  + 0.10 * _clamp(payment_clarity)
                  + 0.10 * _clamp(timeline_clarity)
                  + 0.05 * _clamp(acceptance_instructions_clarity))


def cost_freshness(age_days: int, *, stale_after_days: int = 90) -> float:
    """1.0 when fresh, decaying linearly to 0 at 2× the stale horizon.
    Feeds cost_known_coverage so stale costs reduce price confidence."""
    if age_days <= 0:
        return 1.0
    return _clamp(1.0 - age_days / (2.0 * stale_after_days))

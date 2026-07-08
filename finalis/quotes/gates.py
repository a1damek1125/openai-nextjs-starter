"""Quote safety gates. Hard blockers always win — no score can unblock.

Each gate returns a GateResult with machine decision + human-readable
reasons (business language, dashboard-ready).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from .models import Quote, ZERO
from .scores import QuoteThresholds


@dataclass
class GateResult:
    decision: str
    reasons: list[str] = field(default_factory=list)
    hard_blockers: list[str] = field(default_factory=list)


# --- 1. QuoteReadinessGate ---------------------------------------------------------
READINESS_DECISIONS = {"READY", "NEEDS_MORE_INFO", "REQUIRE_HUMAN_REVIEW",
                       "BLOCKED"}


def quote_readiness_gate(quote: Quote, *,
                         required_scope_facts_missing: int = 0,
                         unresolved_complaint: bool = False,
                         client_opted_out_of_offers: bool = False,
                         has_price_book_or_rules: bool = True
                         ) -> GateResult:
    hard: list[str] = []
    if not quote.case_id:
        hard.append("quote has no case")
    if not quote.customer_party_id:
        hard.append("quote has no customer contact")
    if unresolved_complaint:
        hard.append("customer has an unresolved complaint — resolve first")
    if client_opted_out_of_offers:
        hard.append("client opted out of offer communication (non-overrideable)")
    if not quote.line_items:
        hard.append("no priceable item or service on the quote")
    if not quote.currency:
        hard.append("quote has no currency")
    if not has_price_book_or_rules:
        hard.append("no price book or pricing rule configured for tenant")
    if quote.custom_terms_text and not quote.terms_template_approved:
        hard.append("custom legal/warranty terms without an approved template")
    if hard:
        return GateResult("BLOCKED", hard, hard)
    if required_scope_facts_missing > 0:
        return GateResult("NEEDS_MORE_INFO",
                          [f"{required_scope_facts_missing} required scope "
                           "facts still missing"])
    if any(li.requires_human_review for li in quote.line_items):
        return GateResult("REQUIRE_HUMAN_REVIEW",
                          ["a line item needs human review before sending"])
    return GateResult("READY", ["all readiness checks passed"])


# --- 2. MarginSafetyGate --------------------------------------------------------------
MARGIN_DECISIONS = {"SAFE", "REQUIRE_APPROVAL", "BLOCKED"}


def margin_safety_gate(quote: Quote, thresholds: QuoteThresholds
                       ) -> GateResult:
    reasons: list[str] = []
    hard: list[str] = []
    needs_approval = False
    for li in quote.line_items:
        label = li.description or li.sku or li.id[:8]
        if li.mandatory and not li.cost_known:
            reasons.append(f"'{label}': cost is unknown on a mandatory "
                           "line — human review required")
            needs_approval = True
            continue
        if li.is_free_item:
            reasons.append(f"'{label}': free item — approval required")
            needs_approval = True
            continue
        m = li.margin_percent
        if m is None:
            reasons.append(f"'{label}': margin undefined (zero price) — "
                           "human review required")
            needs_approval = True
        elif m < ZERO:
            hard.append(f"'{label}': would be sold below cost "
                        f"(margin {m:.1%})")
        elif m < thresholds.margin_floor:
            hard.append(f"'{label}': margin {m:.1%} is under the "
                        f"{thresholds.margin_floor:.0%} floor")
        elif m < thresholds.target_margin:
            reasons.append(f"'{label}': margin {m:.1%} is below the "
                           f"{thresholds.target_margin:.0%} target — "
                           "approval required")
            needs_approval = True
        if li.manual_price is not None and m is not None \
                and m < thresholds.target_margin:
            reasons.append(f"'{label}': manual price below target margin — "
                           "approval required")
            needs_approval = True
    if hard:
        return GateResult("BLOCKED", hard + reasons, hard)
    if needs_approval:
        return GateResult("REQUIRE_APPROVAL", reasons)
    return GateResult("SAFE", ["all margins at or above target"])


# --- 3. DiscountApprovalGate ---------------------------------------------------------
def discount_approval_gate(quote: Quote, thresholds: QuoteThresholds
                           ) -> GateResult:
    reasons: list[str] = []
    for li in quote.line_items:
        label = li.description or li.sku or li.id[:8]
        if li.requested_discount > thresholds.max_auto_discount:
            reasons.append(f"'{label}': discount {li.requested_discount} "
                           "exceeds the auto-approval threshold")
        if li.is_free_item:
            reasons.append(f"'{label}': free item added")
        if li.requested_discount > ZERO and not li.discount_reason.strip():
            reasons.append(f"'{label}': discount has no reason recorded")
        m = li.margin_percent
        if li.applied_discount > ZERO and m is not None \
                and m < thresholds.target_margin:
            reasons.append(f"'{label}': discount takes margin below target")
    if quote.subtotal > ZERO:
        cum = sum((li.applied_discount * li.quantity
                   for li in quote.line_items), ZERO)
        if cum / (quote.subtotal + cum) > thresholds.cumulative_discount_cap:
            reasons.append("cumulative discount across the quote is high")
    if quote.total > thresholds.high_value_threshold \
            and any(li.applied_discount > ZERO for li in quote.line_items):
        reasons.append("high-value quote with discount — approval required")
    if reasons:
        return GateResult("REQUIRE_APPROVAL", reasons)
    return GateResult("SAFE", ["no discount approval needed"])


# --- 4. FulfillmentFeasibilityGate ------------------------------------------------
FEASIBILITY_DECISIONS = {"FEASIBLE", "FEASIBLE_WITH_RISK",
                         "REQUIRE_HUMAN_REVIEW", "BLOCKED"}


def fulfillment_feasibility_gate(*, delivery_window_possible: bool,
                                 resource_available: bool,
                                 material_availability_known: bool,
                                 service_area_supported: bool,
                                 calendar_load: float = 0.0) -> GateResult:
    hard: list[str] = []
    if not service_area_supported:
        hard.append("address is outside the supported service area")
    if not delivery_window_possible:
        hard.append("promised delivery window is not possible")
    if hard:
        return GateResult("BLOCKED", hard, hard)
    if not material_availability_known:
        return GateResult("REQUIRE_HUMAN_REVIEW",
                          ["material availability is unknown — confirm "
                           "before promising a date"])
    if not resource_available:
        return GateResult("REQUIRE_HUMAN_REVIEW",
                          ["no technician/resource available in the window"])
    if calendar_load > 0.8:
        return GateResult("FEASIBLE_WITH_RISK",
                          ["calendar is nearly full — delivery risk"])
    return GateResult("FEASIBLE", ["fulfillment looks feasible"])

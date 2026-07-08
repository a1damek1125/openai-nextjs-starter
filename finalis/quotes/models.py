"""Quote domain models + the quote state machine.

All money fields are Decimal (see pricing.py for the math). States after
SENT are immutable: any change becomes a new version (before acceptance)
or a ChangeOrder (after acceptance).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional


def _uuid() -> str:
    return str(uuid.uuid4())


ZERO = Decimal("0")

# --- state machine -----------------------------------------------------------------
QUOTE_STATES = {
    "DRAFT", "NEEDS_MORE_INFO", "PRICE_CALCULATED", "APPROVAL_REQUIRED",
    "APPROVED", "REJECTED_BY_APPROVER", "SENT", "VIEWED", "ACCEPTED",
    "DECLINED", "EXPIRED", "CANCELLED", "REVISED",
    "CONVERTED_TO_INVOICE", "SUPERSEDED",
}

QUOTE_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"NEEDS_MORE_INFO", "PRICE_CALCULATED", "CANCELLED"},
    "NEEDS_MORE_INFO": {"DRAFT", "CANCELLED"},
    "PRICE_CALCULATED": {"APPROVAL_REQUIRED", "APPROVED", "DRAFT",
                         "CANCELLED"},
    "APPROVAL_REQUIRED": {"APPROVED", "REJECTED_BY_APPROVER", "DRAFT",
                          "CANCELLED"},
    "APPROVED": {"SENT", "DRAFT", "CANCELLED"},
    "REJECTED_BY_APPROVER": {"DRAFT", "CANCELLED"},
    "SENT": {"VIEWED", "ACCEPTED", "DECLINED", "EXPIRED", "REVISED",
             "CANCELLED"},
    "VIEWED": {"ACCEPTED", "DECLINED", "EXPIRED", "REVISED"},
    "ACCEPTED": {"CONVERTED_TO_INVOICE"},
    "DECLINED": {"REVISED"},
    "EXPIRED": {"REVISED"},
    "CANCELLED": set(),
    "REVISED": {"SUPERSEDED"},
    "CONVERTED_TO_INVOICE": set(),
    "SUPERSEDED": set(),
}

# States in which line items / terms / schedules may still be edited.
EDITABLE_STATES = {"DRAFT", "NEEDS_MORE_INFO"}
# Client-visible states: content is frozen from here on.
LOCKED_STATES = QUOTE_STATES - EDITABLE_STATES - {"PRICE_CALCULATED",
                                                  "APPROVAL_REQUIRED",
                                                  "APPROVED",
                                                  "REJECTED_BY_APPROVER"}


class IllegalQuoteTransition(Exception):
    pass


class QuoteImmutableError(Exception):
    pass


def quote_transition(quote: "Quote", to_state: str) -> None:
    if to_state not in QUOTE_STATES:
        raise IllegalQuoteTransition(f"unknown state {to_state}")
    if to_state not in QUOTE_TRANSITIONS[quote.state]:
        raise IllegalQuoteTransition(
            f"{quote.state} -> {to_state} is not allowed")
    quote.state = to_state


# --- price book & rules ---------------------------------------------------------------
@dataclass
class PriceBookItem:
    sku: str
    name: str
    list_price: Decimal
    cost_hint: Optional[Decimal] = None
    tax_category: str = "standard"
    currency: str = "EUR"


@dataclass
class PriceBook:
    tenant_id: str
    name: str = "default"
    currency: str = "EUR"
    items: dict[str, PriceBookItem] = field(default_factory=dict)
    id: str = field(default_factory=_uuid)

    def get(self, sku: str) -> Optional[PriceBookItem]:
        return self.items.get(sku)


@dataclass
class PricingRule:
    """Deterministic adjustment applied at calculation time (ERPNext-style
    pricing-rule pattern: match on sku/quantity, apply discount or margin)."""
    tenant_id: str
    name: str
    applies_to_sku: str = "*"
    min_quantity: Decimal = ZERO
    discount_percent: Decimal = ZERO       # 0..100
    priority: int = 0
    id: str = field(default_factory=_uuid)

    def matches(self, sku: str, quantity: Decimal) -> bool:
        return (self.applies_to_sku in ("*", sku)
                and quantity >= self.min_quantity)


# --- quote ------------------------------------------------------------------------------
@dataclass
class QuoteLineItem:
    description: str
    quantity: Decimal = Decimal("1")
    sku: Optional[str] = None
    # Cost components (Decimal, same currency as the quote).
    material_cost: Decimal = ZERO
    labor_cost: Decimal = ZERO
    subcontractor_cost: Decimal = ZERO
    travel_cost: Decimal = ZERO
    permit_cost: Decimal = ZERO
    overhead_allocation: Decimal = ZERO
    risk_contingency: Decimal = ZERO
    cost_known: bool = True                 # False → mandatory-line review
    cost_age_days: int = 0                  # staleness feeds confidence
    mandatory: bool = True
    # Pricing.
    price_book_price: Optional[Decimal] = None
    manual_price: Optional[Decimal] = None  # explicit human override
    requested_discount: Decimal = ZERO      # absolute amount per unit
    discount_reason: str = ""
    is_free_item: bool = False
    tax_category: str = "standard"
    # Provenance / review.
    created_by: str = "human"               # "human" | "ai_worker"
    is_custom: bool = False                 # not from the price book
    requires_human_review: bool = False
    # Calculated (filled by pricing.calculate_line).
    line_cost: Decimal = ZERO
    price_before_discount: Decimal = ZERO
    applied_discount: Decimal = ZERO
    price_after_discount: Decimal = ZERO
    margin_percent: Optional[Decimal] = None
    line_total: Decimal = ZERO
    id: str = field(default_factory=_uuid)


@dataclass
class QuoteOption:
    """Good/better/best option grouping."""
    name: str
    line_item_ids: list[str] = field(default_factory=list)
    recommended: bool = False
    id: str = field(default_factory=_uuid)


@dataclass
class PaymentMilestone:
    label: str
    fraction: Decimal                       # of QuoteTotal, sums to 1
    trigger: str = "on_acceptance"          # on_acceptance|before_fulfillment|on_completion
    is_deposit: bool = False
    blocks_fulfillment_until_paid: bool = False


@dataclass
class PaymentSchedule:
    milestones: list[PaymentMilestone] = field(default_factory=list)
    id: str = field(default_factory=_uuid)

    def validate(self) -> None:
        total = sum((m.fraction for m in self.milestones), ZERO)
        if self.milestones and total != Decimal("1"):
            raise ValueError(f"milestone fractions sum to {total}, not 1")
        if any(m.fraction <= ZERO for m in self.milestones):
            raise ValueError("milestone fraction must be positive")


@dataclass
class PaymentRequirement:
    """Created when a quote is accepted — the handoff to invoicing later."""
    quote_id: str
    label: str
    amount: Decimal
    trigger: str
    blocks_fulfillment_until_paid: bool = False
    status: str = "REQUIRED"
    id: str = field(default_factory=_uuid)


@dataclass
class QuoteApprovalRequirement:
    quote_id: str
    reason: str
    requested_by: str
    status: str = "PENDING"                 # PENDING|APPROVED|REJECTED
    approver_id: Optional[str] = None
    id: str = field(default_factory=_uuid)


@dataclass
class QuoteEvidenceBundle:
    """What the price is based on — feeds EvidenceCoverageScore."""
    required_facts_covered: float = 0.0
    source_reliability: float = 0.0
    evidence_recency: float = 0.0
    scope_consistency: float = 0.0
    human_verified_facts: float = 0.0
    pricing_data_coverage: float = 0.0
    evidence_reference_ids: list[str] = field(default_factory=list)


@dataclass
class AcceptanceEvidence:
    """Manual acceptance must point at proof (call segment, email, upload)."""
    kind: str                               # verbal_call|email|signed_doc|portal_click
    reference_id: str
    recorded_by: str
    note: str = ""
    id: str = field(default_factory=_uuid)


@dataclass
class ChangeOrder:
    quote_id: str
    description: str
    price_delta: Decimal
    cost_delta: Decimal = ZERO
    reason: str = ""
    requested_by: str = "human"
    status: str = "PENDING_APPROVAL"        # PENDING_APPROVAL|APPROVED|REJECTED
    approver_id: Optional[str] = None
    id: str = field(default_factory=_uuid)


@dataclass
class QuoteDomainEvent:
    event_type: str
    quote_id: str
    case_id: Optional[str]
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default_factory=_uuid)


@dataclass
class Quote:
    tenant_id: str
    case_id: str
    customer_party_id: Optional[str] = None
    currency: str = "EUR"
    state: str = "DRAFT"
    version: int = 1
    revised_from_id: Optional[str] = None
    created_by: str = "human"               # "human" | "ai_worker"
    line_items: list[QuoteLineItem] = field(default_factory=list)
    options: list[QuoteOption] = field(default_factory=list)
    # Sendability requirements.
    assumptions: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    terms_template_id: Optional[str] = None
    terms_template_approved: bool = False
    custom_terms_text: str = ""             # anything here needs approval
    payment_schedule: Optional[PaymentSchedule] = None
    evidence: QuoteEvidenceBundle = field(default_factory=QuoteEvidenceBundle)
    acceptance_evidence: Optional[AcceptanceEvidence] = None
    # Calculated totals (pricing.calculate_quote).
    subtotal: Decimal = ZERO
    tax_total: Decimal = ZERO
    total: Decimal = ZERO
    rounding_adjustment: Decimal = ZERO
    # Validity.
    valid_days: int = 30
    valid_until: Optional[datetime] = None
    cost_volatility: float = 0.0            # 0..1, shortens validity
    sent_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    id: str = field(default_factory=_uuid)

    @property
    def editable(self) -> bool:
        return self.state in EDITABLE_STATES

    def assert_editable(self) -> None:
        if not self.editable:
            raise QuoteImmutableError(
                f"quote in state {self.state} is immutable — "
                "create a new version (before acceptance) or a "
                "change order (after acceptance)")

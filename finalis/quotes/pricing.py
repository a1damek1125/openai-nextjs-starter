"""Deterministic quote money math — Decimal only, no float drift.

Every intermediate that reaches a stored field is quantized to cents with
ROUND_HALF_UP, so recomputing a quote always reproduces the same totals and
the invariant `total == sum(line totals) + tax` holds exactly (any residue
from per-line rounding is stored explicitly as rounding_adjustment).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from .models import PriceBook, PricingRule, Quote, QuoteLineItem, ZERO

CENT = Decimal("0.01")
ONE = Decimal("1")


def money(x) -> Decimal:
    """Normalize any numeric input to a cent-quantized Decimal."""
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


def line_cost(li: QuoteLineItem) -> Decimal:
    return money(li.material_cost + li.labor_cost + li.subcontractor_cost
                 + li.travel_cost + li.permit_cost + li.overhead_allocation
                 + li.risk_contingency)


def price_from_margin(cost: Decimal, target_margin: Decimal) -> Decimal:
    """cost / (1 - margin). Margin >= 100% is a config error, not math."""
    if target_margin >= ONE:
        raise ValueError("target margin must be below 100%")
    if target_margin < ZERO:
        raise ValueError("target margin cannot be negative")
    return money(cost / (ONE - target_margin))


def margin_percent(price_after_discount: Decimal,
                   cost: Decimal) -> Optional[Decimal]:
    """(price - cost) / price. None when price is zero (free item /
    undefined margin) — callers must route None to human review."""
    if price_after_discount == ZERO:
        return None
    return ((price_after_discount - cost) / price_after_discount
            ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_line(li: QuoteLineItem, *, target_margin: Decimal,
                   max_auto_discount: Decimal,
                   price_book: Optional[PriceBook] = None,
                   pricing_rules: Optional[list[PricingRule]] = None,
                   discount_approved: bool = False) -> QuoteLineItem:
    """Fill the calculated fields of one line, deterministically."""
    li.line_cost = line_cost(li)

    book_price = li.price_book_price
    if book_price is None and li.sku and price_book:
        item = price_book.get(li.sku)
        if item:
            book_price = item.list_price
            li.price_book_price = book_price
    floor_price = price_from_margin(li.line_cost, target_margin)
    if li.manual_price is not None:
        # Explicit human override wins the base price; gates judge it.
        li.price_before_discount = money(li.manual_price)
    else:
        li.price_before_discount = max(money(book_price or ZERO),
                                       floor_price)

    # Pricing rules (highest priority match) express % discount requests.
    requested = money(li.requested_discount)
    for rule in sorted(pricing_rules or [], key=lambda r: -r.priority):
        if rule.matches(li.sku or "", li.quantity):
            rule_discount = money(li.price_before_discount
                                  * rule.discount_percent / Decimal("100"))
            requested = max(requested, rule_discount)
            break

    if li.is_free_item:
        requested = li.price_before_discount
    cap = money(max_auto_discount)
    li.applied_discount = requested if discount_approved \
        else min(requested, cap)
    li.price_after_discount = money(li.price_before_discount
                                    - li.applied_discount)
    if li.price_after_discount < ZERO:
        li.price_after_discount = ZERO
    li.margin_percent = margin_percent(li.price_after_discount, li.line_cost)
    li.line_total = money(li.price_after_discount * li.quantity)
    return li


# --- tax (MOCK — a real tax engine replaces this function's guts) --------------
MOCK_TAX_RATES = {"standard": Decimal("0.23"), "reduced": Decimal("0.08"),
                  "exempt": ZERO}
MOCK_TAX_ENGINE_IS_MOCK = True


def mock_tax_engine(subtotal: Decimal, tax_category: str,
                    tenant_tax_config: Optional[dict] = None) -> Decimal:
    rates = {**MOCK_TAX_RATES, **{
        k: Decimal(str(v)) for k, v in (tenant_tax_config or {}).items()}}
    if tax_category not in rates:
        raise ValueError(f"unknown tax category {tax_category}")
    return money(subtotal * rates[tax_category])


def calculate_quote(quote: Quote, *, target_margin: Decimal,
                    max_auto_discount: Decimal,
                    price_book: Optional[PriceBook] = None,
                    pricing_rules: Optional[list[PricingRule]] = None,
                    tenant_tax_config: Optional[dict] = None,
                    discount_approved: bool = False) -> Quote:
    """Recalculate every line + totals. Invariant: total = subtotal + tax,
    subtotal = exact sum of line totals (rounding residue is zero by
    construction because each line is already cent-quantized; the field
    stays for currencies/engines that round differently)."""
    for li in quote.line_items:
        calculate_line(li, target_margin=target_margin,
                       max_auto_discount=max_auto_discount,
                       price_book=price_book, pricing_rules=pricing_rules,
                       discount_approved=discount_approved)
    exact_sum = sum((li.line_total for li in quote.line_items), ZERO)
    quote.subtotal = money(exact_sum)
    quote.rounding_adjustment = money(quote.subtotal - exact_sum)
    # Tax per line category, summed (mixed-category quotes stay correct).
    tax = ZERO
    for li in quote.line_items:
        tax += mock_tax_engine(li.line_total, li.tax_category,
                               tenant_tax_config)
    quote.tax_total = money(tax)
    quote.total = money(quote.subtotal + quote.tax_total)
    return quote

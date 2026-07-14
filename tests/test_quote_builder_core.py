"""Quote Builder core tests (Q-A) — the 25 mandated rules + property tests.

Domain logic only: no API, no UI, no browser. Money is Decimal throughout;
every assertion about totals is exact, not approximate.
"""
import random
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from finalis.audit import AuditLog
from finalis.lifecycle.vector import (DealState, FulfillmentState,
                                      LifecycleVector, TransactionState)
from finalis.quotes.engine import QuoteEngine
from finalis.quotes.gates import (discount_approval_gate,
                                  fulfillment_feasibility_gate,
                                  margin_safety_gate, quote_readiness_gate)
from finalis.quotes.models import (AcceptanceEvidence, ChangeOrder,
                                   PaymentMilestone, PaymentSchedule,
                                   PriceBook, PriceBookItem, PricingRule,
                                   IllegalQuoteTransition,
                                   QuoteImmutableError, QuoteLineItem)
from finalis.quotes.pricing import (calculate_line, line_cost,
                                    margin_percent, mock_tax_engine, money,
                                    price_from_margin)
from finalis.quotes.scores import (QuoteThresholds, cost_freshness,
                                   evidence_coverage_score,
                                   price_confidence_score,
                                   quote_clarity_score, quote_risk_score)

D = Decimal
NOW = datetime(2026, 7, 9, 12, 0)


def engine(**kw):
    return QuoteEngine(AuditLog(), **kw)


def li(cost=D("100"), price=D("200"), qty=D("1"), **kw):
    """A simple healthy line: cost 100, book price 200 → 50% margin."""
    return QuoteLineItem(description=kw.pop("description", "heat pump"),
                         quantity=qty, material_cost=cost,
                         price_book_price=price, **kw)


def ready_ctx(**kw):
    return {"required_scope_facts_missing": 0, **kw}


def sendable(eng, q, book=None):
    q.assumptions = ["single-day install"]
    q.exclusions = ["electrical rework"]
    q.terms_template_id = "hvac-standard-v1"
    q.terms_template_approved = True
    eng.calculate(q, price_book=book, now=NOW)
    return q


class TestDraftAndMath:
    def test_1_draft_created_from_case(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="case-1",
                             customer_party_id="p1")
        assert q.state == "DRAFT" and q.version == 1
        assert eng.events[0].event_type == "QUOTE_DRAFT_CREATED"

    def test_2_line_totals_calculate_correctly(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, QuoteLineItem(
            description="pump", quantity=D("2"),
            material_cost=D("400"), labor_cost=D("150"),
            travel_cost=D("30"), overhead_allocation=D("20"),
            price_book_price=D("1000")))
        eng.calculate(q, now=NOW)
        item = q.line_items[0]
        assert item.line_cost == D("600.00")
        assert item.price_before_discount == D("1000.00")
        assert item.line_total == D("2000.00")
        assert q.subtotal == D("2000.00")
        assert q.tax_total == D("460.00")          # mock 23% VAT
        assert q.total == D("2460.00")

    def test_3_deterministic_money_rounding(self):
        assert money("10.005") == D("10.01")       # half-up, not banker's
        assert money("10.004") == D("10.00")
        assert money(0.1) + money(0.2) == D("0.30")  # no float drift
        assert mock_tax_engine(D("99.99"), "reduced") == D("8.00")

    def test_4_margin_calculation(self):
        assert margin_percent(D("200"), D("100")) == D("0.5000")
        assert margin_percent(D("100"), D("120")) == D("-0.2000")
        assert margin_percent(D("0"), D("50")) is None   # undefined → review

    def test_price_from_margin_floor_and_guards(self):
        assert price_from_margin(D("650"), D("0.35")) == D("1000.00")
        with pytest.raises(ValueError, match="below 100"):
            price_from_margin(D("100"), D("1"))
        with pytest.raises(ValueError, match="negative"):
            price_from_margin(D("100"), D("-0.1"))

    def test_price_is_max_of_book_and_margin_floor(self):
        # Cheap book price loses to the margin-derived floor.
        item = calculate_line(li(cost=D("650"), price=D("700")),
                              target_margin=D("0.35"),
                              max_auto_discount=D("0"))
        assert item.price_before_discount == D("1000.00")

    def test_pricing_rule_applies_percent_discount(self):
        rule = PricingRule(tenant_id="t1", name="bulk", applies_to_sku="HP1",
                           min_quantity=D("2"), discount_percent=D("10"))
        item = QuoteLineItem(description="x", sku="HP1", quantity=D("3"),
                             material_cost=D("100"),
                             price_book_price=D("500"),
                             discount_reason="bulk rule")
        calculate_line(item, target_margin=D("0.35"),
                       max_auto_discount=D("100"), pricing_rules=[rule])
        assert item.applied_discount == D("50.00")
        assert item.price_after_discount == D("450.00")

    def test_price_book_lookup_by_sku(self):
        book = PriceBook(tenant_id="t1")
        book.items["HP1"] = PriceBookItem(sku="HP1", name="pump",
                                          list_price=D("900"))
        item = QuoteLineItem(description="x", sku="HP1",
                             material_cost=D("100"))
        calculate_line(item, target_margin=D("0.35"),
                       max_auto_discount=D("0"), price_book=book)
        assert item.price_before_discount == D("900.00")


class TestMarginGate:
    def test_5_negative_margin_blocked(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, QuoteLineItem(description="loss leader",
                                      material_cost=D("500"),
                                      manual_price=D("400")))
        eng.calculate(q, now=NOW)
        g = margin_safety_gate(q, eng.thresholds)
        assert g.decision == "BLOCKED"
        assert g.hard_blockers
        assert "below cost" in g.reasons[0]

    def test_6_margin_below_floor_blocked_below_target_needs_approval(self):
        t = QuoteThresholds(margin_floor=D("0.10"),
                            target_margin=D("0.35"))
        eng = engine(thresholds=t)
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, QuoteLineItem(description="thin",
                                      material_cost=D("95"),
                                      manual_price=D("100")))  # 5% < floor
        eng.calculate(q, now=NOW)
        assert margin_safety_gate(q, t).decision == "BLOCKED"
        # Repriced to 20.8%: above floor, below target → approval path.
        q.line_items[0].manual_price = D("120")
        from finalis.quotes.pricing import calculate_quote
        calculate_quote(q, target_margin=t.target_margin,
                        max_auto_discount=t.max_auto_discount)
        assert margin_safety_gate(q, t).decision == "REQUIRE_APPROVAL"

    def test_8_unknown_cost_on_mandatory_line_needs_review(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, li(cost_known=False))
        eng.calculate(q, now=NOW)
        g = margin_safety_gate(q, eng.thresholds)
        assert g.decision == "REQUIRE_APPROVAL"
        assert "cost is unknown" in g.reasons[0]


class TestDiscountGate:
    def test_7_discount_above_threshold_requires_approval(self):
        t = QuoteThresholds(max_auto_discount=D("50"))
        eng = engine(thresholds=t)
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, li(price=D("1000"),
                           requested_discount=D("200"),
                           discount_reason="negotiation"))
        eng.calculate(q, now=NOW)
        # Auto path caps the discount at the threshold...
        assert q.line_items[0].applied_discount == D("50.00")
        # ...and the gate demands approval for the requested amount.
        g = discount_approval_gate(q, t)
        assert g.decision == "REQUIRE_APPROVAL"
        assert "exceeds the auto-approval threshold" in " ".join(g.reasons)

    def test_free_item_and_missing_reason_require_approval(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, li(description="freebie", is_free_item=True))
        eng.add_line(q, li(description="quiet discount",
                           requested_discount=D("10")))   # no reason
        eng.calculate(q, now=NOW)
        reasons = " ".join(discount_approval_gate(q, eng.thresholds).reasons)
        assert "free item" in reasons
        assert "no reason recorded" in reasons

    def test_approved_discount_applies_fully(self):
        item = calculate_line(li(price=D("1000"),
                                 requested_discount=D("300"),
                                 discount_reason="matched competitor"),
                              target_margin=D("0.35"),
                              max_auto_discount=D("50"),
                              discount_approved=True)
        assert item.applied_discount == D("300.00")
        assert item.price_after_discount == D("700.00")


class TestScores:
    def test_9_high_risk_blocks_ai_send(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, li())
        sendable(eng, q)
        risk = quote_risk_score(low_margin_risk=1, evidence_gap_risk=1,
                                delivery_risk=1, legal_terms_risk=0,
                                tax_risk=0, customer_complaint_risk=0,
                                scope_ambiguity_risk=1, expiration_risk=0,
                                price_override_risk=0)
        r = eng.send(q, actor_type="ai_worker",
                     readiness_context=ready_ctx(),
                     price_confidence=0.9, evidence_coverage=0.9,
                     clarity=0.9, risk=risk)
        assert r.decision == "REQUIRE_HUMAN_REVIEW"
        assert q.state != "SENT"

    @pytest.mark.parametrize("field", ["price_confidence",
                                       "evidence_coverage", "clarity"])
    def test_10_11_12_low_scores_block_auto_send(self, field):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, li())
        sendable(eng, q)
        scores = {"price_confidence": 0.9, "evidence_coverage": 0.9,
                  "clarity": 0.9, field: 0.4}
        r = eng.send(q, actor_type="ai_worker",
                     readiness_context=ready_ctx(), risk=0.1, **scores)
        assert r.decision == "REQUIRE_HUMAN_REVIEW"
        assert q.state != "SENT"

    def test_18_stale_cost_reduces_price_confidence(self):
        eng = engine()
        fresh_q = eng.create_draft(tenant_id="t1", case_id="c1",
                                   customer_party_id="p1")
        eng.add_line(fresh_q, li(cost_age_days=0))
        stale_q = eng.create_draft(tenant_id="t1", case_id="c2",
                                   customer_party_id="p1")
        eng.add_line(stale_q, li(cost_age_days=150))
        assert eng.price_confidence(stale_q) < eng.price_confidence(fresh_q)
        assert cost_freshness(0) == 1.0
        assert cost_freshness(180, stale_after_days=90) == 0.0

    def test_19_high_volatility_shortens_validity(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, li())
        q.cost_volatility = 0.9
        eng.calculate(q, now=NOW)
        assert q.valid_days == eng.thresholds.volatile_valid_days
        assert q.valid_until == NOW + timedelta(days=7)

    def test_score_bounds(self):
        assert quote_risk_score(
            low_margin_risk=9, evidence_gap_risk=9, delivery_risk=9,
            legal_terms_risk=9, tax_risk=9, customer_complaint_risk=9,
            scope_ambiguity_risk=9, expiration_risk=9,
            price_override_risk=9) == 1.0
        assert price_confidence_score(
            price_book_coverage=1, cost_known_coverage=1,
            similar_case_evidence=1, scope_certainty=1,
            labor_estimate_confidence=1, material_estimate_confidence=1,
            tax_rule_confidence=1) == 1.0
        assert evidence_coverage_score(
            required_facts_covered=0, source_reliability=0,
            evidence_recency=0, scope_consistency=0,
            human_verified_facts=0, pricing_data_coverage=0) == 0.0
        assert 0 <= quote_clarity_score(
            scope_clarity=.5, price_clarity=.5, terms_clarity=.5,
            exclusions_clarity=.5, payment_clarity=.5, timeline_clarity=.5,
            acceptance_instructions_clarity=.5) <= 1


class TestImmutabilityAndVersioning:
    def _sent_quote(self, eng):
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, li())
        sendable(eng, q)
        r = eng.send(q, readiness_context=ready_ctx(), now=NOW)
        assert r.decision == "SENT" and q.state == "SENT"
        return q

    def test_13_sent_quote_cannot_be_edited(self):
        eng = engine()
        q = self._sent_quote(eng)
        with pytest.raises(QuoteImmutableError):
            eng.add_line(q, li())
        with pytest.raises(QuoteImmutableError):
            eng.set_payment_schedule(q, PaymentSchedule(milestones=[
                PaymentMilestone(label="all", fraction=D("1"))]))
        with pytest.raises(QuoteImmutableError):
            eng.calculate(q, now=NOW)

    def test_14_accepted_quote_cannot_be_edited_or_revised(self):
        eng = engine()
        q = self._sent_quote(eng)
        eng.accept(q, now=NOW)
        with pytest.raises(QuoteImmutableError):
            eng.add_line(q, li())
        with pytest.raises(QuoteImmutableError, match="ChangeOrder"):
            eng.revise(q)

    def test_15_revision_creates_new_version_and_supersedes(self):
        eng = engine()
        q = self._sent_quote(eng)
        q2 = eng.revise(q)
        assert q.state == "REVISED"
        assert q2.version == 2 and q2.state == "DRAFT"
        assert q2.revised_from_id == q.id
        q2.line_items[0].requested_discount = D("20")
        q2.line_items[0].discount_reason = "loyalty"
        sendable(eng, q2)
        r = eng.send(q2, readiness_context=ready_ctx(), now=NOW)
        assert r.decision == "SENT"
        assert q.state == "SUPERSEDED"      # old version closed out

    def test_16_change_after_acceptance_is_change_order(self):
        eng = engine()
        q = self._sent_quote(eng)
        eng.accept(q, now=NOW)
        co = eng.create_change_order(q, description="extra duct run",
                                     price_delta=D("450"),
                                     requested_by="operator-1")
        assert co.status == "PENDING_APPROVAL"
        eng.approve_change_order(co, approver_id="owner-1")
        assert co.status == "APPROVED"
        extras = [p for p in eng.payment_requirements
                  if "change order" in p.label]
        assert extras and extras[0].amount == D("450.00")
        # Change orders only exist for accepted quotes.
        q3 = eng.create_draft(tenant_id="t1", case_id="c9",
                              customer_party_id="p1")
        with pytest.raises(ValueError, match="ACCEPTED"):
            eng.create_change_order(q3, description="x",
                                    price_delta=D("1"))

    def test_21_scope_creep_after_acceptance_needs_change_order(self):
        """The immutability error itself routes scope creep to the right
        mechanism: editing an accepted quote names ChangeOrder."""
        eng = engine()
        q = self._sent_quote(eng)
        eng.accept(q, now=NOW)
        with pytest.raises(QuoteImmutableError, match="change order"):
            eng.add_line(q, li(description="scope creep item"))


class TestAcceptance:
    def _sent(self, eng, schedule=None):
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, li(price=D("2000"), cost=D("1000")))
        if schedule:
            eng.set_payment_schedule(q, schedule)
        sendable(eng, q)
        eng.send(q, readiness_context=ready_ctx(), now=NOW)
        return q

    def test_17_payment_schedule_creates_requirements(self):
        eng = engine()
        schedule = PaymentSchedule(milestones=[
            PaymentMilestone(label="deposit", fraction=D("0.3"),
                             is_deposit=True,
                             blocks_fulfillment_until_paid=True),
            PaymentMilestone(label="final", fraction=D("0.7"),
                             trigger="on_completion")])
        q = self._sent(eng, schedule)
        reqs = eng.accept(q, now=NOW)
        assert len(reqs) == 2
        assert reqs[0].amount == D("738.00")       # 30% of 2460 gross
        assert reqs[1].amount == D("1722.00")      # remainder absorbs rounding
        assert sum(r.amount for r in reqs) == q.total
        assert reqs[0].blocks_fulfillment_until_paid is True

    def test_bad_payment_schedule_rejected(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        with pytest.raises(ValueError, match="sum"):
            eng.set_payment_schedule(q, PaymentSchedule(milestones=[
                PaymentMilestone(label="deposit", fraction=D("0.5"))]))

    def test_22_manual_acceptance_requires_evidence(self):
        eng = engine()
        q = self._sent(eng)
        with pytest.raises(ValueError, match="AcceptanceEvidence"):
            eng.accept(q, channel="verbal_call", now=NOW)
        ev = AcceptanceEvidence(kind="verbal_call",
                                reference_id="segment-42",
                                recorded_by="operator-1")
        reqs = eng.accept(q, channel="verbal_call", evidence=ev, now=NOW)
        assert q.state == "ACCEPTED" and reqs

    def test_expired_quote_cannot_be_accepted(self):
        eng = engine()
        q = self._sent(eng)
        with pytest.raises(ValueError, match="expired"):
            eng.accept(q, now=NOW + timedelta(days=60))
        assert q.state == "EXPIRED"

    def test_25_acceptance_does_not_complete_case(self):
        eng = engine()
        q = self._sent(eng)
        eng.accept(q, now=NOW)
        ev = [e for e in eng.events if e.event_type == "QUOTE_ACCEPTED"][0]
        assert ev.payload["case_completed"] is False
        assert ev.payload["opens"] == {"payment": True, "fulfillment": True}
        # And through the lifecycle's own math: accepted deal with open
        # payment + fulfillment is WON_NOT_FULFILLED, never WON_COMPLETED.
        v = LifecycleVector(deal=DealState.ACCEPTED_BY_CLIENT,
                            transaction=TransactionState.INVOICE_REQUIRED,
                            fulfillment=FulfillmentState.REQUIRED)
        assert v.derived_outcome_view() == "WON_NOT_FULFILLED"


class TestReadinessAndFeasibility:
    def test_24_hard_blockers_override_all_scores(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, li())
        sendable(eng, q)
        # Perfect scores, but the client opted out → BLOCKED, not sent.
        r = eng.send(q, actor_type="ai_worker",
                     readiness_context=ready_ctx(
                         client_opted_out_of_offers=True),
                     price_confidence=1.0, evidence_coverage=1.0,
                     clarity=1.0, risk=0.0)
        assert r.decision == "BLOCKED"
        assert "opted out" in " ".join(r.hard_blockers)
        assert q.state != "SENT"

    def test_readiness_blockers_enumerated(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id=None)   # no contact
        q.currency = ""
        q.custom_terms_text = "we guarantee everything forever"
        g = quote_readiness_gate(q, unresolved_complaint=True,
                                 has_price_book_or_rules=False)
        text = " ".join(g.hard_blockers)
        for expected in ("no customer contact", "unresolved complaint",
                         "no priceable item", "no currency",
                         "no price book", "approved template"):
            assert expected in text, expected
        assert g.decision == "BLOCKED"

    def test_20_feasibility_gate_blocks_undeliverable(self):
        g = fulfillment_feasibility_gate(
            delivery_window_possible=False, resource_available=True,
            material_availability_known=True, service_area_supported=True)
        assert g.decision == "BLOCKED"
        g2 = fulfillment_feasibility_gate(
            delivery_window_possible=True, resource_available=True,
            material_availability_known=False, service_area_supported=True)
        assert g2.decision == "REQUIRE_HUMAN_REVIEW"
        g3 = fulfillment_feasibility_gate(
            delivery_window_possible=True, resource_available=True,
            material_availability_known=True, service_area_supported=True,
            calendar_load=0.95)
        assert g3.decision == "FEASIBLE_WITH_RISK"
        # Feasibility hard blocker also stops sending, even for a human.
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, li())
        sendable(eng, q)
        r = eng.send(q, readiness_context=ready_ctx(),
                     feasibility_context={
                         "delivery_window_possible": True,
                         "resource_available": True,
                         "material_availability_known": True,
                         "service_area_supported": False}, now=NOW)
        assert r.decision == "BLOCKED"

    def test_23_ai_custom_line_requires_human_review(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1", created_by="ai_worker")
        item = eng.add_line(q, li(created_by="ai_worker", is_custom=True))
        assert item.requires_human_review is True
        sendable(eng, q)
        g = quote_readiness_gate(q, **ready_ctx())
        assert g.decision == "REQUIRE_HUMAN_REVIEW"
        r = eng.send(q, actor_type="ai_worker",
                     readiness_context=ready_ctx(),
                     price_confidence=1.0, evidence_coverage=1.0,
                     clarity=1.0, risk=0.0)
        assert r.decision == "REQUIRE_HUMAN_REVIEW"

    def test_terms_not_from_template_blocks_send(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, li())
        q.assumptions, q.exclusions = ["a"], ["e"]
        eng.calculate(q, now=NOW)          # terms never approved
        r = eng.send(q, readiness_context=ready_ctx(), now=NOW)
        assert r.decision == "REQUIRE_APPROVAL"
        assert "approved" in r.reasons[0]

    def test_missing_assumptions_or_exclusions_blocks_send(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, li())
        q.terms_template_approved = True
        eng.calculate(q, now=NOW)
        r = eng.send(q, readiness_context=ready_ctx(), now=NOW)
        assert r.decision == "BLOCKED"
        assert "assumptions" in r.reasons[0]


class TestApprovals:
    def test_ai_cannot_approve_and_no_self_approval(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1",
                             created_by="ai-worker-7")
        eng.add_line(q, li())
        eng.calculate(q, now=NOW)
        eng.request_approval(q, reason="below target margin",
                             requested_by="ai-worker-7")
        assert q.state == "APPROVAL_REQUIRED"
        with pytest.raises(PermissionError, match="human"):
            eng.approve(q, approver_id="ai-worker-7",
                        approver_actor_type="ai_worker")
        with pytest.raises(PermissionError, match="own quote"):
            eng.approve(q, approver_id="ai-worker-7")
        eng.approve(q, approver_id="owner-1")
        assert q.state == "APPROVED"
        with pytest.raises(PermissionError, match="own change order"):
            eng.approve_change_order(
                ChangeOrder(quote_id=q.id, description="x",
                            price_delta=D("1"), requested_by="op-1"),
                approver_id="op-1")

    def test_human_send_with_pending_approval_blocked(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, li(price=D("1000"), requested_discount=D("500"),
                           discount_reason="huge discount"))
        sendable(eng, q)
        r = eng.send(q, readiness_context=ready_ctx(), now=NOW)
        assert r.decision == "REQUIRE_APPROVAL"
        assert q.state != "SENT"


class TestStateMachine:
    def test_illegal_transitions_refused(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        with pytest.raises(IllegalQuoteTransition):
            from finalis.quotes.models import quote_transition
            quote_transition(q, "ACCEPTED")     # DRAFT → ACCEPTED illegal
        with pytest.raises(IllegalQuoteTransition):
            from finalis.quotes.models import quote_transition
            quote_transition(q, "NOT_A_STATE")

    def test_decline_requires_reason(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, li())
        sendable(eng, q)
        eng.send(q, readiness_context=ready_ctx(), now=NOW)
        with pytest.raises(ValueError, match="reason"):
            eng.decline(q, reason="  ")
        eng.decline(q, reason="price too high")
        assert q.state == "DECLINED"


class TestProperties:
    def test_totals_always_consistent(self):
        """Property: for random quotes, total == subtotal + tax and
        subtotal == exact sum of line totals; margins never negative
        unless flagged BLOCKED by the gate."""
        rng = random.Random(2026)
        eng = engine()
        for i in range(60):
            q = eng.create_draft(tenant_id="t1", case_id=f"c{i}",
                                 customer_party_id="p1")
            for _ in range(rng.randint(1, 6)):
                cost = D(rng.randint(50, 5000)) / 100
                price = D(rng.randint(1, 900000)) / 100
                q.line_items.append(QuoteLineItem(
                    description="r", quantity=D(rng.randint(1, 5)),
                    material_cost=cost, price_book_price=price,
                    requested_discount=D(rng.randint(0, 5000)) / 100,
                    discount_reason="prop",
                    tax_category=rng.choice(["standard", "reduced",
                                             "exempt"])))
            eng.calculate(q, now=NOW)
            assert q.total == q.subtotal + q.tax_total
            assert q.subtotal == sum(
                (l.line_total for l in q.line_items), D("0"))
            assert q.rounding_adjustment == D("0.00")
            g = margin_safety_gate(q, eng.thresholds)
            for l in q.line_items:
                if l.margin_percent is not None \
                        and l.margin_percent < D("0"):
                    assert g.decision == "BLOCKED"

    def test_margin_never_silently_below_floor(self):
        """Property: whatever the discount inputs, either the applied price
        keeps margin >= floor, or the margin gate refuses SAFE."""
        rng = random.Random(7)
        t = QuoteThresholds()
        eng = engine(thresholds=t)
        for i in range(80):
            q = eng.create_draft(tenant_id="t1", case_id=f"c{i}",
                                 customer_party_id="p1")
            q.line_items.append(QuoteLineItem(
                description="m", material_cost=D(rng.randint(100, 2000)),
                price_book_price=D(rng.randint(1, 3000)),
                requested_discount=D(rng.randint(0, 2000)),
                discount_reason="prop"))
            eng.calculate(q, now=NOW)
            g = margin_safety_gate(q, t)
            m = q.line_items[0].margin_percent
            if m is not None and m < t.margin_floor:
                assert g.decision != "SAFE"

    def test_accepted_quote_immutable_property(self):
        rng = random.Random(11)
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, li())
        sendable(eng, q)
        eng.send(q, readiness_context=ready_ctx(), now=NOW)
        eng.accept(q, now=NOW)
        for _ in range(20):
            op = rng.choice(["line", "schedule", "calc", "revise"])
            with pytest.raises((QuoteImmutableError,
                                IllegalQuoteTransition)):
                if op == "line":
                    eng.add_line(q, li())
                elif op == "schedule":
                    eng.set_payment_schedule(q, PaymentSchedule(milestones=[
                        PaymentMilestone(label="x", fraction=D("1"))]))
                elif op == "calc":
                    eng.calculate(q, now=NOW)
                else:
                    eng.revise(q)
        assert q.state == "ACCEPTED"        # nothing slipped through

    def test_hard_blockers_always_override_scores_property(self):
        rng = random.Random(13)
        eng = engine()
        for i in range(30):
            q = eng.create_draft(tenant_id="t1", case_id=f"c{i}",
                                 customer_party_id="p1")
            eng.add_line(q, li())
            sendable(eng, q)
            r = eng.send(q, actor_type="ai_worker",
                         readiness_context=ready_ctx(
                             client_opted_out_of_offers=True),
                         price_confidence=rng.random(),
                         evidence_coverage=rng.random(),
                         clarity=rng.random(), risk=rng.random())
            assert r.decision == "BLOCKED"
            assert q.state != "SENT"

    def test_audit_chain_survives_quote_lifecycle(self):
        eng = engine()
        q = eng.create_draft(tenant_id="t1", case_id="c1",
                             customer_party_id="p1")
        eng.add_line(q, li())
        sendable(eng, q)
        eng.send(q, readiness_context=ready_ctx(), now=NOW)
        eng.accept(q, now=NOW)
        types = {e.event_type for e in eng.events}
        assert {"QUOTE_DRAFT_CREATED", "QUOTE_LINE_ADDED",
                "QUOTE_PRICE_CALCULATED", "QUOTE_SENT",
                "QUOTE_ACCEPTED"} <= types
        assert eng.audit.verify_chain()

"""QuoteEngine — orchestrates models, pricing, gates, and scores into the
quote lifecycle, emitting domain events for audit/lifecycle handoff.

Every rule is enforced here, server-side: immutability after SENT,
versioning, change orders after acceptance, AI self-approval ban,
acceptance evidence, and the invariant that an ACCEPTED quote never
completes a case by itself.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from .gates import (GateResult, discount_approval_gate,
                    fulfillment_feasibility_gate, margin_safety_gate,
                    quote_readiness_gate)
from .models import (AcceptanceEvidence, ChangeOrder, PaymentRequirement,
                     PaymentSchedule, PriceBook, PricingRule, Quote,
                     QuoteApprovalRequirement, QuoteDomainEvent,
                     QuoteImmutableError, QuoteLineItem, ZERO,
                     quote_transition)
from .pricing import calculate_quote, money
from .scores import (QuoteThresholds, cost_freshness,
                     price_confidence_score)


class QuoteEngine:
    def __init__(self, audit=None,
                 thresholds: Optional[QuoteThresholds] = None) -> None:
        self.audit = audit
        self.thresholds = thresholds or QuoteThresholds()
        self.quotes: dict[str, Quote] = {}
        self.approvals: list[QuoteApprovalRequirement] = []
        self.change_orders: list[ChangeOrder] = []
        self.payment_requirements: list[PaymentRequirement] = []
        self.events: list[QuoteDomainEvent] = []

    # -- events -------------------------------------------------------------------
    def _emit(self, event_type: str, quote: Quote, **payload) -> None:
        ev = QuoteDomainEvent(event_type=event_type, quote_id=quote.id,
                              case_id=quote.case_id, payload=payload)
        self.events.append(ev)
        if self.audit is not None:
            self.audit.append(event_type=event_type, actor="quote-engine",
                              case_id=quote.case_id,
                              payload={"quote_id": quote.id, **payload})

    # -- draft & lines -------------------------------------------------------------
    def create_draft(self, *, tenant_id: str, case_id: str,
                     customer_party_id: Optional[str] = None,
                     created_by: str = "human",
                     currency: str = "EUR") -> Quote:
        q = Quote(tenant_id=tenant_id, case_id=case_id,
                  customer_party_id=customer_party_id,
                  created_by=created_by, currency=currency)
        self.quotes[q.id] = q
        self._emit("QUOTE_DRAFT_CREATED", q, created_by=created_by,
                   version=q.version)
        return q

    def add_line(self, quote: Quote, li: QuoteLineItem) -> QuoteLineItem:
        quote.assert_editable()
        # AI-created custom (off-price-book) lines always need human review.
        if li.created_by == "ai_worker" and li.is_custom:
            li.requires_human_review = True
        quote.line_items.append(li)
        self._emit("QUOTE_LINE_ADDED", quote, line_id=li.id,
                   description=li.description,
                   requires_human_review=li.requires_human_review)
        return li

    def set_payment_schedule(self, quote: Quote,
                             schedule: PaymentSchedule) -> None:
        quote.assert_editable()
        schedule.validate()
        quote.payment_schedule = schedule
        self._emit("QUOTE_PAYMENT_SCHEDULE_SET", quote,
                   milestones=len(schedule.milestones))

    # -- calculation -----------------------------------------------------------------
    def calculate(self, quote: Quote, *,
                  price_book: Optional[PriceBook] = None,
                  pricing_rules: Optional[list[PricingRule]] = None,
                  tenant_tax_config: Optional[dict] = None,
                  discount_approved: bool = False,
                  now: Optional[datetime] = None) -> Quote:
        quote.assert_editable()
        calculate_quote(quote, target_margin=self.thresholds.target_margin,
                        max_auto_discount=self.thresholds.max_auto_discount,
                        price_book=price_book, pricing_rules=pricing_rules,
                        tenant_tax_config=tenant_tax_config,
                        discount_approved=discount_approved)
        # Validity: volatile costs shorten it and may force review.
        days = self.thresholds.base_valid_days
        if quote.cost_volatility >= self.thresholds \
                .volatility_review_threshold:
            days = self.thresholds.volatile_valid_days
        quote.valid_days = days
        quote.valid_until = (now or datetime.utcnow()) + timedelta(days=days)
        quote_transition(quote, "PRICE_CALCULATED")
        self._emit("QUOTE_PRICE_CALCULATED", quote,
                   subtotal=str(quote.subtotal), tax=str(quote.tax_total),
                   total=str(quote.total), valid_days=days)
        return quote

    # -- gates + approvals ---------------------------------------------------------
    def evaluate_gates(self, quote: Quote, *,
                       readiness_context: Optional[dict] = None,
                       feasibility_context: Optional[dict] = None
                       ) -> dict[str, GateResult]:
        results = {
            "readiness": quote_readiness_gate(
                quote, **(readiness_context or {})),
            "margin": margin_safety_gate(quote, self.thresholds),
            "discount": discount_approval_gate(quote, self.thresholds),
        }
        if feasibility_context is not None:
            results["feasibility"] = fulfillment_feasibility_gate(
                **feasibility_context)
        return results

    def request_approval(self, quote: Quote, *, reason: str,
                         requested_by: str) -> QuoteApprovalRequirement:
        req = QuoteApprovalRequirement(quote_id=quote.id, reason=reason,
                                       requested_by=requested_by)
        self.approvals.append(req)
        if quote.state == "PRICE_CALCULATED":
            quote_transition(quote, "APPROVAL_REQUIRED")
        self._emit("QUOTE_APPROVAL_REQUESTED", quote, reason=reason,
                   requested_by=requested_by)
        return req

    def approve(self, quote: Quote, *, approver_id: str,
                approver_actor_type: str = "human") -> None:
        """AI cannot approve quotes; nobody approves their own quote."""
        if approver_actor_type != "human":
            raise PermissionError("only a human can approve a quote")
        if approver_id == quote.created_by:
            raise PermissionError("cannot approve your own quote")
        for req in self.approvals:
            if req.quote_id == quote.id and req.status == "PENDING":
                req.status = "APPROVED"
                req.approver_id = approver_id
        if quote.state in ("PRICE_CALCULATED", "APPROVAL_REQUIRED"):
            quote_transition(quote, "APPROVED")
        self._emit("QUOTE_APPROVED", quote, approver_id=approver_id)

    # -- sending ----------------------------------------------------------------------
    def send(self, quote: Quote, *, actor_type: str = "human",
             readiness_context: Optional[dict] = None,
             feasibility_context: Optional[dict] = None,
             price_confidence: Optional[float] = None,
             evidence_coverage: Optional[float] = None,
             clarity: Optional[float] = None,
             risk: Optional[float] = None,
             now: Optional[datetime] = None) -> GateResult:
        """Returns SAFE/SENT result or the blocking gate result. Hard
        blockers always win; AI auto-send additionally needs every score
        above its threshold and no pending approval."""
        gates = self.evaluate_gates(quote,
                                    readiness_context=readiness_context,
                                    feasibility_context=feasibility_context)
        for name, g in gates.items():
            if g.hard_blockers:
                self._emit("QUOTE_SEND_BLOCKED", quote, gate=name,
                           reasons=g.reasons)
                return g
        if not quote.assumptions or not quote.exclusions:
            g = GateResult("BLOCKED",
                           ["a sendable quote must list its assumptions "
                            "and exclusions"],
                           ["missing assumptions/exclusions"])
            self._emit("QUOTE_SEND_BLOCKED", quote, gate="content",
                       reasons=g.reasons)
            return g
        if not quote.terms_template_approved:
            g = GateResult("REQUIRE_APPROVAL",
                           ["terms/warranty text is not from an approved "
                            "template — human approval required"])
            self._emit("QUOTE_SEND_BLOCKED", quote, gate="terms",
                       reasons=g.reasons)
            return g
        pending = [r for r in self.approvals
                   if r.quote_id == quote.id and r.status == "PENDING"]
        needs_approval = pending or any(
            g.decision in ("REQUIRE_APPROVAL", "REQUIRE_HUMAN_REVIEW",
                           "NEEDS_MORE_INFO") for g in gates.values())
        if actor_type != "human":
            t = self.thresholds
            checks = [("price confidence", price_confidence,
                       t.min_price_confidence),
                      ("evidence coverage", evidence_coverage,
                       t.min_evidence_coverage),
                      ("quote clarity", clarity, t.min_clarity)]
            for label, value, minimum in checks:
                if value is None or value < minimum:
                    g = GateResult("REQUIRE_HUMAN_REVIEW",
                                   [f"{label} "
                                    f"{'unknown' if value is None else value}"
                                    f" is below the {minimum} auto-send "
                                    "threshold"])
                    self._emit("QUOTE_SEND_BLOCKED", quote, gate=label,
                               reasons=g.reasons)
                    return g
            if risk is not None and risk >= t.risk_review_threshold:
                g = GateResult("REQUIRE_HUMAN_REVIEW",
                               [f"quote risk {risk} requires human review"])
                self._emit("QUOTE_SEND_BLOCKED", quote, gate="risk",
                           reasons=g.reasons)
                return g
            if needs_approval:
                g = GateResult("REQUIRE_HUMAN_REVIEW",
                               ["approval-requiring quote cannot be "
                                "auto-sent by AI"])
                self._emit("QUOTE_SEND_BLOCKED", quote, gate="approval",
                           reasons=g.reasons)
                return g
        elif needs_approval and quote.state != "APPROVED":
            g = GateResult("REQUIRE_APPROVAL",
                           [r for gate in gates.values()
                            for r in gate.reasons
                            if gate.decision != "SAFE"]
                           or ["pending approval"])
            self._emit("QUOTE_SEND_BLOCKED", quote, gate="approval",
                       reasons=g.reasons)
            return g
        if quote.state == "PRICE_CALCULATED":
            quote_transition(quote, "APPROVED")
        quote_transition(quote, "SENT")
        quote.sent_at = now or datetime.utcnow()
        # Sending a revision supersedes the ancestor it revised.
        if quote.revised_from_id:
            old = self.quotes.get(quote.revised_from_id)
            if old is not None and old.state == "REVISED":
                quote_transition(old, "SUPERSEDED")
                self._emit("QUOTE_SUPERSEDED", old,
                           superseded_by=quote.id)
        self._emit("QUOTE_SENT", quote, total=str(quote.total),
                   actor_type=actor_type)
        return GateResult("SENT", ["quote sent"])

    # -- client responses --------------------------------------------------------------
    def mark_viewed(self, quote: Quote) -> None:
        quote_transition(quote, "VIEWED")
        self._emit("QUOTE_VIEWED", quote)

    def accept(self, quote: Quote, *, channel: str = "portal_click",
               evidence: Optional[AcceptanceEvidence] = None,
               now: Optional[datetime] = None) -> list[PaymentRequirement]:
        """Acceptance freezes the quote and creates payment requirements.
        It NEVER completes the case — deal acceptance only opens the
        payment + fulfillment obligations (lifecycle handles the rest)."""
        if channel != "portal_click" and evidence is None:
            raise ValueError("manual acceptance requires AcceptanceEvidence "
                             "(call segment, e-mail, or signed document)")
        now = now or datetime.utcnow()
        if quote.valid_until and now > quote.valid_until:
            quote_transition(quote, "EXPIRED")
            self._emit("QUOTE_EXPIRED", quote)
            raise ValueError("quote validity has expired — revise it")
        quote_transition(quote, "ACCEPTED")
        quote.accepted_at = now
        quote.acceptance_evidence = evidence
        reqs: list[PaymentRequirement] = []
        schedule = quote.payment_schedule or PaymentSchedule(milestones=[])
        if not schedule.milestones:
            reqs.append(PaymentRequirement(
                quote_id=quote.id, label="full amount", amount=quote.total,
                trigger="on_acceptance"))
        else:
            allocated = ZERO
            for i, m in enumerate(schedule.milestones):
                if i < len(schedule.milestones) - 1:
                    amount = money(quote.total * m.fraction)
                    allocated += amount
                else:                       # last milestone absorbs rounding
                    amount = money(quote.total - allocated)
                reqs.append(PaymentRequirement(
                    quote_id=quote.id, label=m.label, amount=amount,
                    trigger=m.trigger,
                    blocks_fulfillment_until_paid=m
                    .blocks_fulfillment_until_paid))
        self.payment_requirements.extend(reqs)
        self._emit("QUOTE_ACCEPTED", quote, channel=channel,
                   evidence_kind=evidence.kind if evidence else "portal",
                   payment_requirements=len(reqs),
                   case_completed=False,     # explicit: accepted ≠ done
                   opens={"payment": True, "fulfillment": True})
        return reqs

    def decline(self, quote: Quote, *, reason: str) -> None:
        if not reason.strip():
            raise ValueError("declining requires a reason")
        quote_transition(quote, "DECLINED")
        self._emit("QUOTE_DECLINED", quote, reason=reason)

    # -- versioning & change orders -------------------------------------------------
    def revise(self, quote: Quote, *, revised_by: str = "human") -> Quote:
        """Before acceptance: any change to a SENT/VIEWED/DECLINED/EXPIRED
        quote is a NEW VERSION; the old quote becomes REVISED (and
        SUPERSEDED once the new version is sent)."""
        if quote.state == "ACCEPTED":
            raise QuoteImmutableError(
                "accepted quotes change via ChangeOrder, not revision")
        quote_transition(quote, "REVISED")
        import copy
        import uuid
        new = copy.deepcopy(quote)
        new.id = str(uuid.uuid4())
        for li in new.line_items:           # a new version owns its lines
            li.id = str(uuid.uuid4())
        new.state = "DRAFT"
        new.version = quote.version + 1
        new.revised_from_id = quote.id
        new.sent_at = None
        new.accepted_at = None
        new.acceptance_evidence = None
        new.created_by = revised_by
        self.quotes[new.id] = new
        self._emit("QUOTE_REVISED", quote, new_quote_id=new.id,
                   new_version=new.version)
        return new

    def create_change_order(self, quote: Quote, *, description: str,
                            price_delta: Decimal,
                            cost_delta: Decimal = ZERO,
                            reason: str = "",
                            requested_by: str = "human") -> ChangeOrder:
        """After acceptance (scope creep, extras): the accepted quote stays
        immutable; the delta lives in an approval-gated ChangeOrder."""
        if quote.state != "ACCEPTED":
            raise ValueError("change orders apply to ACCEPTED quotes only "
                             "— revise the quote instead")
        co = ChangeOrder(quote_id=quote.id, description=description,
                         price_delta=money(price_delta),
                         cost_delta=money(cost_delta), reason=reason,
                         requested_by=requested_by)
        self.change_orders.append(co)
        self._emit("QUOTE_CHANGE_ORDER_CREATED", quote,
                   change_order_id=co.id, price_delta=str(co.price_delta),
                   status=co.status)
        return co

    def approve_change_order(self, co: ChangeOrder, *, approver_id: str,
                             approver_actor_type: str = "human") -> None:
        if approver_actor_type != "human":
            raise PermissionError("only a human can approve a change order")
        if approver_id == co.requested_by:
            raise PermissionError("cannot approve your own change order")
        co.status = "APPROVED"
        co.approver_id = approver_id
        quote = self.quotes[co.quote_id]
        # The extra amount becomes a payment requirement too.
        self.payment_requirements.append(PaymentRequirement(
            quote_id=quote.id, label=f"change order: {co.description}",
            amount=co.price_delta, trigger="on_completion"))
        self._emit("QUOTE_CHANGE_ORDER_APPROVED", quote,
                   change_order_id=co.id, approver_id=approver_id)

    # -- confidence helper ----------------------------------------------------------
    def price_confidence(self, quote: Quote, *,
                         similar_case_evidence: float = 0.5,
                         scope_certainty: float = 0.8,
                         labor_estimate_confidence: float = 0.8,
                         material_estimate_confidence: float = 0.8,
                         tax_rule_confidence: float = 0.9) -> float:
        """Compute PriceConfidence from the quote's own lines: price-book
        coverage and cost freshness are derived, not asserted."""
        lines = quote.line_items or []
        n = len(lines) or 1
        book_cov = sum(1 for li in lines
                       if li.price_book_price is not None) / n
        cost_cov = sum(
            (1.0 if li.cost_known else 0.0)
            * cost_freshness(li.cost_age_days,
                             stale_after_days=self.thresholds
                             .cost_stale_after_days)
            for li in lines) / n
        return price_confidence_score(
            price_book_coverage=book_cov, cost_known_coverage=cost_cov,
            similar_case_evidence=similar_case_evidence,
            scope_certainty=scope_certainty,
            labor_estimate_confidence=labor_estimate_confidence,
            material_estimate_confidence=material_estimate_confidence,
            tax_rule_confidence=tax_rule_confidence)

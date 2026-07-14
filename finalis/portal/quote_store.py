"""Quote persistence — Quote dataclasses ↔ migration-v3 SQLite tables.

Money round-trips as TEXT-encoded Decimal (never REAL), so a reloaded
quote recomputes to identical totals. Line items keep their full dataclass
body in body_json (source of truth) plus indexed columns for queries.
"""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from decimal import Decimal
from typing import Optional

from ..quotes.models import (AcceptanceEvidence, ChangeOrder,
                             PaymentMilestone, PaymentRequirement,
                             PaymentSchedule, PriceBook, PriceBookItem,
                             PricingRule, Quote, QuoteApprovalRequirement,
                             QuoteEvidenceBundle, QuoteLineItem)
from .db import Database, utcnow

_LINE_DECIMALS = ["quantity", "material_cost", "labor_cost",
                  "subcontractor_cost", "travel_cost", "permit_cost",
                  "overhead_allocation", "risk_contingency",
                  "requested_discount", "line_cost",
                  "price_before_discount", "applied_discount",
                  "price_after_discount", "line_total"]
_LINE_OPT_DECIMALS = ["price_book_price", "manual_price", "margin_percent"]


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _dt(s: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(s) if s else None


def _line_to_json(li: QuoteLineItem) -> str:
    return json.dumps(dataclasses.asdict(li), default=str)


def _line_from_json(raw: str) -> QuoteLineItem:
    d = json.loads(raw)
    for k in _LINE_DECIMALS:
        d[k] = Decimal(d[k])
    for k in _LINE_OPT_DECIMALS:
        d[k] = Decimal(d[k]) if d.get(k) is not None else None
    return QuoteLineItem(**d)


class QuoteStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    # -- quotes ------------------------------------------------------------------
    def save_quote(self, q: Quote) -> None:
        row = {
            "id": q.id, "tenant_id": q.tenant_id, "case_id": q.case_id,
            "customer_party_id": q.customer_party_id,
            "currency": q.currency, "state": q.state, "version": q.version,
            "revised_from_id": q.revised_from_id,
            "created_by": q.created_by,
            "subtotal": str(q.subtotal), "tax_total": str(q.tax_total),
            "total": str(q.total),
            "rounding_adjustment": str(q.rounding_adjustment),
            "valid_days": q.valid_days, "valid_until": _iso(q.valid_until),
            "cost_volatility": q.cost_volatility,
            "sent_at": _iso(q.sent_at), "accepted_at": _iso(q.accepted_at),
            "assumptions_json": json.dumps(q.assumptions),
            "exclusions_json": json.dumps(q.exclusions),
            "terms_template_id": q.terms_template_id,
            "terms_template_approved": int(q.terms_template_approved),
            "custom_terms_text": q.custom_terms_text,
            "payment_schedule_json": json.dumps(
                [dataclasses.asdict(m) for m in
                 q.payment_schedule.milestones], default=str)
            if q.payment_schedule else None,
            "evidence_json": json.dumps(dataclasses.asdict(q.evidence)),
            "acceptance_evidence_json": json.dumps(
                dataclasses.asdict(q.acceptance_evidence))
            if q.acceptance_evidence else None,
            "updated_at": utcnow(),
        }
        if self.db.one("SELECT id FROM quotes WHERE id=?", q.id):
            self.db.update("quotes", q.id, row)
        else:
            self.db.insert("quotes", row)
        self.db.conn.execute(
            "DELETE FROM quote_line_items WHERE quote_id=?", (q.id,))
        self.db.conn.commit()
        for pos, li in enumerate(q.line_items):
            self.db.insert("quote_line_items", {
                "id": li.id, "tenant_id": q.tenant_id, "quote_id": q.id,
                "position": pos, "description": li.description,
                "sku": li.sku, "line_total": str(li.line_total),
                "margin_percent": str(li.margin_percent)
                if li.margin_percent is not None else None,
                "body_json": _line_to_json(li)})
        if q.acceptance_evidence:
            ev = q.acceptance_evidence
            if not self.db.one("SELECT id FROM acceptance_evidence "
                               "WHERE id=?", ev.id):
                self.db.insert("acceptance_evidence", {
                    "id": ev.id, "tenant_id": q.tenant_id, "quote_id": q.id,
                    "kind": ev.kind, "reference_id": ev.reference_id,
                    "recorded_by": ev.recorded_by, "note": ev.note})

    def load_quote(self, quote_id: str, *,
                   tenant_id: str) -> Optional[Quote]:
        r = self.db.one("SELECT * FROM quotes WHERE id=? AND tenant_id=?",
                        quote_id, tenant_id)
        if r is None:
            return None
        schedule = None
        if r["payment_schedule_json"]:
            schedule = PaymentSchedule(milestones=[
                PaymentMilestone(label=m["label"],
                                 fraction=Decimal(m["fraction"]),
                                 trigger=m["trigger"],
                                 is_deposit=m["is_deposit"],
                                 blocks_fulfillment_until_paid=m[
                                     "blocks_fulfillment_until_paid"])
                for m in json.loads(r["payment_schedule_json"])])
        acceptance = None
        if r["acceptance_evidence_json"]:
            acceptance = AcceptanceEvidence(
                **json.loads(r["acceptance_evidence_json"]))
        q = Quote(
            tenant_id=r["tenant_id"], case_id=r["case_id"],
            customer_party_id=r["customer_party_id"],
            currency=r["currency"], state=r["state"],
            version=r["version"], revised_from_id=r["revised_from_id"],
            created_by=r["created_by"],
            assumptions=json.loads(r["assumptions_json"]),
            exclusions=json.loads(r["exclusions_json"]),
            terms_template_id=r["terms_template_id"],
            terms_template_approved=bool(r["terms_template_approved"]),
            custom_terms_text=r["custom_terms_text"],
            payment_schedule=schedule,
            evidence=QuoteEvidenceBundle(**json.loads(r["evidence_json"])),
            acceptance_evidence=acceptance,
            subtotal=Decimal(r["subtotal"]),
            tax_total=Decimal(r["tax_total"]), total=Decimal(r["total"]),
            rounding_adjustment=Decimal(r["rounding_adjustment"]),
            valid_days=r["valid_days"], valid_until=_dt(r["valid_until"]),
            cost_volatility=r["cost_volatility"],
            sent_at=_dt(r["sent_at"]), accepted_at=_dt(r["accepted_at"]),
            id=r["id"])
        q.line_items = [
            _line_from_json(lr["body_json"]) for lr in self.db.all(
                "SELECT body_json FROM quote_line_items WHERE quote_id=? "
                "ORDER BY position", quote_id)]
        return q

    def list_quotes(self, *, tenant_id: str,
                    case_id: Optional[str] = None) -> list[dict]:
        sql = ("SELECT id, case_id, state, version, total, currency, "
               "created_by, valid_until FROM quotes WHERE tenant_id=?")
        params = [tenant_id]
        if case_id:
            sql += " AND case_id=?"
            params.append(case_id)
        return [dict(r) for r in self.db.all(sql + " ORDER BY created_at",
                                             *params)]

    # -- approvals -----------------------------------------------------------------
    def save_approval(self, tenant_id: str,
                      req: QuoteApprovalRequirement) -> None:
        row = {"id": req.id, "tenant_id": tenant_id,
               "quote_id": req.quote_id, "reason": req.reason,
               "requested_by": req.requested_by, "status": req.status,
               "approver_id": req.approver_id}
        if self.db.one("SELECT id FROM quote_approvals WHERE id=?", req.id):
            self.db.update("quote_approvals", req.id, row)
        else:
            self.db.insert("quote_approvals", row)

    def load_approvals(self, quote_id: str, *,
                       tenant_id: str) -> list[QuoteApprovalRequirement]:
        return [QuoteApprovalRequirement(
                    quote_id=r["quote_id"], reason=r["reason"],
                    requested_by=r["requested_by"], status=r["status"],
                    approver_id=r["approver_id"], id=r["id"])
                for r in self.db.all(
                    "SELECT * FROM quote_approvals WHERE quote_id=? AND "
                    "tenant_id=?", quote_id, tenant_id)]

    # -- change orders ------------------------------------------------------------
    def save_change_order(self, tenant_id: str, co: ChangeOrder,
                          margin_percent: Optional[Decimal] = None) -> None:
        row = {"id": co.id, "tenant_id": tenant_id, "quote_id": co.quote_id,
               "description": co.description,
               "price_delta": str(co.price_delta),
               "cost_delta": str(co.cost_delta),
               "margin_percent": str(margin_percent)
               if margin_percent is not None else None,
               "reason": co.reason, "requested_by": co.requested_by,
               "status": co.status, "approver_id": co.approver_id}
        if self.db.one("SELECT id FROM change_orders WHERE id=?", co.id):
            self.db.update("change_orders", co.id, row)
        else:
            self.db.insert("change_orders", row)

    def load_change_orders(self, quote_id: str, *,
                           tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT * FROM change_orders WHERE quote_id=? AND tenant_id=?",
            quote_id, tenant_id)]

    # -- payment requirements ----------------------------------------------------
    def save_payment_requirements(self, tenant_id: str,
                                  reqs: list[PaymentRequirement]) -> None:
        for p in reqs:
            self.db.insert("payment_requirements", {
                "id": p.id, "tenant_id": tenant_id, "quote_id": p.quote_id,
                "label": p.label, "amount": str(p.amount),
                "trigger_event": p.trigger,
                "blocks_fulfillment_until_paid":
                    int(p.blocks_fulfillment_until_paid),
                "status": p.status})

    def load_payment_requirements(self, quote_id: str, *,
                                  tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT * FROM payment_requirements WHERE quote_id=? AND "
            "tenant_id=?", quote_id, tenant_id)]

    # -- price books & rules ------------------------------------------------------
    def save_price_book(self, book: PriceBook) -> None:
        if not self.db.one("SELECT id FROM price_books WHERE id=?", book.id):
            self.db.insert("price_books", {
                "id": book.id, "tenant_id": book.tenant_id,
                "name": book.name, "currency": book.currency})
        for item in book.items.values():
            self.save_price_book_item(book, item)

    def save_price_book_item(self, book: PriceBook,
                             item: PriceBookItem) -> None:
        existing = self.db.one(
            "SELECT id FROM price_book_items WHERE price_book_id=? AND "
            "sku=?", book.id, item.sku)
        row = {"tenant_id": book.tenant_id, "price_book_id": book.id,
               "sku": item.sku, "name": item.name,
               "list_price": str(item.list_price),
               "cost_hint": str(item.cost_hint)
               if item.cost_hint is not None else None,
               "tax_category": item.tax_category}
        if existing:
            self.db.update("price_book_items", existing["id"], row)
        else:
            import uuid
            self.db.insert("price_book_items",
                           {"id": str(uuid.uuid4()), **row})

    def load_price_book(self, book_id: str, *,
                        tenant_id: str) -> Optional[PriceBook]:
        r = self.db.one("SELECT * FROM price_books WHERE id=? AND "
                        "tenant_id=?", book_id, tenant_id)
        if r is None:
            return None
        book = PriceBook(tenant_id=r["tenant_id"], name=r["name"],
                         currency=r["currency"], id=r["id"])
        for ir in self.db.all("SELECT * FROM price_book_items WHERE "
                              "price_book_id=?", book_id):
            book.items[ir["sku"]] = PriceBookItem(
                sku=ir["sku"], name=ir["name"],
                list_price=Decimal(ir["list_price"]),
                cost_hint=Decimal(ir["cost_hint"])
                if ir["cost_hint"] else None,
                tax_category=ir["tax_category"])
        return book

    def default_price_book(self, tenant_id: str) -> Optional[PriceBook]:
        r = self.db.one("SELECT id FROM price_books WHERE tenant_id=? "
                        "ORDER BY created_at LIMIT 1", tenant_id)
        return self.load_price_book(r["id"], tenant_id=tenant_id) \
            if r else None

    def save_pricing_rule(self, rule: PricingRule,
                          active: bool = True) -> None:
        row = {"id": rule.id, "tenant_id": rule.tenant_id,
               "name": rule.name, "applies_to_sku": rule.applies_to_sku,
               "min_quantity": str(rule.min_quantity),
               "discount_percent": str(rule.discount_percent),
               "priority": rule.priority, "active": int(active)}
        if self.db.one("SELECT id FROM pricing_rules WHERE id=?", rule.id):
            self.db.update("pricing_rules", rule.id, row)
        else:
            self.db.insert("pricing_rules", row)

    def load_pricing_rules(self, tenant_id: str,
                           active_only: bool = True) -> list[PricingRule]:
        sql = "SELECT * FROM pricing_rules WHERE tenant_id=?"
        if active_only:
            sql += " AND active=1"
        return [PricingRule(tenant_id=r["tenant_id"], name=r["name"],
                            applies_to_sku=r["applies_to_sku"],
                            min_quantity=Decimal(r["min_quantity"]),
                            discount_percent=Decimal(r["discount_percent"]),
                            priority=r["priority"], id=r["id"])
                for r in self.db.all(sql, tenant_id)]

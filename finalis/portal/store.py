"""PortalStore — hydrates domain objects from SQL and persists them back.

The tested domain services stay untouched: the API loads a Case aggregate,
runs the same logic the 212-test core verifies, then saves the mutations.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from ..models import Case, MissingItem, Promise
from ..state_machine import CaseState
from .db import Database, utcnow


def _dt(s: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(s) if s else None


class PortalStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    # -- tenants / parties -------------------------------------------------------
    def create_tenant(self, tenant_id: str, name: str) -> None:
        self.db.insert("tenants", {"id": tenant_id, "name": name})

    def create_party(self, *, tenant_id: str, party_id: str, type_: str,
                     name: str, phone: str = "", email: str = "",
                     address: str = "") -> None:
        self.db.insert("parties", {"id": party_id, "tenant_id": tenant_id,
                                   "type": type_, "display_name": name,
                                   "phone": phone, "email": email,
                                   "address": address})

    # -- cases ---------------------------------------------------------------------
    def save_case(self, case: Case, *, title: str = "",
                  client_party_id: Optional[str] = None) -> None:
        row = {
            "id": case.id, "tenant_id": case.tenant_id, "title": title,
            "state": case.state.value,
            "client_party_id": client_party_id,
            "value_estimate": case.value_estimate,
            "lead_score": case.lead_score, "risk_score": case.risk_score,
            "autonomy_level": case.autonomy_level,
            "opted_out": int(case.opted_out),
            "autonomy_frozen_at": case.autonomy_frozen_at,
            "next_best_action": json.dumps(case.next_best_action or None),
            "next_action_due_at": case.next_action_due_at.isoformat()
            if case.next_action_due_at else None,
            "last_progress_at": case.last_progress_at.isoformat()
            if case.last_progress_at else None,
            "updated_at": utcnow(),
        }
        if self.db.one("SELECT id FROM cases WHERE id=?", case.id):
            fields = {k: v for k, v in row.items() if k != "id"}
            # Never clobber presentation fields on a plain aggregate save —
            # only overwrite title/client link when explicitly provided.
            if not title:
                fields.pop("title")
            if client_party_id is None:
                fields.pop("client_party_id")
            self.db.update("cases", case.id, fields)
        else:
            self.db.insert("cases", row)
        # Children: upsert simple (delete+insert for the aggregate's rows).
        self.db.conn.execute("DELETE FROM missing_items WHERE case_id=?",
                             (case.id,))
        for m in case.missing_items:
            self.db.insert("missing_items", {
                "id": m.id, "tenant_id": case.tenant_id, "case_id": case.id,
                "field_key": m.field_key, "label": m.label,
                "weight": m.weight, "blocks_quote": int(m.blocks_quote),
                "status": m.status})
        self.db.conn.execute("DELETE FROM promises WHERE case_id=?",
                             (case.id,))
        for p in case.promises:
            self.db.insert("promises", {
                "id": p.id, "tenant_id": case.tenant_id, "case_id": case.id,
                "promisor": p.promisor, "what": p.what,
                "due_at": p.due_at.isoformat(), "importance": p.importance,
                "dependency_impact": p.dependency_impact,
                "status": p.status})

    def load_case(self, case_id: str, *, tenant_id: str) -> Optional[Case]:
        r = self.db.one("SELECT * FROM cases WHERE id=? AND tenant_id=?",
                        case_id, tenant_id)
        if r is None:
            return None
        case = Case(tenant_id=r["tenant_id"],
                    state=CaseState(r["state"]),
                    value_estimate=r["value_estimate"],
                    lead_score=r["lead_score"], risk_score=r["risk_score"],
                    autonomy_level=r["autonomy_level"], id=r["id"])
        case.opted_out = bool(r["opted_out"])
        case.autonomy_frozen_at = r["autonomy_frozen_at"]
        nba = r["next_best_action"]
        case.next_best_action = json.loads(nba) if nba else None
        case.next_action_due_at = _dt(r["next_action_due_at"])
        case.last_progress_at = _dt(r["last_progress_at"])
        for m in self.db.all("SELECT * FROM missing_items WHERE case_id=?",
                             case_id):
            item = MissingItem(field_key=m["field_key"], label=m["label"],
                               weight=m["weight"],
                               blocks_quote=bool(m["blocks_quote"]),
                               status=m["status"], id=m["id"])
            case.missing_items.append(item)
        for p in self.db.all("SELECT * FROM promises WHERE case_id=?",
                             case_id):
            case.promises.append(Promise(
                promisor=p["promisor"], what=p["what"],
                due_at=_dt(p["due_at"]), importance=p["importance"],
                dependency_impact=p["dependency_impact"],
                status=p["status"], id=p["id"]))
        return case

    def list_cases(self, *, tenant_id: str,
                   state: Optional[str] = None) -> list[dict]:
        sql = ("SELECT c.*, p.display_name client_name FROM cases c "
               "LEFT JOIN parties p ON p.id=c.client_party_id "
               "WHERE c.tenant_id=?")
        params: list = [tenant_id]
        if state:
            sql += " AND c.state=?"
            params.append(state)
        sql += " ORDER BY c.updated_at DESC"
        return [dict(r) for r in self.db.all(sql, *params)]

    def case_meta(self, case_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT c.*, p.display_name client_name, p.phone client_phone "
            "FROM cases c LEFT JOIN parties p ON p.id=c.client_party_id "
            "WHERE c.id=? AND c.tenant_id=?", case_id, tenant_id)
        return dict(r) if r else None

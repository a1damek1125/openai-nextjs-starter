"""Seed the demo tenant: owner login + realistic HVAC cases.

Usage: python3 -m finalis.portal.seed [db_path]
Demo login: owner@demo.finalis / demo1234 (also manager@/operator@/viewer@).
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta

from ..models import Case, MissingItem, Promise
from ..state_machine import CaseState
from .auth import AuthService
from .db import Database, DbAuditLog
from .store import PortalStore

DEMO_TENANT = "demo-hvac"


def seed(db: Database) -> dict:
    store = PortalStore(db)
    audit = DbAuditLog(db, tenant_id=DEMO_TENANT)
    auth = AuthService(db)
    if db.one("SELECT id FROM tenants WHERE id=?", DEMO_TENANT):
        return {"seeded": False, "reason": "already seeded"}

    store.create_tenant(DEMO_TENANT, "Demo HVAC Sp. z o.o.")
    users = {}
    for role in ("owner", "manager", "operator", "viewer"):
        users[role] = auth.create_user(
            tenant_id=DEMO_TENANT, email=f"{role}@demo.finalis",
            password="demo1234", role=role,
            display_name=role.capitalize())
    # A second tenant to prove isolation.
    store.create_tenant("other-tenant", "Other Co")
    auth.create_user(tenant_id="other-tenant", email="owner@other.finalis",
                     password="demo1234", role="owner")

    now = datetime.utcnow()
    cases = []

    def mk(title, client, phone, state, value, lead, days_stalled=0,
           missing=(), promise=None, offer_sent_days=None):
        pid = str(uuid.uuid4())
        store.create_party(tenant_id=DEMO_TENANT, party_id=pid,
                           type_="client", name=client, phone=phone)
        c = Case(tenant_id=DEMO_TENANT, state=state, value_estimate=value,
                 lead_score=lead, autonomy_level=3)
        c.next_best_action = {"type": "review_case"}
        c.next_action_due_at = now + timedelta(hours=4)
        c.last_progress_at = now - timedelta(days=days_stalled)
        for key, blocks in missing:
            c.missing_items.append(MissingItem(
                field_key=key, label=key, weight=0.9, blocks_quote=blocks))
        if promise:
            c.promises.append(Promise(
                promisor="client", what=promise,
                due_at=now - timedelta(hours=12), importance=.7,
                dependency_impact=.8))
        store.save_case(c, title=title, client_party_id=pid)
        if offer_sent_days is not None:
            db.update("cases", c.id, {"offer_sent_at": (
                now - timedelta(days=offer_sent_days)).isoformat()})
        audit.append(event_type="CASE_CREATED", actor="seed",
                     case_id=c.id, payload={"title": title})
        cases.append(c.id)
        return c

    mk("Heat pump install", "Jan Kowalski", "+48600100200",
       CaseState.OFFER_SENT, 12000, 82, days_stalled=3, offer_sent_days=3)
    mk("AC replacement", "Anna Nowak", "+48600100201",
       CaseState.WAITING_FOR_DOCUMENTS, 6000, 55, days_stalled=8,
       missing=[("installation_photo", True), ("address", True)],
       promise="send photos")
    mk("Boiler service", "Piotr Wiśniewski", "+48600100202",
       CaseState.INTAKE_IN_PROGRESS, 3000, 45)
    mk("Split AC x2 (won)", "Firma XYZ", "+48600100203",
       CaseState.WON, 9000, 70)
    return {"seeded": True, "tenant": DEMO_TENANT, "cases": cases,
            "login": "owner@demo.finalis / demo1234"}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "finalis-dev.db"
    print(seed(Database(path)))

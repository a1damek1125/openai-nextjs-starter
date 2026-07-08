"""Persistence for the Human Approval Gate Foundation (CORE-A4.1)."""
from __future__ import annotations

import json
from typing import Optional

from ..portal.db import Database


class AIApprovalStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, row: dict) -> None:
        self.db.insert("ai_approval_requests", row)

    def get(self, approval_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one("SELECT * FROM ai_approval_requests WHERE id=? AND "
                        "tenant_id=?", approval_id, tenant_id)
        return dict(r) if r else None

    def list(self, *, tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT * FROM ai_approval_requests WHERE tenant_id=? ORDER BY "
            "created_at", tenant_id)]

    def payload(self, approval_id: str, *, tenant_id: str) -> Optional[dict]:
        row = self.get(approval_id, tenant_id=tenant_id)
        return json.loads(row["payload_json"]) if row else None

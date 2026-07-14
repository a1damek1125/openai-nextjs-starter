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

    def update_payload(self, approval_id: str, *, tenant_id: str,
                       payload: dict, status: str, updated_at: str) -> None:
        self.db.conn.execute(
            "UPDATE ai_approval_requests SET payload_json=?, "
            "approval_status=?, updated_at=? WHERE id=? AND tenant_id=?",
            (json.dumps(payload), status, updated_at, approval_id, tenant_id))
        self.db.conn.commit()


class AIApprovalDecisionStore:
    def __init__(self, db) -> None:
        self.db = db

    def save(self, row: dict) -> None:
        self.db.insert("ai_approval_decisions", row)

    def list_for_request(self, approval_request_id: str, *,
                         tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_approval_decisions WHERE "
            "approval_request_id=? AND tenant_id=? ORDER BY created_at",
            approval_request_id, tenant_id)]

    def get_decision(self, decision_id: str, *,
                     tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_approval_decisions WHERE id=? AND "
            "tenant_id=?", decision_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def latest_hash(self, approval_request_id: str, *,
                    tenant_id: str) -> Optional[str]:
        r = self.db.one(
            "SELECT decision_hash FROM ai_approval_decisions WHERE "
            "approval_request_id=? AND tenant_id=? ORDER BY created_at DESC "
            "LIMIT 1", approval_request_id, tenant_id)
        return r["decision_hash"] if r else None


class AIApprovalGrantStore:
    def __init__(self, db) -> None:
        self.db = db

    def save(self, row: dict) -> None:
        self.db.insert("ai_approval_grants", row)

    def get_for_request(self, approval_request_id: str, *,
                        tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_approval_grants WHERE "
            "approval_request_id=? AND tenant_id=? ORDER BY created_at DESC "
            "LIMIT 1", approval_request_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def get_row(self, grant_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one("SELECT * FROM ai_approval_grants WHERE id=? AND "
                        "tenant_id=?", grant_id, tenant_id)
        return dict(r) if r else None

    def active_for_scope(self, *, tenant_id: str, run_id: str, task_id: str,
                         action_type: str, exclude_id: str) -> list[dict]:
        rows = self.db.all(
            "SELECT id, payload_json FROM ai_approval_grants WHERE "
            "tenant_id=? AND run_id=? AND task_id=? AND approval_action_type=? "
            "AND id!=? AND revoked_at IS NULL AND superseded_at IS NULL AND "
            "consumed_at IS NULL", tenant_id, run_id, task_id, action_type,
            exclude_id)
        return [dict(r) for r in rows]

    def update(self, grant_id: str, *, tenant_id: str, payload: dict,
               status: str, updated_at: str, **cols) -> None:
        sets = ["payload_json=?", "grant_status=?", "updated_at=?"]
        vals = [json.dumps(payload), status, updated_at]
        for k, v in cols.items():
            sets.append(f"{k}=?")
            vals.append(v)
        vals.extend([grant_id, tenant_id])
        self.db.conn.execute(
            f"UPDATE ai_approval_grants SET {', '.join(sets)} WHERE id=? AND "
            "tenant_id=?", tuple(vals))
        self.db.conn.commit()

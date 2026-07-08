"""Persistence for the ViktorAI Lifecycle Kernel transition ledger (CORE-A5).

Append-only, tenant-scoped. Stores the deterministic transition records that
drive lifecycle state; it never executes the underlying task action.
"""
from __future__ import annotations

import json
from typing import Optional


class AITaskTransitionStore:
    def __init__(self, db) -> None:
        self.db = db

    def save(self, row: dict) -> None:
        self.db.insert("ai_task_transitions", row)

    def list(self, task_id: str, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_task_transitions WHERE task_id=? AND "
            "tenant_id=? ORDER BY transition_index", task_id, tenant_id)]

    def applied(self, task_id: str, *, tenant_id: str) -> list[dict]:
        return [t for t in self.list(task_id, tenant_id=tenant_id)
                if t.get("transition_status") == "ALLOWED"]

    def next_index(self, task_id: str, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(transition_index) m FROM ai_task_transitions WHERE "
            "task_id=? AND tenant_id=?", task_id, tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 0

    def latest(self, task_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_task_transitions WHERE task_id=? AND "
            "tenant_id=? ORDER BY transition_index DESC LIMIT 1",
            task_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def latest_applied(self, task_id: str, *, tenant_id: str) -> Optional[dict]:
        rows = self.applied(task_id, tenant_id=tenant_id)
        return rows[-1] if rows else None

    def find_by_idempotency(self, task_id: str, *, tenant_id: str,
                            key: str) -> Optional[dict]:
        if not key:
            return None
        r = self.db.one(
            "SELECT payload_json FROM ai_task_transitions WHERE task_id=? AND "
            "tenant_id=? AND transition_idempotency_key=? ORDER BY "
            "transition_index DESC LIMIT 1", task_id, tenant_id, key)
        return json.loads(r["payload_json"]) if r else None

"""Persistence for the Secure Work Intake Registry (CORE-A2)."""
from __future__ import annotations

import json
import uuid
from typing import Optional

from ..portal.db import Database, utcnow


class AITaskStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, row: dict) -> None:
        self.db.insert("ai_tasks", row)

    def get(self, task_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one("SELECT * FROM ai_tasks WHERE id=? AND tenant_id=?",
                        task_id, tenant_id)
        return dict(r) if r else None

    def list(self, *, tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT * FROM ai_tasks WHERE tenant_id=? ORDER BY created_at",
            tenant_id)]

    def find_by_idempotency(self, *, tenant_id: str, requester_user_id: str,
                            idempotency_key: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT * FROM ai_tasks WHERE tenant_id=? AND requester_user_id=? "
            "AND idempotency_key=? ORDER BY created_at DESC LIMIT 1",
            tenant_id, requester_user_id, idempotency_key)
        return dict(r) if r else None

    def update(self, task_id: str, fields: dict, *,
               tenant_id: Optional[str] = None) -> None:
        # Defense-in-depth: scope the write to the tenant when known, so a
        # mutation can never touch another tenant's row even if a caller
        # forgot the prior tenant-scoped load.
        if tenant_id is not None:
            sets = ", ".join(f"{k}=?" for k in fields)
            self.db.conn.execute(
                f"UPDATE ai_tasks SET {sets} WHERE id=? AND tenant_id=?",
                (*fields.values(), task_id, tenant_id))
            self.db.conn.commit()
        else:
            self.db.update("ai_tasks", task_id, fields)

    # -- append-only intake events ---------------------------------------------
    def add_event(self, *, task_id: str, tenant_id: str, actor_id: str,
                  actor_type: str, event_type: str, reason: str = "",
                  metadata: Optional[dict] = None) -> None:
        self.db.insert("ai_task_intake_events", {
            "id": str(uuid.uuid4()), "task_id": task_id,
            "tenant_id": tenant_id, "actor_id": actor_id,
            "actor_type": actor_type, "event_type": event_type,
            "reason": reason, "metadata_json": json.dumps(metadata or {}),
            "created_at": utcnow()})

    def events(self, task_id: str, *, tenant_id: str) -> list[dict]:
        return [{"event_id": r["id"], "task_id": r["task_id"],
                 "tenant_id": r["tenant_id"], "actor_id": r["actor_id"],
                 "actor_type": r["actor_type"], "event_type": r["event_type"],
                 "reason": r["reason"],
                 "metadata": json.loads(r["metadata_json"]),
                 "created_at": r["created_at"]}
                for r in self.db.all(
                    "SELECT * FROM ai_task_intake_events WHERE task_id=? AND "
                    "tenant_id=? ORDER BY created_at", task_id, tenant_id)]

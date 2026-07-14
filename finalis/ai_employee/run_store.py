"""Persistence for the Run Ledger (CORE-A3). Append-only run events."""
from __future__ import annotations

import json
from typing import Optional

from ..portal.db import Database


class AIRunStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    # -- runs ------------------------------------------------------------------
    def save_run(self, row: dict) -> None:
        self.db.insert("ai_runs", row)

    def get_run(self, run_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one("SELECT * FROM ai_runs WHERE id=? AND tenant_id=?",
                        run_id, tenant_id)
        return dict(r) if r else None

    def list_runs(self, *, tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT * FROM ai_runs WHERE tenant_id=? ORDER BY created_at",
            tenant_id)]

    def update_run(self, run_id: str, fields: dict, *, tenant_id: str) -> None:
        sets = ", ".join(f"{k}=?" for k in fields)
        self.db.conn.execute(
            f"UPDATE ai_runs SET {sets} WHERE id=? AND tenant_id=?",
            (*fields.values(), run_id, tenant_id))
        self.db.conn.commit()

    # -- events (append-only) --------------------------------------------------
    def add_event(self, *, run_id: str, tenant_id: str, task_id: str,
                  envelope: dict, created_at: str) -> None:
        self.db.insert("ai_run_events", {
            "id": envelope["event_id"], "run_id": run_id,
            "tenant_id": tenant_id, "task_id": task_id,
            "event_index": envelope["event_index"],
            "event_type": envelope["event_type"],
            "event_status": envelope["event_status"],
            "previous_event_hash": envelope["previous_event_hash"],
            "event_hash": envelope["event_hash"],
            "envelope_json": json.dumps(envelope), "created_at": created_at})

    def events(self, run_id: str, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["envelope_json"]) for r in self.db.all(
            "SELECT * FROM ai_run_events WHERE run_id=? AND tenant_id=? "
            "ORDER BY event_index", run_id, tenant_id)]

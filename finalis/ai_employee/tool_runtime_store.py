"""Persistence for the ViktorAI Verifiable Read-Path Runtime Microkernel
(TOOL-B6).

Runtime requests + read-only runtime outcomes + frozen local snapshots + an
append-only, hash-chained runtime event ledger, all tenant-scoped. It records
local read-only results only; it performs no external effect.
"""
from __future__ import annotations

import json
from typing import Optional


class ToolRuntimeStore:
    def __init__(self, db) -> None:
        self.db = db

    # -- snapshots (frozen, local) -------------------------------------------
    def save_snapshot(self, row: dict) -> None:
        self.db.insert("ai_runtime_snapshots", row)

    def snapshot(self, snapshot_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_runtime_snapshots WHERE id=? AND "
            "tenant_id=?", snapshot_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def list_snapshots(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_runtime_snapshots WHERE tenant_id=? "
            "ORDER BY created_at", tenant_id)]

    # -- runtime requests -----------------------------------------------------
    def save_request(self, row: dict) -> None:
        self.db.insert("ai_runtime_requests", row)

    def request(self, runtime_request_id: str, *,
                tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_runtime_requests WHERE id=? AND "
            "tenant_id=?", runtime_request_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def list_requests(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_runtime_requests WHERE tenant_id=? "
            "ORDER BY created_at", tenant_id)]

    # -- runtime outcomes -----------------------------------------------------
    def save_outcome(self, row: dict) -> None:
        self.db.insert("ai_runtime_outcomes", row)

    def outcome(self, runtime_request_id: str, *,
                tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_runtime_outcomes WHERE "
            "runtime_request_id=? AND tenant_id=? ORDER BY created_at DESC "
            "LIMIT 1", runtime_request_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def list_outcomes(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_runtime_outcomes WHERE tenant_id=? "
            "ORDER BY created_at", tenant_id)]

    def outcomes_for_snapshot(self, snapshot_id: str, *,
                              tenant_id: str) -> list[dict]:
        if not snapshot_id:
            return []
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_runtime_outcomes WHERE tenant_id=? "
            "AND snapshot_id=? ORDER BY created_at", tenant_id, snapshot_id)]

    # -- runtime event ledger (append-only, hash-chained) --------------------
    def append_event(self, row: dict) -> None:
        self.db.insert("ai_runtime_events", row)

    def events(self, *, tenant_id: str,
               runtime_request_id: Optional[str] = None) -> list[dict]:
        if runtime_request_id:
            rows = self.db.all(
                "SELECT payload_json FROM ai_runtime_events WHERE tenant_id=? "
                "AND runtime_request_id=? ORDER BY sequence", tenant_id,
                runtime_request_id)
        else:
            rows = self.db.all(
                "SELECT payload_json FROM ai_runtime_events WHERE tenant_id=? "
                "ORDER BY sequence", tenant_id)
        return [json.loads(r["payload_json"]) for r in rows]

    def last_event(self, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_runtime_events WHERE tenant_id=? "
            "ORDER BY sequence DESC LIMIT 1", tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def next_sequence(self, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(sequence) m FROM ai_runtime_events WHERE tenant_id=?",
            tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

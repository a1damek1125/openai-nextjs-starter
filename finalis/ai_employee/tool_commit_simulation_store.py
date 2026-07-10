"""Persistence for the ViktorAI Machine-Checkable Pre-B9 Assurance Envelope /
Local Commit Simulator (TOOL-B8).

Commit-simulation requests + simulation-only pre-B9 assurance outcomes + an
append-only, hash-chained event ledger, all tenant-scoped. It records local
evidence only; it performs NO real commit, NO effect release, NO commitment/B9
activation and NO external effect.
"""
from __future__ import annotations

import json
from typing import Optional


class ToolCommitSimulationStore:
    def __init__(self, db) -> None:
        self.db = db

    # -- requests ------------------------------------------------------------
    def save_request(self, row: dict) -> None:
        self.db.insert("ai_commit_simulation_requests", row)

    def request(self, commit_simulation_id: str, *,
                tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_commit_simulation_requests WHERE id=? "
            "AND tenant_id=?", commit_simulation_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def list_requests(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_commit_simulation_requests WHERE "
            "tenant_id=? ORDER BY created_at", tenant_id)]

    # -- outcomes ------------------------------------------------------------
    def save_outcome(self, row: dict) -> None:
        self.db.insert("ai_commit_simulation_outcomes", row)

    def outcome(self, commit_simulation_id: str, *,
                tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_commit_simulation_outcomes WHERE "
            "commit_simulation_id=? AND tenant_id=? ORDER BY created_at DESC "
            "LIMIT 1", commit_simulation_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def list_outcomes(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_commit_simulation_outcomes WHERE "
            "tenant_id=? ORDER BY created_at", tenant_id)]

    # -- event ledger (append-only, hash-chained) ----------------------------
    def append_event(self, row: dict) -> None:
        self.db.insert("ai_commit_simulation_events", row)

    def events(self, *, tenant_id: str,
               commit_simulation_id: Optional[str] = None) -> list[dict]:
        if commit_simulation_id:
            rows = self.db.all(
                "SELECT payload_json FROM ai_commit_simulation_events WHERE "
                "tenant_id=? AND commit_simulation_id=? ORDER BY sequence",
                tenant_id, commit_simulation_id)
        else:
            rows = self.db.all(
                "SELECT payload_json FROM ai_commit_simulation_events WHERE "
                "tenant_id=? ORDER BY sequence", tenant_id)
        return [json.loads(r["payload_json"]) for r in rows]

    def last_event(self, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_commit_simulation_events WHERE "
            "tenant_id=? ORDER BY sequence DESC LIMIT 1", tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def next_sequence(self, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(sequence) m FROM ai_commit_simulation_events WHERE "
            "tenant_id=?", tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

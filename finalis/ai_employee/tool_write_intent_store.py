"""Persistence for the ViktorAI Transaction-Escrow Write-Intent Draft Runtime
(TOOL-B7).

Write-intent draft requests + draft-only escrowed outcomes + an append-only,
hash-chained write-intent event ledger, all tenant-scoped. It records local
draft/escrow evidence only; it performs NO write, NO commit, NO effect release,
NO commitment activation and NO external effect.
"""
from __future__ import annotations

import json
from typing import Optional


class ToolWriteIntentStore:
    def __init__(self, db) -> None:
        self.db = db

    # -- write-intent requests -----------------------------------------------
    def save_request(self, row: dict) -> None:
        self.db.insert("ai_write_intent_requests", row)

    def request(self, write_intent_id: str, *,
                tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_write_intent_requests WHERE id=? AND "
            "tenant_id=?", write_intent_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def list_requests(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_write_intent_requests WHERE "
            "tenant_id=? ORDER BY created_at", tenant_id)]

    # -- write-intent outcomes -----------------------------------------------
    def save_outcome(self, row: dict) -> None:
        self.db.insert("ai_write_intent_outcomes", row)

    def outcome(self, write_intent_id: str, *,
                tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_write_intent_outcomes WHERE "
            "write_intent_id=? AND tenant_id=? ORDER BY created_at DESC "
            "LIMIT 1", write_intent_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def list_outcomes(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_write_intent_outcomes WHERE "
            "tenant_id=? ORDER BY created_at", tenant_id)]

    def outcomes_for_entity(self, entity_id: str, *,
                            tenant_id: str) -> list[dict]:
        if not entity_id:
            return []
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_write_intent_outcomes WHERE "
            "tenant_id=? AND target_entity_id=? ORDER BY created_at",
            tenant_id, entity_id)]

    # -- event ledger (append-only, hash-chained) ----------------------------
    def append_event(self, row: dict) -> None:
        self.db.insert("ai_write_intent_events", row)

    def events(self, *, tenant_id: str,
               write_intent_id: Optional[str] = None) -> list[dict]:
        if write_intent_id:
            rows = self.db.all(
                "SELECT payload_json FROM ai_write_intent_events WHERE "
                "tenant_id=? AND write_intent_id=? ORDER BY sequence",
                tenant_id, write_intent_id)
        else:
            rows = self.db.all(
                "SELECT payload_json FROM ai_write_intent_events WHERE "
                "tenant_id=? ORDER BY sequence", tenant_id)
        return [json.loads(r["payload_json"]) for r in rows]

    def last_event(self, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_write_intent_events WHERE tenant_id=? "
            "ORDER BY sequence DESC LIMIT 1", tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def next_sequence(self, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(sequence) m FROM ai_write_intent_events WHERE "
            "tenant_id=?", tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

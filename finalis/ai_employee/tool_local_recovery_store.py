"""Persistence for the Recovery Safety Case + Chaos Sentinel + Proof-of-Recovery
Runtime (TOOL-B9.1 v4).

Recovery requests + outcomes + an append-only, hash-chained B9.1 recovery event
ledger, all tenant-scoped. It records LOCAL recovery/rollback/abort/quarantine/
stuck/crash-drill evidence only; it performs NO external effect, NO provider
call, NO message/payment/CRM/evidence mutation, and never releases the inert
outbox. Recovery/quarantine/stuck sub-objects live in the outcome payload_json.
"""
from __future__ import annotations

import json
from typing import Optional


class ToolLocalRecoveryStore:
    def __init__(self, db) -> None:
        self.db = db

    # -- requests ------------------------------------------------------------
    def save_request(self, row: dict) -> None:
        self.db.insert("ai_local_transaction_recovery_requests", row)

    def request(self, recovery_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_local_transaction_recovery_requests "
            "WHERE id=? AND tenant_id=?", recovery_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def list_requests(self, *, tenant_id: str,
                      transaction_id: Optional[str] = None) -> list[dict]:
        if transaction_id:
            rows = self.db.all(
                "SELECT payload_json FROM "
                "ai_local_transaction_recovery_requests WHERE tenant_id=? AND "
                "transaction_id=? ORDER BY created_at", tenant_id, transaction_id)
        else:
            rows = self.db.all(
                "SELECT payload_json FROM "
                "ai_local_transaction_recovery_requests WHERE tenant_id=? "
                "ORDER BY created_at", tenant_id)
        return [json.loads(r["payload_json"]) for r in rows]

    # -- outcomes ------------------------------------------------------------
    def save_outcome(self, row: dict) -> None:
        self.db.insert("ai_local_transaction_recovery_outcomes", row)

    def outcome(self, recovery_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_local_transaction_recovery_outcomes "
            "WHERE recovery_id=? AND tenant_id=? ORDER BY created_at DESC "
            "LIMIT 1", recovery_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def outcome_for_transaction(self, transaction_id: str, *,
                                tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_local_transaction_recovery_outcomes "
            "WHERE transaction_id=? AND tenant_id=? ORDER BY created_at DESC "
            "LIMIT 1", transaction_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def list_outcomes(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_local_transaction_recovery_outcomes "
            "WHERE tenant_id=? ORDER BY created_at", tenant_id)]

    # -- event ledger (append-only, hash-chained) ----------------------------
    def append_event(self, row: dict) -> None:
        self.db.insert("ai_local_transaction_recovery_events", row)

    def events(self, *, tenant_id: str,
               recovery_id: Optional[str] = None) -> list[dict]:
        if recovery_id:
            rows = self.db.all(
                "SELECT payload_json FROM "
                "ai_local_transaction_recovery_events WHERE tenant_id=? AND "
                "recovery_id=? ORDER BY sequence", tenant_id, recovery_id)
        else:
            rows = self.db.all(
                "SELECT payload_json FROM "
                "ai_local_transaction_recovery_events WHERE tenant_id=? "
                "ORDER BY sequence", tenant_id)
        return [json.loads(r["payload_json"]) for r in rows]

    def last_event(self, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_local_transaction_recovery_events "
            "WHERE tenant_id=? ORDER BY sequence DESC LIMIT 1", tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def next_sequence(self, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(sequence) m FROM ai_local_transaction_recovery_events "
            "WHERE tenant_id=?", tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

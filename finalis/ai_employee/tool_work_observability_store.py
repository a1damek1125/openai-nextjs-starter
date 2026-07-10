"""Persistence for the Governed Work Lineage Observatory (TOOL-B9.2 v5).

Governed-work-run observation requests + outcomes + an append-only, hash-chained
B9.2 work event ledger, all tenant-scoped. It records DERIVED, LOCAL work-lineage
evidence only (read-only over B9/B9.1); it performs NO external effect, NO
provider call, NO message/payment/CRM/evidence mutation, and never releases the
inert outbox. Lineage sub-objects (origin, principal, memory, approval, gateway,
artifact DAG, PoWO, twin, ...) are stored in the outcome payload_json.
"""
from __future__ import annotations

import json
from typing import Optional


class ToolWorkObservabilityStore:
    def __init__(self, db) -> None:
        self.db = db

    # -- requests ------------------------------------------------------------
    def save_request(self, row: dict) -> None:
        self.db.insert("ai_governed_work_runs", row)

    def request(self, work_run_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_governed_work_runs WHERE id=? AND "
            "tenant_id=?", work_run_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def list_requests(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_governed_work_runs WHERE tenant_id=? "
            "ORDER BY created_at", tenant_id)]

    # -- outcomes ------------------------------------------------------------
    def save_outcome(self, row: dict) -> None:
        self.db.insert("ai_work_outcome_proofs", row)

    def outcome(self, work_run_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_work_outcome_proofs WHERE "
            "work_run_id=? AND tenant_id=? ORDER BY created_at DESC LIMIT 1",
            work_run_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def list_outcomes(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_work_outcome_proofs WHERE tenant_id=? "
            "ORDER BY created_at", tenant_id)]

    # -- event ledger (append-only, hash-chained) ----------------------------
    def append_event(self, row: dict) -> None:
        self.db.insert("ai_work_lineage_events", row)

    def events(self, *, tenant_id: str,
               work_run_id: Optional[str] = None) -> list[dict]:
        if work_run_id:
            rows = self.db.all(
                "SELECT payload_json FROM ai_work_lineage_events WHERE "
                "tenant_id=? AND work_run_id=? ORDER BY sequence", tenant_id,
                work_run_id)
        else:
            rows = self.db.all(
                "SELECT payload_json FROM ai_work_lineage_events WHERE "
                "tenant_id=? ORDER BY sequence", tenant_id)
        return [json.loads(r["payload_json"]) for r in rows]

    def last_event(self, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_work_lineage_events WHERE tenant_id=? "
            "ORDER BY sequence DESC LIMIT 1", tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def next_sequence(self, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(sequence) m FROM ai_work_lineage_events WHERE "
            "tenant_id=?", tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

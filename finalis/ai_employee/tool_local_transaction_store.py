"""Persistence for the Finalis Transaction Twin + Proof-of-Execution Runtime
(TOOL-B9 v5).

Local-transaction requests + outcomes + an append-only, hash-chained B9 event
ledger + a LOCAL, REVERSIBLE per-target state store, all tenant-scoped. It
commits only to local internal state; it performs NO external effect, NO
provider call, NO message/payment/CRM/evidence mutation.
"""
from __future__ import annotations

import json
from typing import Optional


class ToolLocalTransactionStore:
    def __init__(self, db) -> None:
        self.db = db

    # -- requests ------------------------------------------------------------
    def save_request(self, row: dict) -> None:
        self.db.insert("ai_local_transactions", row)

    def request(self, transaction_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_local_transactions WHERE id=? AND "
            "tenant_id=?", transaction_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def list_requests(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_local_transactions WHERE tenant_id=? "
            "ORDER BY created_at", tenant_id)]

    # -- outcomes ------------------------------------------------------------
    def save_outcome(self, row: dict) -> None:
        self.db.insert("ai_local_transaction_outcomes", row)

    def outcome(self, transaction_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_local_transaction_outcomes WHERE "
            "transaction_id=? AND tenant_id=? ORDER BY created_at DESC LIMIT 1",
            transaction_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def list_outcomes(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_local_transaction_outcomes WHERE "
            "tenant_id=? ORDER BY created_at", tenant_id)]

    # -- local reversible state (per target) ---------------------------------
    def get_state(self, object_reference: str, *,
                  tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT state_json, version, before_state_json, last_transaction_id "
            "FROM ai_local_transaction_state WHERE tenant_id=? AND "
            "object_reference=?", tenant_id, object_reference)
        if not r:
            return None
        return {"state": json.loads(r["state_json"]), "version": r["version"],
                "before_state": json.loads(r["before_state_json"] or "{}"),
                "last_transaction_id": r["last_transaction_id"]}

    def apply_commit(self, *, tenant_id: str, object_reference: str,
                     before_state: dict, after_state: dict, transaction_id: str,
                     created_at: str) -> int:
        """Apply a LOCAL, REVERSIBLE commit: upsert the target's state,
        recording the prior state so the transaction can be rolled back. No
        external effect. Returns the new version."""
        cur = self.get_state(object_reference, tenant_id=tenant_id)
        version = (cur["version"] + 1) if cur else 1
        if cur:
            self.db.conn.execute(
                "UPDATE ai_local_transaction_state SET state_json=?, "
                "before_state_json=?, version=?, last_transaction_id=?, "
                "updated_at=? WHERE tenant_id=? AND object_reference=?",
                (json.dumps(after_state), json.dumps(before_state), version,
                 transaction_id, created_at, tenant_id, object_reference))
        else:
            self.db.insert("ai_local_transaction_state", {
                "id": tenant_id + ":" + object_reference,
                "tenant_id": tenant_id, "object_reference": object_reference,
                "state_json": json.dumps(after_state),
                "before_state_json": json.dumps(before_state),
                "version": version, "last_transaction_id": transaction_id,
                "updated_at": created_at})
        self.db.conn.commit()
        return version

    # -- event ledger (append-only, hash-chained) ----------------------------
    def append_event(self, row: dict) -> None:
        self.db.insert("ai_local_transaction_events", row)

    def events(self, *, tenant_id: str,
               transaction_id: Optional[str] = None) -> list[dict]:
        if transaction_id:
            rows = self.db.all(
                "SELECT payload_json FROM ai_local_transaction_events WHERE "
                "tenant_id=? AND transaction_id=? ORDER BY sequence",
                tenant_id, transaction_id)
        else:
            rows = self.db.all(
                "SELECT payload_json FROM ai_local_transaction_events WHERE "
                "tenant_id=? ORDER BY sequence", tenant_id)
        return [json.loads(r["payload_json"]) for r in rows]

    def last_event(self, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_local_transaction_events WHERE "
            "tenant_id=? ORDER BY sequence DESC LIMIT 1", tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def next_sequence(self, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(sequence) m FROM ai_local_transaction_events WHERE "
            "tenant_id=?", tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

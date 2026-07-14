"""Persistence for the Employee Work Inbox — R-FSAFEQ Governed Work Admission
Fabric (EMP-A1 v1).

Tenant-isolated work items + append-only hash-chained work-event ledger +
bundles + fenced claims + flow state (bounded calibration/risk/backlog/fairness)
+ admission receipts + single-use EMP-A2 handoff capabilities + inbox policies.

Admission is committed serializably: the write transaction begins BEFORE
admission-dependent reads (SQLite BEGIN IMMEDIATE-equivalent), and a serialization
retry rolls back the FULL attempt (no event, no receipt, no charge). It performs
NO external effect, creates NO EMP-A2 run, starts NO TOOL-B9 transaction, and
never releases an outbox. Sub-objects live in payload_json.
"""
from __future__ import annotations

import json
from typing import Optional


class EmployeeWorkInboxStore:
    def __init__(self, db) -> None:
        self.db = db

    # -- serializable admission boundary -------------------------------------
    def begin_immediate(self):
        """Begin the admission write transaction before admission-dependent
        reads (SQLite BEGIN IMMEDIATE-equivalent; PostgreSQL adapter uses
        SERIALIZABLE)."""
        try:
            self.db.conn.execute("BEGIN IMMEDIATE")
        except Exception:
            pass  # a transaction is already open; the outer commit still applies

    def commit(self):
        self.db.conn.commit()

    def rollback(self):
        try:
            self.db.conn.rollback()
        except Exception:
            pass

    # -- work items ----------------------------------------------------------
    def save_item(self, row: dict) -> None:
        self.db.insert("ai_employee_work_items", row)

    def item(self, work_item_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_employee_work_items WHERE id=? AND "
            "tenant_id=?", work_item_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def item_by_idempotency(self, *, tenant_id: str,
                            idempotency_key: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_employee_work_items WHERE tenant_id=? "
            "AND idempotency_key=? ORDER BY created_sequence LIMIT 1",
            tenant_id, idempotency_key)
        return json.loads(r["payload_json"]) if r else None

    def update_item(self, work_item_id: str, *, tenant_id: str,
                    row: dict) -> None:
        self.db.conn.execute(
            "UPDATE ai_employee_work_items SET work_item_state=?, "
            "work_item_version=?, work_item_hash=?, payload_json=?, updated_at=? "
            "WHERE id=? AND tenant_id=?",
            (row["work_item_state"], row["work_item_version"],
             row["work_item_hash"], json.dumps(row["payload"]),
             row["updated_at"], work_item_id, tenant_id))

    def list_items(self, *, tenant_id: str, state: Optional[str] = None,
                   limit: int = 100, after_sequence: int = 0) -> list[dict]:
        if state:
            rows = self.db.all(
                "SELECT payload_json FROM ai_employee_work_items WHERE "
                "tenant_id=? AND work_item_state=? AND created_sequence>? "
                "ORDER BY created_sequence LIMIT ?", tenant_id, state,
                after_sequence, limit)
        else:
            rows = self.db.all(
                "SELECT payload_json FROM ai_employee_work_items WHERE "
                "tenant_id=? AND created_sequence>? ORDER BY created_sequence "
                "LIMIT ?", tenant_id, after_sequence, limit)
        return [json.loads(r["payload_json"]) for r in rows]

    def counts_by_state(self, *, tenant_id: str) -> dict:
        rows = self.db.all(
            "SELECT work_item_state s, COUNT(*) c FROM ai_employee_work_items "
            "WHERE tenant_id=? GROUP BY work_item_state", tenant_id)
        return {r["s"]: r["c"] for r in rows}

    def next_created_sequence(self, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(created_sequence) m FROM ai_employee_work_items WHERE "
            "tenant_id=?", tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

    def recent_fingerprints(self, *, tenant_id: str, limit: int = 50) -> list:
        rows = self.db.all(
            "SELECT structural_fingerprint, source_principal_id, work_type, "
            "payload_json FROM ai_employee_work_items WHERE tenant_id=? "
            "ORDER BY created_sequence DESC LIMIT ?", tenant_id, limit)
        out = []
        for r in rows:
            p = json.loads(r["payload_json"])
            out.append({"fingerprint": r["structural_fingerprint"],
                        "principal": r["source_principal_id"],
                        "work_type": r["work_type"],
                        "targets": p.get("target_refs") or []})
        return out

    # -- events (append-only, hash-chained) ----------------------------------
    def append_event(self, row: dict) -> None:
        self.db.insert("ai_employee_work_item_events", row)

    def events(self, *, tenant_id: str,
               work_item_id: Optional[str] = None) -> list[dict]:
        if work_item_id:
            rows = self.db.all(
                "SELECT payload_json FROM ai_employee_work_item_events WHERE "
                "tenant_id=? AND work_item_id=? ORDER BY sequence", tenant_id,
                work_item_id)
        else:
            rows = self.db.all(
                "SELECT payload_json FROM ai_employee_work_item_events WHERE "
                "tenant_id=? ORDER BY sequence", tenant_id)
        return [json.loads(r["payload_json"]) for r in rows]

    def last_event(self, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_employee_work_item_events WHERE "
            "tenant_id=? ORDER BY sequence DESC LIMIT 1", tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def next_sequence(self, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(sequence) m FROM ai_employee_work_item_events WHERE "
            "tenant_id=?", tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

    def next_decision_sequence(self, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(decision_sequence) m FROM ai_employee_work_admission_"
            "receipts WHERE tenant_id=?", tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

    # -- bundles -------------------------------------------------------------
    def save_bundle(self, row: dict) -> None:
        self.db.insert("ai_employee_work_bundles", row)

    def bundle(self, bundle_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_employee_work_bundles WHERE id=? AND "
            "tenant_id=?", bundle_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    # -- claims (CAS + fencing) ----------------------------------------------
    def active_claim(self, *, tenant_id: str,
                     work_item_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_employee_work_claims WHERE tenant_id=? "
            "AND work_item_id=? AND state='ACTIVE' ORDER BY fencing_token DESC "
            "LIMIT 1", tenant_id, work_item_id)
        return json.loads(r["payload_json"]) if r else None

    def max_fencing_token(self, *, tenant_id: str, work_item_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(fencing_token) m FROM ai_employee_work_claims WHERE "
            "tenant_id=? AND work_item_id=?", tenant_id, work_item_id)
        return (r["m"]) if r and r["m"] is not None else 0

    def save_claim(self, row: dict) -> None:
        self.db.insert("ai_employee_work_claims", row)

    def expire_claims(self, *, tenant_id: str, work_item_id: str) -> None:
        self.db.conn.execute(
            "UPDATE ai_employee_work_claims SET state='EXPIRED' WHERE "
            "tenant_id=? AND work_item_id=? AND state='ACTIVE'",
            (tenant_id, work_item_id))

    # -- flow state (bounded calibration/risk/backlog/fairness) --------------
    def flow_state(self, *, tenant_id: str, flow_key: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_employee_work_flow_state WHERE "
            "tenant_id=? AND flow_key=?", tenant_id, flow_key)
        return json.loads(r["payload_json"]) if r else None

    def upsert_flow_state(self, *, tenant_id: str, flow_key: str,
                          state: dict) -> None:
        exists = self.db.one(
            "SELECT 1 FROM ai_employee_work_flow_state WHERE tenant_id=? AND "
            "flow_key=?", tenant_id, flow_key)
        if exists:
            self.db.conn.execute(
                "UPDATE ai_employee_work_flow_state SET payload_json=?, "
                "updated_at=? WHERE tenant_id=? AND flow_key=?",
                (json.dumps(state), state.get("updated_at", ""), tenant_id,
                 flow_key))
        else:
            self.db.insert("ai_employee_work_flow_state", {
                "id": tenant_id + ":" + flow_key, "tenant_id": tenant_id,
                "flow_key": flow_key, "payload_json": json.dumps(state),
                "updated_at": state.get("updated_at", "")})

    def list_flow_state(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_employee_work_flow_state WHERE "
            "tenant_id=? ORDER BY flow_key", tenant_id)]

    # -- admission receipts --------------------------------------------------
    def save_receipt(self, row: dict) -> None:
        self.db.insert("ai_employee_work_admission_receipts", row)

    def receipt(self, *, tenant_id: str,
                work_item_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_employee_work_admission_receipts WHERE "
            "tenant_id=? AND work_item_id=? ORDER BY decision_sequence DESC "
            "LIMIT 1", tenant_id, work_item_id)
        return json.loads(r["payload_json"]) if r else None

    # -- handoff capabilities (single-use) -----------------------------------
    def save_handoff(self, row: dict) -> None:
        self.db.insert("ai_employee_work_handoff_capabilities", row)

    def active_handoff(self, *, tenant_id: str,
                       work_item_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_employee_work_handoff_capabilities "
            "WHERE tenant_id=? AND work_item_id=? AND state='PREPARED' ORDER BY "
            "issued_at DESC LIMIT 1", tenant_id, work_item_id)
        return json.loads(r["payload_json"]) if r else None

    def invalidate_handoffs(self, *, tenant_id: str,
                            work_item_id: str) -> None:
        self.db.conn.execute(
            "UPDATE ai_employee_work_handoff_capabilities SET "
            "state='INVALIDATED' WHERE tenant_id=? AND work_item_id=? AND "
            "state='PREPARED'", (tenant_id, work_item_id))

    # -- policy --------------------------------------------------------------
    def policy(self, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_employee_work_inbox_policies WHERE "
            "tenant_id=? ORDER BY created_at DESC LIMIT 1", tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def save_policy(self, row: dict) -> None:
        self.db.insert("ai_employee_work_inbox_policies", row)

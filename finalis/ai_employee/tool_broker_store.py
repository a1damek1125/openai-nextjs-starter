"""Persistence for the ViktorAI Four-Plane Proof-Carrying Null Broker (TOOL-B5).

Broker requests + null broker outcomes + an append-only, hash-chained broker
event ledger, all tenant-scoped. It records validation / null-effect outcomes
only; it executes nothing.
"""
from __future__ import annotations

import json
from typing import Optional


class ToolBrokerStore:
    def __init__(self, db) -> None:
        self.db = db

    # -- broker requests ------------------------------------------------------
    def save_request(self, row: dict) -> None:
        self.db.insert("ai_broker_requests", row)

    def request(self, broker_request_id: str, *,
                tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_broker_requests WHERE id=? AND "
            "tenant_id=?", broker_request_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def requests_for_tool(self, tool_id: str, *,
                          tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_broker_requests WHERE tool_id=? AND "
            "tenant_id=? ORDER BY created_at", tool_id, tenant_id)]

    def list_requests(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_broker_requests WHERE tenant_id=? "
            "ORDER BY created_at", tenant_id)]

    # -- broker outcomes ------------------------------------------------------
    def save_outcome(self, row: dict) -> None:
        self.db.insert("ai_broker_outcomes", row)

    def outcome(self, broker_request_id: str, *,
                tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_broker_outcomes WHERE "
            "broker_request_id=? AND tenant_id=? ORDER BY created_at DESC "
            "LIMIT 1", broker_request_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def list_outcomes(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_broker_outcomes WHERE tenant_id=? "
            "ORDER BY created_at", tenant_id)]

    def prior_outcome_for_key(self, idempotency_key: str, *, tenant_id: str,
                              exclude_request_id: str = "") -> Optional[dict]:
        """The most recent broker outcome for a given idempotency key (excluding
        the current request) — the basis for replay-conflict detection."""
        if not idempotency_key:
            return None
        rows = self.db.all(
            "SELECT id FROM ai_broker_requests WHERE tenant_id=? AND "
            "idempotency_key=? ORDER BY created_at DESC", tenant_id,
            idempotency_key)
        for r in rows:
            if r["id"] == exclude_request_id:
                continue
            o = self.outcome(r["id"], tenant_id=tenant_id)
            if o is not None:
                return o
        return None

    def related_outcomes(self, *, tenant_id: str, batch_id: str = "",
                         customer_id: str = "", task_id: str = "",
                         case_id: str = "",
                         exclude_request_id: str = "") -> list[dict]:
        """Broker outcomes correlated to a request by ANY server-derived key
        (batch / customer / task / case) — so cross-request conservation is not
        defeated simply by omitting or varying the client-supplied batch_id."""
        keys = [(col, val) for col, val in (
            ("batch_id", batch_id), ("customer_id", customer_id),
            ("task_id", task_id), ("case_id", case_id)) if val]
        if not keys:
            return []
        where = " OR ".join(f"r.{col}=?" for col, _ in keys)
        rows = self.db.all(
            "SELECT o.payload_json, o.broker_request_id FROM ai_broker_outcomes "
            "o JOIN ai_broker_requests r ON o.broker_request_id=r.id WHERE "
            f"o.tenant_id=? AND ({where}) ORDER BY o.created_at",
            tenant_id, *[val for _, val in keys])
        seen, out = set(), []
        for r in rows:
            if r["broker_request_id"] in (exclude_request_id, *seen):
                continue
            seen.add(r["broker_request_id"])
            out.append(json.loads(r["payload_json"]))
        return out

    def outcomes_for_batch(self, batch_id: str, *,
                           tenant_id: str) -> list[dict]:
        if not batch_id:
            return []
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT o.payload_json FROM ai_broker_outcomes o JOIN "
            "ai_broker_requests r ON o.broker_request_id=r.id WHERE "
            "o.tenant_id=? AND r.batch_id=? ORDER BY o.created_at",
            tenant_id, batch_id)]

    # -- broker event ledger (append-only, hash-chained) ----------------------
    def append_event(self, row: dict) -> None:
        self.db.insert("ai_broker_events", row)

    def events(self, *, tenant_id: str,
               broker_request_id: Optional[str] = None) -> list[dict]:
        if broker_request_id:
            rows = self.db.all(
                "SELECT payload_json FROM ai_broker_events WHERE tenant_id=? "
                "AND broker_request_id=? ORDER BY sequence", tenant_id,
                broker_request_id)
        else:
            rows = self.db.all(
                "SELECT payload_json FROM ai_broker_events WHERE tenant_id=? "
                "ORDER BY sequence", tenant_id)
        return [json.loads(r["payload_json"]) for r in rows]

    def last_event(self, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_broker_events WHERE tenant_id=? "
            "ORDER BY sequence DESC LIMIT 1", tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def next_sequence(self, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(sequence) m FROM ai_broker_events WHERE tenant_id=?",
            tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

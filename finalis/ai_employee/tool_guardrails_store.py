"""Persistence for the ViktorAI Causal Pre-Action Reference Monitor (TOOL-B4).

Tool Action Proposals + pre-action decisions + circuit breakers + an
append-only, hash-chained decision event ledger, all tenant-scoped. It records
governance decisions only; it executes nothing.
"""
from __future__ import annotations

import json
from typing import Optional


class ToolGuardrailStore:
    def __init__(self, db) -> None:
        self.db = db

    # -- proposals ------------------------------------------------------------
    def save_proposal(self, row: dict) -> None:
        self.db.insert("ai_action_proposals", row)

    def proposal(self, proposal_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_action_proposals WHERE id=? AND "
            "tenant_id=?", proposal_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def proposals_for_tool(self, tool_id: str, *,
                           tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_action_proposals WHERE tool_id=? AND "
            "tenant_id=? ORDER BY created_at", tool_id, tenant_id)]

    def list_proposals(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_action_proposals WHERE tenant_id=? "
            "ORDER BY created_at", tenant_id)]

    # -- decisions ------------------------------------------------------------
    def save_decision(self, row: dict) -> None:
        self.db.insert("ai_action_decisions", row)

    def decision(self, decision_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_action_decisions WHERE id=? AND "
            "tenant_id=?", decision_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def decision_for_proposal(self, proposal_id: str, *,
                              tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_action_decisions WHERE proposal_id=? "
            "AND tenant_id=? ORDER BY created_at DESC LIMIT 1", proposal_id,
            tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def decisions_for_tool(self, tool_id: str, *,
                           tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_action_decisions WHERE tool_id=? AND "
            "tenant_id=? ORDER BY created_at", tool_id, tenant_id)]

    def list_decisions(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_action_decisions WHERE tenant_id=? "
            "ORDER BY created_at", tenant_id)]

    def latest_decision_for_key(self, idempotency_key: str, *,
                                tenant_id: str) -> Optional[dict]:
        """The most recent decision for a given idempotency key — the basis for
        replay/conflict detection and the temporal automaton's prior state."""
        if not idempotency_key:
            return None
        r = self.db.one(
            "SELECT payload_json FROM ai_action_decisions WHERE tenant_id=? "
            "AND idempotency_key=? ORDER BY created_at DESC LIMIT 1",
            tenant_id, idempotency_key)
        return json.loads(r["payload_json"]) if r else None

    def count_decisions_in_window(self, *, tenant_id: str,
                                  tool_id: Optional[str] = None) -> int:
        if tool_id:
            r = self.db.one(
                "SELECT COUNT(*) n FROM ai_action_decisions WHERE tenant_id=? "
                "AND tool_id=?", tenant_id, tool_id)
        else:
            r = self.db.one(
                "SELECT COUNT(*) n FROM ai_action_decisions WHERE tenant_id=?",
                tenant_id)
        return int(r["n"]) if r else 0

    # -- circuit breakers -----------------------------------------------------
    def save_breaker(self, row: dict) -> None:
        # A breaker is keyed by (tenant, tool); upsert the latest state.
        existing = self.db.one(
            "SELECT id FROM ai_action_circuit_breakers WHERE tenant_id=? AND "
            "tool_id=?", row["tenant_id"], row["tool_id"])
        if existing:
            self.db.conn.execute(
                "UPDATE ai_action_circuit_breakers SET breaker_state=?, "
                "reason_code=?, payload_json=?, updated_at=? WHERE id=?",
                (row["breaker_state"], row["reason_code"], row["payload_json"],
                 row["updated_at"], existing["id"]))
            self.db.conn.commit()
        else:
            self.db.insert("ai_action_circuit_breakers", row)

    def breaker(self, tool_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_action_circuit_breakers WHERE "
            "tool_id=? AND tenant_id=?", tool_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def list_breakers(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_action_circuit_breakers WHERE "
            "tenant_id=? ORDER BY tool_id", tenant_id)]

    # -- decision event ledger (append-only, hash-chained) --------------------
    def append_event(self, row: dict) -> None:
        self.db.insert("ai_action_decision_events", row)

    def events(self, *, tenant_id: str,
               proposal_id: Optional[str] = None) -> list[dict]:
        if proposal_id:
            rows = self.db.all(
                "SELECT payload_json FROM ai_action_decision_events WHERE "
                "tenant_id=? AND proposal_id=? ORDER BY sequence", tenant_id,
                proposal_id)
        else:
            rows = self.db.all(
                "SELECT payload_json FROM ai_action_decision_events WHERE "
                "tenant_id=? ORDER BY sequence", tenant_id)
        return [json.loads(r["payload_json"]) for r in rows]

    def last_event(self, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_action_decision_events WHERE "
            "tenant_id=? ORDER BY sequence DESC LIMIT 1", tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def next_sequence(self, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(sequence) m FROM ai_action_decision_events WHERE "
            "tenant_id=?", tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

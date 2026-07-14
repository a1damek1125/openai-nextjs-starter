"""Persistence for the ViktorAI Formal Protocol Contract Proof Kernel
(TOOL-B3).

Contracts + contract versions + projection envelopes + an append-only contract
event ledger, all tenant-scoped. Records protocol-aware internal contracts and
validation-only projections; executes nothing.
"""
from __future__ import annotations

import json
from typing import Optional


class ToolContractStore:
    def __init__(self, db) -> None:
        self.db = db

    # -- contracts ------------------------------------------------------------
    def save(self, row: dict) -> None:
        self.db.insert("ai_tool_contracts", row)

    def get(self, contract_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT * FROM ai_tool_contracts WHERE id=? AND tenant_id=?",
            contract_id, tenant_id)
        return dict(r) if r else None

    def payload(self, contract_id: str, *, tenant_id: str) -> Optional[dict]:
        row = self.get(contract_id, tenant_id=tenant_id)
        return json.loads(row["payload_json"]) if row else None

    def for_tool(self, tool_id: str, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_tool_contracts WHERE tool_id=? AND "
            "tenant_id=? ORDER BY created_at", tool_id, tenant_id)]

    def list(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_tool_contracts WHERE tenant_id=? "
            "ORDER BY created_at", tenant_id)]

    def update(self, contract_id: str, *, tenant_id: str, payload: dict,
               **cols) -> None:
        cols["payload_json"] = json.dumps(payload)
        sets = ", ".join(f"{k}=?" for k in cols)
        self.db.conn.execute(
            f"UPDATE ai_tool_contracts SET {sets} WHERE id=? AND tenant_id=?",
            (*cols.values(), contract_id, tenant_id))
        self.db.conn.commit()

    # -- contract versions ----------------------------------------------------
    def save_version(self, row: dict) -> None:
        self.db.insert("ai_tool_contract_versions", row)

    def versions(self, contract_id: str, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_tool_contract_versions WHERE "
            "contract_id=? AND tenant_id=? ORDER BY version_number",
            contract_id, tenant_id)]

    def latest_version(self, contract_id: str, *,
                       tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_tool_contract_versions WHERE "
            "contract_id=? AND tenant_id=? ORDER BY version_number DESC LIMIT 1",
            contract_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def next_version_number(self, contract_id: str, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(version_number) m FROM ai_tool_contract_versions WHERE "
            "contract_id=? AND tenant_id=?", contract_id, tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

    # -- projections ----------------------------------------------------------
    def save_projection(self, row: dict) -> None:
        self.db.insert("ai_tool_contract_projections", row)

    def projection(self, projection_id: str, *,
                   tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_tool_contract_projections WHERE id=? "
            "AND tenant_id=?", projection_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def projections_for(self, contract_id: str, *,
                        tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_tool_contract_projections WHERE "
            "contract_id=? AND tenant_id=? ORDER BY created_at", contract_id,
            tenant_id)]

    def latest_projection_for_target(self, contract_id: str, target: str, *,
                                     tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_tool_contract_projections WHERE "
            "contract_id=? AND tenant_id=? AND projection_target=? ORDER BY "
            "created_at DESC LIMIT 1", contract_id, tenant_id, target)
        return json.loads(r["payload_json"]) if r else None

    # -- contract event ledger (append-only) ----------------------------------
    def append_event(self, row: dict) -> None:
        self.db.insert("ai_tool_contract_events", row)

    def events(self, *, tenant_id: str,
               contract_id: Optional[str] = None) -> list[dict]:
        if contract_id:
            rows = self.db.all(
                "SELECT payload_json FROM ai_tool_contract_events WHERE "
                "tenant_id=? AND contract_id=? ORDER BY sequence", tenant_id,
                contract_id)
        else:
            rows = self.db.all(
                "SELECT payload_json FROM ai_tool_contract_events WHERE "
                "tenant_id=? ORDER BY sequence", tenant_id)
        return [json.loads(r["payload_json"]) for r in rows]

    def last_event(self, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_tool_contract_events WHERE tenant_id=? "
            "ORDER BY sequence DESC LIMIT 1", tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def next_sequence(self, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(sequence) m FROM ai_tool_contract_events WHERE "
            "tenant_id=?", tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

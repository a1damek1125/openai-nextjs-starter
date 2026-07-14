"""Persistence for the ViktorAI Zero-Trust Tool Capability Governance Registry
(TOOL-B1).

Append-only descriptor versions + an append-only registry event ledger + a
mutable tool head row, all tenant-scoped. Records and governs tool capability
descriptors for a FUTURE broker; executes nothing.
"""
from __future__ import annotations

import json
from typing import Optional


class ToolRegistryStore:
    def __init__(self, db) -> None:
        self.db = db

    # -- tool head ------------------------------------------------------------
    def save(self, row: dict) -> None:
        self.db.insert("ai_tools", row)

    def get(self, tool_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one("SELECT * FROM ai_tools WHERE id=? AND tenant_id=?",
                        tool_id, tenant_id)
        return dict(r) if r else None

    def payload(self, tool_id: str, *, tenant_id: str) -> Optional[dict]:
        row = self.get(tool_id, tenant_id=tenant_id)
        return json.loads(row["payload_json"]) if row else None

    def list(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_tools WHERE tenant_id=? ORDER BY "
            "created_at", tenant_id)]

    def list_heads(self, *, tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT * FROM ai_tools WHERE tenant_id=? ORDER BY created_at",
            tenant_id)]

    def by_key(self, tool_key: str, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_tools WHERE tenant_id=? AND "
            "tool_key=? ORDER BY created_at", tenant_id, tool_key)]

    def update_head(self, tool_id: str, *, tenant_id: str, payload: dict,
                    **cols) -> None:
        cols["payload_json"] = json.dumps(payload)
        sets = ", ".join(f"{k}=?" for k in cols)
        self.db.conn.execute(
            f"UPDATE ai_tools SET {sets} WHERE id=? AND tenant_id=?",
            (*cols.values(), tool_id, tenant_id))
        self.db.conn.commit()

    # -- versions -------------------------------------------------------------
    def save_version(self, row: dict) -> None:
        self.db.insert("ai_tool_versions", row)

    def versions(self, tool_id: str, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_tool_versions WHERE tool_id=? AND "
            "tenant_id=? ORDER BY version_number", tool_id, tenant_id)]

    def version(self, tool_id: str, version_id: str, *,
                tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_tool_versions WHERE id=? AND "
            "tool_id=? AND tenant_id=?", version_id, tool_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def latest_version(self, tool_id: str, *,
                       tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_tool_versions WHERE tool_id=? AND "
            "tenant_id=? ORDER BY version_number DESC LIMIT 1",
            tool_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def next_version_number(self, tool_id: str, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(version_number) m FROM ai_tool_versions WHERE "
            "tool_id=? AND tenant_id=?", tool_id, tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

    # -- registry event ledger (append-only) ----------------------------------
    def append_event(self, row: dict) -> None:
        self.db.insert("ai_tool_registry_events", row)

    def events(self, *, tenant_id: str, tool_id: Optional[str] = None
               ) -> list[dict]:
        if tool_id:
            rows = self.db.all(
                "SELECT payload_json FROM ai_tool_registry_events WHERE "
                "tenant_id=? AND tool_id=? ORDER BY sequence", tenant_id,
                tool_id)
        else:
            rows = self.db.all(
                "SELECT payload_json FROM ai_tool_registry_events WHERE "
                "tenant_id=? ORDER BY sequence", tenant_id)
        return [json.loads(r["payload_json"]) for r in rows]

    def last_event(self, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_tool_registry_events WHERE tenant_id=? "
            "ORDER BY sequence DESC LIMIT 1", tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def next_sequence(self, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(sequence) m FROM ai_tool_registry_events WHERE "
            "tenant_id=?", tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

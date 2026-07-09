"""Persistence for the ViktorAI Formal Tool Descriptor Assurance Graph
(TOOL-B2).

Append-only quality reports (history per tool/descriptor version) + an
append-only quality binding event ledger, all tenant-scoped. Records and scores
descriptor quality; executes nothing.
"""
from __future__ import annotations

import json
from typing import Optional


class ToolQualityStore:
    def __init__(self, db) -> None:
        self.db = db

    # -- quality reports (append-only history) --------------------------------
    def save_report(self, row: dict) -> None:
        self.db.insert("ai_tool_quality_reports", row)

    def latest(self, tool_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_tool_quality_reports WHERE tool_id=? "
            "AND tenant_id=? ORDER BY seq DESC LIMIT 1", tool_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def latest_for_version(self, tool_id: str, tool_version_id: str, *,
                           tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_tool_quality_reports WHERE tool_id=? "
            "AND tool_version_id=? AND tenant_id=? ORDER BY seq DESC LIMIT 1",
            tool_id, tool_version_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def history(self, tool_id: str, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_tool_quality_reports WHERE tool_id=? "
            "AND tenant_id=? ORDER BY seq", tool_id, tenant_id)]

    def report(self, report_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_tool_quality_reports WHERE id=? AND "
            "tenant_id=?", report_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def next_seq(self, tool_id: str, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(seq) m FROM ai_tool_quality_reports WHERE tool_id=? AND "
            "tenant_id=?", tool_id, tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

    def all_latest(self, *, tenant_id: str) -> list[dict]:
        """Latest report per tool for the tenant (registry quality summary)."""
        rows = self.db.all(
            "SELECT tool_id, MAX(seq) ms FROM ai_tool_quality_reports WHERE "
            "tenant_id=? GROUP BY tool_id", tenant_id)
        out = []
        for r in rows:
            rec = self.db.one(
                "SELECT payload_json FROM ai_tool_quality_reports WHERE "
                "tool_id=? AND tenant_id=? AND seq=?", r["tool_id"], tenant_id,
                r["ms"])
            if rec:
                out.append(json.loads(rec["payload_json"]))
        return out

    # -- quality binding event ledger (append-only) ---------------------------
    def append_event(self, row: dict) -> None:
        self.db.insert("ai_tool_quality_events", row)

    def events(self, *, tenant_id: str, tool_id: Optional[str] = None
               ) -> list[dict]:
        if tool_id:
            rows = self.db.all(
                "SELECT payload_json FROM ai_tool_quality_events WHERE "
                "tenant_id=? AND tool_id=? ORDER BY sequence", tenant_id,
                tool_id)
        else:
            rows = self.db.all(
                "SELECT payload_json FROM ai_tool_quality_events WHERE "
                "tenant_id=? ORDER BY sequence", tenant_id)
        return [json.loads(r["payload_json"]) for r in rows]

    def last_event(self, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_tool_quality_events WHERE tenant_id=? "
            "ORDER BY sequence DESC LIMIT 1", tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def next_sequence(self, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(sequence) m FROM ai_tool_quality_events WHERE "
            "tenant_id=?", tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

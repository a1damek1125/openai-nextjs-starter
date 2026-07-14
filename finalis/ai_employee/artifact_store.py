"""Persistence for the ViktorAI Artifact System (CORE-A6).

Append-only versions + a mutable artifact head row, all tenant-scoped. Records
and versions work products; executes nothing.
"""
from __future__ import annotations

import json
from typing import Optional


class AIArtifactStore:
    def __init__(self, db) -> None:
        self.db = db

    # -- artifact head --------------------------------------------------------
    def save(self, row: dict) -> None:
        self.db.insert("ai_artifacts", row)

    def get(self, artifact_id: str, *, tenant_id: str) -> Optional[dict]:
        r = self.db.one("SELECT * FROM ai_artifacts WHERE id=? AND tenant_id=?",
                        artifact_id, tenant_id)
        return dict(r) if r else None

    def payload(self, artifact_id: str, *, tenant_id: str) -> Optional[dict]:
        row = self.get(artifact_id, tenant_id=tenant_id)
        return json.loads(row["payload_json"]) if row else None

    def list(self, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_artifacts WHERE tenant_id=? ORDER BY "
            "created_at", tenant_id)]

    def list_for_task(self, task_id: str, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_artifacts WHERE tenant_id=? AND "
            "task_id=? ORDER BY created_at", tenant_id, task_id)]

    def list_for_run(self, run_id: str, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_artifacts WHERE tenant_id=? AND "
            "run_id=? ORDER BY created_at", tenant_id, run_id)]

    def update_head(self, artifact_id: str, *, tenant_id: str, payload: dict,
                    **cols) -> None:
        cols["payload_json"] = json.dumps(payload)
        sets = ", ".join(f"{k}=?" for k in cols)
        self.db.conn.execute(
            f"UPDATE ai_artifacts SET {sets} WHERE id=? AND tenant_id=?",
            (*cols.values(), artifact_id, tenant_id))
        self.db.conn.commit()

    # -- versions -------------------------------------------------------------
    def save_version(self, row: dict) -> None:
        self.db.insert("ai_artifact_versions", row)

    def versions(self, artifact_id: str, *, tenant_id: str) -> list[dict]:
        return [json.loads(r["payload_json"]) for r in self.db.all(
            "SELECT payload_json FROM ai_artifact_versions WHERE artifact_id=? "
            "AND tenant_id=? ORDER BY version_number", artifact_id, tenant_id)]

    def version(self, artifact_id: str, version_id: str, *,
                tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_artifact_versions WHERE id=? AND "
            "artifact_id=? AND tenant_id=?", version_id, artifact_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def latest_version(self, artifact_id: str, *,
                       tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT payload_json FROM ai_artifact_versions WHERE artifact_id=? "
            "AND tenant_id=? ORDER BY version_number DESC LIMIT 1",
            artifact_id, tenant_id)
        return json.loads(r["payload_json"]) if r else None

    def next_version_number(self, artifact_id: str, *, tenant_id: str) -> int:
        r = self.db.one(
            "SELECT MAX(version_number) m FROM ai_artifact_versions WHERE "
            "artifact_id=? AND tenant_id=?", artifact_id, tenant_id)
        return (r["m"] + 1) if r and r["m"] is not None else 1

"""Persistence for the Finalis AI Employee identity (CORE-A1)."""
from __future__ import annotations

import json
import uuid
from typing import Optional

from ..portal.db import Database, utcnow
from .identity import SEGMENTS, AIEmployee


class AIEmployeeStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def _row_to_emp(self, r: dict) -> AIEmployee:
        return AIEmployee(
            tenant_id=r["tenant_id"], id=r["id"],
            display_name=r["display_name"], internal_name=r["internal_name"],
            identity_type=r["identity_type"], role=r["role"],
            segment_capabilities=json.loads(r["segment_capabilities_json"]),
            status=r["status"], identity_version=r["identity_version"],
            profile_version=r["profile_version"],
            human_supervisor_required=bool(r["human_supervisor_required"]),
            default_supervisor_role=r["default_supervisor_role"],
            created_by=r["created_by"], created_at=r["created_at"])

    def create(self, emp: AIEmployee) -> AIEmployee:
        emp.id = emp.id or str(uuid.uuid4())
        emp.created_at = emp.created_at or utcnow()
        self.db.insert("ai_employees", {
            "id": emp.id, "tenant_id": emp.tenant_id,
            "display_name": emp.display_name,
            "internal_name": emp.internal_name,
            "identity_type": emp.identity_type, "role": emp.role,
            "segment_capabilities_json": json.dumps(emp.segment_capabilities),
            "status": emp.status, "identity_version": emp.identity_version,
            "profile_version": emp.profile_version,
            "human_supervisor_required": int(emp.human_supervisor_required),
            "default_supervisor_role": emp.default_supervisor_role,
            "created_by": emp.created_by, "created_at": emp.created_at})
        return emp

    def list(self, *, tenant_id: str) -> list[AIEmployee]:
        return [self._row_to_emp(dict(r)) for r in self.db.all(
            "SELECT * FROM ai_employees WHERE tenant_id=? ORDER BY created_at",
            tenant_id)]

    def get(self, ai_employee_id: str, *,
            tenant_id: str) -> Optional[AIEmployee]:
        r = self.db.one("SELECT * FROM ai_employees WHERE id=? AND "
                        "tenant_id=?", ai_employee_id, tenant_id)
        return self._row_to_emp(dict(r)) if r else None

    def get_or_create_default(self, *, tenant_id: str,
                              created_by: str = "system") -> AIEmployee:
        existing = self.list(tenant_id=tenant_id)
        if existing:
            return existing[0]
        return self.create(AIEmployee(
            tenant_id=tenant_id, segment_capabilities=list(SEGMENTS),
            created_by=created_by))

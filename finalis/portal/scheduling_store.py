"""Scheduling persistence (migration v4) — write-through store.

The SchedulingEngine stays the source of business rules (double booking,
buffers, token expiry, lifecycle handoff); this store makes the DATABASE
the source of truth across restarts: every mutation is written through,
and `hydrate()` rebuilds the engine's appointments and token map on
startup. Raw confirmation tokens are never stored — only their SHA-256
hash (which is exactly what the engine keeps too).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from ..scheduling.engine import Appointment, SchedulingEngine
from .db import Database, utcnow

# States whose token may still confirm (expiry is checked by the engine).
_CONFIRMABLE = {"PENDING_CLIENT_CONFIRMATION"}


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _dt(s: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(s) if s else None


class SchedulingStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, appt: Appointment, *, actor: str = "system",
             event_type: Optional[str] = None,
             payload: Optional[dict] = None) -> None:
        row = {
            "id": appt.id, "tenant_id": appt.tenant_id,
            "case_id": appt.case_id,
            "appointment_type": appt.appointment_type,
            "status": appt.status,
            "assigned_user_id": appt.assigned_user_id,
            "resource_id": appt.assigned_resource_id,
            "start_at": appt.start_at.isoformat(),
            "end_at": appt.end_at.isoformat(),
            "video_meeting_url": appt.video_meeting_url,
            "provider_name": appt.provider,
            "provider_is_mock": 1,
            "requires_confirmation": int(appt.requires_confirmation),
            "confirmation_token_hash": appt.confirmation_token_hash,
            # The engine invalidates tokens after start_at.
            "confirmation_expires_at": appt.start_at.isoformat(),
            "confirmed_at": _iso(appt.confirmed_at),
            "cancelled_at": _iso(appt.cancelled_at),
            "cancellation_reason": appt.cancellation_reason,
            "completed_at": utcnow() if appt.status == "COMPLETED" else None,
            "no_show_at": utcnow() if appt.status == "NO_SHOW" else None,
            "reschedule_count": appt.reschedule_count,
            "updated_at": utcnow(),
        }
        if self.db.one("SELECT id FROM scheduling_appointments WHERE id=?",
                       appt.id):
            self.db.update("scheduling_appointments", appt.id, row)
        else:
            self.db.insert("scheduling_appointments", row)
        if event_type:
            self.append_event(appt.tenant_id, appt.id, event_type,
                              actor=actor, payload=payload)

    def append_event(self, tenant_id: str, appointment_id: str,
                     event_type: str, *, actor: str = "system",
                     payload: Optional[dict] = None) -> None:
        self.db.insert("scheduling_appointment_events", {
            "id": str(uuid.uuid4()), "tenant_id": tenant_id,
            "appointment_id": appointment_id, "event_type": event_type,
            "actor": actor,
            "payload_json": json.dumps(payload or {}, default=str)})

    def events(self, appointment_id: str, *,
               tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.db.all(
            "SELECT * FROM scheduling_appointment_events "
            "WHERE appointment_id=? AND tenant_id=? ORDER BY created_at",
            appointment_id, tenant_id)]

    def get(self, appointment_id: str, *,
            tenant_id: str) -> Optional[dict]:
        r = self.db.one(
            "SELECT * FROM scheduling_appointments WHERE id=? AND "
            "tenant_id=?", appointment_id, tenant_id)
        return dict(r) if r else None

    def list(self, *, tenant_id: str,
             case_id: Optional[str] = None) -> list[dict]:
        sql = ("SELECT * FROM scheduling_appointments WHERE tenant_id=?")
        params = [tenant_id]
        if case_id:
            sql += " AND case_id=?"
            params.append(case_id)
        return [dict(r) for r in self.db.all(
            sql + " ORDER BY start_at", *params)]

    def appointment_id_for_token_hash(self, token_hash: str
                                      ) -> Optional[str]:
        r = self.db.one("SELECT id FROM scheduling_appointments WHERE "
                        "confirmation_token_hash=?", token_hash)
        return r["id"] if r else None

    # -- restart survival --------------------------------------------------------
    def hydrate(self, engine: SchedulingEngine) -> int:
        """Rebuild the engine's in-memory state (appointments + token map)
        from the DB. Called once at app startup; returns rows loaded."""
        count = 0
        for r in self.db.all("SELECT * FROM scheduling_appointments"):
            appt = Appointment(
                tenant_id=r["tenant_id"], case_id=r["case_id"],
                appointment_type=r["appointment_type"],
                start_at=_dt(r["start_at"]), end_at=_dt(r["end_at"]),
                status=r["status"],
                assigned_user_id=r["assigned_user_id"],
                assigned_resource_id=r["resource_id"],
                video_meeting_url=r["video_meeting_url"],
                requires_confirmation=bool(r["requires_confirmation"]),
                confirmation_token_hash=r["confirmation_token_hash"],
                confirmed_at=_dt(r["confirmed_at"]),
                cancelled_at=_dt(r["cancelled_at"]),
                cancellation_reason=r["cancellation_reason"],
                reschedule_count=r["reschedule_count"],
                provider=r["provider_name"], id=r["id"])
            engine.appointments[appt.id] = appt
            if appt.confirmation_token_hash \
                    and appt.status in _CONFIRMABLE:
                engine._tokens[appt.confirmation_token_hash] = appt.id
            count += 1
        return count

"""Append-only, hash-chained audit log — executable form of doc 04 `AuditEvent`."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class AuditEvent:
    event_type: str
    actor: str
    case_id: Optional[str]
    payload: dict[str, Any]
    hash_prev: str
    hash_self: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


class AuditLog:
    """Append-only with tamper-evident hash chain. No update/delete API exists."""

    GENESIS = "0" * 64

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(self, *, event_type: str, actor: str,
               case_id: Optional[str] = None,
               payload: Optional[dict[str, Any]] = None) -> AuditEvent:
        prev = self._events[-1].hash_self if self._events else self.GENESIS
        ev = AuditEvent(event_type=event_type, actor=actor, case_id=case_id,
                        payload=payload or {}, hash_prev=prev)
        ev.hash_self = self._digest(ev)
        self._events.append(ev)
        return ev

    @staticmethod
    def _digest(ev: AuditEvent) -> str:
        material = json.dumps(
            {"id": ev.id, "event_type": ev.event_type, "actor": ev.actor,
             "case_id": ev.case_id, "payload": ev.payload,
             "created_at": ev.created_at, "hash_prev": ev.hash_prev},
            sort_keys=True, default=str,
        )
        return hashlib.sha256(material.encode()).hexdigest()

    def verify_chain(self) -> bool:
        prev = self.GENESIS
        for ev in self._events:
            if ev.hash_prev != prev or ev.hash_self != self._digest(ev):
                return False
            prev = ev.hash_self
        return True

    def events(self, *, case_id: Optional[str] = None,
               event_type: Optional[str] = None) -> list[AuditEvent]:
        out = list(self._events)
        if case_id is not None:
            out = [e for e in out if e.case_id == case_id]
        if event_type is not None:
            out = [e for e in out if e.event_type == event_type]
        return out

    def __len__(self) -> int:
        return len(self._events)

"""Infrastructure adapters — Temporal / Novu / Chatwoot behind protocols.

Mocks are deterministic and observable; production swaps the transport, not
the engine. None of these adapters makes decisions — the Finalis brain
(gate/approval/audit) is always upstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional, Protocol


class WorkflowAdapter(Protocol):
    def schedule(self, workflow: str, *, run_at: datetime,
                 payload: dict) -> str: ...
    def advance_to(self, now: datetime) -> list[dict]: ...


class TemporalMock:
    """Durable-workflow mock with a simulated clock.

    Scheduled work survives 'restarts' because state is plain data —
    exactly the property Temporal provides for real.
    """

    def __init__(self, audit) -> None:
        self.audit = audit
        self.scheduled: list[dict] = []
        self.completed: list[dict] = []

    def schedule(self, workflow: str, *, run_at: datetime,
                 payload: dict) -> str:
        wf = {"id": f"wf-{len(self.scheduled) + len(self.completed) + 1}",
              "workflow": workflow, "run_at": run_at, "payload": payload}
        self.scheduled.append(wf)
        self.audit.append(event_type="TEMPORAL_WORKFLOW_STARTED",
                          actor="system",
                          case_id=payload.get("case_id"),
                          payload={"workflow": workflow, "wf_id": wf["id"],
                                   "run_at": str(run_at)})
        return wf["id"]

    def advance_to(self, now: datetime) -> list[dict]:
        due = [w for w in self.scheduled if w["run_at"] <= now]
        self.scheduled = [w for w in self.scheduled if w["run_at"] > now]
        for w in due:
            self.completed.append(w)
            self.audit.append(event_type="TEMPORAL_WORKFLOW_COMPLETED",
                              actor="system",
                              case_id=w["payload"].get("case_id"),
                              payload={"workflow": w["workflow"],
                                       "wf_id": w["id"]})
        return due


class NotificationAdapter(Protocol):
    name: str
    def send(self, *, channel: str, recipient: str, text: str,
             tenant_id: str) -> dict: ...


class NovuMock:
    name = "novu-mock"

    def __init__(self, audit, *, fail_channels: set[str] | None = None) -> None:
        self.audit = audit
        self.sent: list[dict] = []
        self.fail_channels = fail_channels or set()

    def send(self, *, channel: str, recipient: str, text: str,
             tenant_id: str) -> dict:
        if channel in self.fail_channels:
            return {"ok": False, "provider_message_id": None,
                    "error": f"{channel}_provider_down"}
        msg = {"channel": channel, "recipient": recipient, "text": text,
               "tenant_id": tenant_id,
               "provider_message_id": f"novu-{len(self.sent) + 1}"}
        self.sent.append(msg)
        self.audit.append(event_type="NOVU_NOTIFICATION_TRIGGERED",
                          actor="system",
                          payload={"channel": channel,
                                   "provider_message_id":
                                       msg["provider_message_id"]})
        return {"ok": True,
                "provider_message_id": msg["provider_message_id"]}


class ChatwootMock:
    name = "chatwoot-mock"

    def __init__(self, audit) -> None:
        self.audit = audit
        self.conversations: list[dict] = []

    def create_handoff(self, *, tenant_id: str, case_id: str,
                       contact: str, summary: str,
                       labels: list[str] | None = None) -> dict:
        conv = {"id": f"cw-{len(self.conversations) + 1}",
                "tenant_id": tenant_id, "case_id": case_id,
                "contact": contact,
                "private_note": summary,      # AI summary as private note
                "labels": labels or ["finalis-handoff"],
                "assigned": None}
        self.conversations.append(conv)
        self.audit.append(event_type="CHATWOOT_HANDOFF_CREATED",
                          actor="system", case_id=case_id,
                          payload={"conversation_id": conv["id"]})
        return conv

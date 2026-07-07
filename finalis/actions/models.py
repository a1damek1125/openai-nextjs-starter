"""Action & Communication data model (executable subset of the spec)."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional


def _uuid() -> str:
    return str(uuid.uuid4())


@dataclass
class ActionRequest:
    tenant_id: str
    case_id: str
    action_type: str
    reason: str
    source: str = "completion_loop"       # source_engine
    proposed_by: str = "ai"
    payload: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "low"               # low | medium | high
    created_at: Optional[datetime] = None
    id: str = field(default_factory=_uuid)


@dataclass
class MessageDraft:
    tenant_id: str
    case_id: str
    action_request_id: str
    language: str
    channel: str
    text: str
    variables: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "low"
    approval_status: str = "NOT_REQUIRED"  # NOT_REQUIRED|PENDING|APPROVED|REJECTED|EXPIRED|CANCELLED
    edited_text: Optional[str] = None
    id: str = field(default_factory=_uuid)

    @property
    def final_text(self) -> str:
        return self.edited_text or self.text


@dataclass
class ActionExecution:
    tenant_id: str
    case_id: str
    action_request_id: str
    channel: str
    provider: str
    status: str = "created"   # created|queued|scheduled|sent|delivered|failed|read|replied
    scheduled_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    result: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    id: str = field(default_factory=_uuid)


@dataclass
class DeliveryEvent:
    tenant_id: str
    case_id: str
    action_execution_id: str
    provider: str
    provider_message_id: str
    status: str               # sent|delivered|failed|read|replied|clicked|uploaded
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=_uuid)


@dataclass
class UploadLink:
    tenant_id: str
    case_id: str
    purpose: str              # installation_photo | document | ...
    token_hash: str
    expires_at: datetime
    status: str = "CREATED"   # CREATED|SENT|OPENED|USED|EXPIRED|REVOKED
    allowed_types: tuple = ("image/jpeg", "image/png", "application/pdf")
    max_size_mb: int = 25
    used_at: Optional[datetime] = None
    id: str = field(default_factory=_uuid)

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class ConsentPreference:
    tenant_id: str
    party_id: str
    channel: str              # sms | whatsapp | email | phone | any
    status: str               # opted_in | opted_out
    source: str = "intake"


@dataclass
class ChannelPreference:
    tenant_id: str
    party_id: str
    preferred_channel: str = "whatsapp"
    preferred_time_window: tuple[int, int] = (8, 21)   # local hours
    do_not_contact: bool = False
    available_channels: tuple = ("whatsapp", "sms", "email")
    notes: str = ""


@dataclass
class RateLimitRule:
    tenant_id: str
    action_type: str = "*"
    channel: str = "*"
    max_per_day: int = 3
    cooldown_minutes: int = 20 * 60      # 20h default
    max_attempts: int = 3

"""Call session model — sessions, events, consent, dispositions, overrides."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


def _uuid() -> str:
    return str(uuid.uuid4())


INBOUND_STATES = {"INBOUND_RINGING", "INBOUND_ACCEPTED", "CONSENT_REQUESTED",
                  "CONSENT_GRANTED", "CONSENT_DECLINED", "AI_ACTIVE",
                  "HUMAN_TRANSFER_REQUESTED", "HUMAN_TRANSFERRED",
                  "VOICEMAIL_DETECTED", "CALL_COMPLETED", "CALL_ABANDONED",
                  "CALL_FAILED"}
OUTBOUND_STATES = {"OUTBOUND_REQUESTED", "PERMISSION_CHECKED", "SCHEDULED",
                   "DIALING", "RINGING", "ANSWERED", "VOICEMAIL", "BUSY",
                   "NO_ANSWER", "FAILED", "AI_ACTIVE", "HUMAN_TRANSFERRED",
                   "COMPLETED", "RETRY_SCHEDULED", "CANCELLED"}
FINAL_CALL_STATUSES = {"COMPLETED", "FAILED", "NO_ANSWER", "BUSY",
                       "VOICEMAIL", "ABANDONED", "CANCELLED"}

DISPOSITIONS = {
    "ANSWERED_COMPLETED", "ANSWERED_HUMAN_TRANSFER",
    "ANSWERED_CLIENT_REQUESTED_CALLBACK", "ANSWERED_CLIENT_DECLINED",
    "ANSWERED_WRONG_NUMBER", "VOICEMAIL_LEFT", "VOICEMAIL_NO_MESSAGE",
    "NO_ANSWER", "BUSY", "FAILED_PROVIDER", "FAILED_PERMISSION_BLOCK",
    "ABANDONED_BY_CALLER", "SPAM_CALL", "DUPLICATE_CALL",
    "EMERGENCY_OR_UNSAFE_ESCALATION", "UNKNOWN_REQUIRES_REVIEW"}


@dataclass
class CallSession:
    tenant_id: str
    direction: str                     # inbound | outbound
    source_number: str
    destination_number: str
    provider: str = "mock"
    case_id: Optional[str] = None
    party_id: Optional[str] = None
    provider_call_id: Optional[str] = None
    status: str = "OUTBOUND_REQUESTED"
    started_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: int = 0
    recording_allowed: bool = False
    transcription_allowed: bool = False
    recording_uri: Optional[str] = None
    transcript_session_id: Optional[str] = None
    outcome: Optional[str] = None      # disposition
    outcome_reason: Optional[str] = None
    disposition_confidence: float = 0.0
    human_handoff_required: bool = False
    events: list["CallEvent"] = field(default_factory=list)
    id: str = field(default_factory=_uuid)

    def add_event(self, event_type: str, payload: dict | None = None,
                  audit=None) -> "CallEvent":
        ev = CallEvent(tenant_id=self.tenant_id, call_session_id=self.id,
                       event_type=event_type, payload=payload or {})
        self.events.append(ev)
        if audit is not None:
            audit.append(event_type=f"CALL_{event_type}", actor="telephony",
                         case_id=self.case_id,
                         payload={"call_id": self.id, **(payload or {})})
        return ev


@dataclass
class CallEvent:
    tenant_id: str
    call_session_id: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=_uuid)


@dataclass
class CallConsent:
    tenant_id: str
    call_session_id: str
    consent_type: str                  # recording | transcription | analytics
    status: str                        # granted | declined | not_required
    source: str = "verbal"
    id: str = field(default_factory=_uuid)


@dataclass
class ContactCallState:
    """Per-contact calling history the guards evaluate."""
    opted_out: bool = False
    do_not_call: bool = False
    explicit_refusal: bool = False
    wrong_number: bool = False
    open_complaint: bool = False
    identity_verified: bool = False
    calls_today: int = 0
    attempts_in_sequence: int = 0
    last_attempt_hours_ago: float = 999.0
    consecutive_no_answer: int = 0
    voicemails_left: int = 0


# --- Human Override system ---------------------------------------------------
SOFT_BLOCK = "SOFT_BLOCK_OVERRIDE"
HARD_BLOCK = "HARD_BLOCK_OVERRIDE"
NON_OVERRIDEABLE = "NON_OVERRIDEABLE_SAFETY_BLOCK"

# Block type → override level required.
BLOCK_LEVELS: dict[str, str] = {
    "low_confidence_field": SOFT_BLOCK,
    "high_value_approval": SOFT_BLOCK,
    "extra_followup_after_limit": HARD_BLOCK,
    "reopen_final_case": HARD_BLOCK,
    "manual_payment_correction": HARD_BLOCK,
    "pricing_message": HARD_BLOCK,
    "close_despite_noncritical_missing": HARD_BLOCK,
    # Never overrideable in product UI:
    "opt_out": NON_OVERRIDEABLE,
    "do_not_call": NON_OVERRIDEABLE,
    "explicit_refusal": NON_OVERRIDEABLE,
    "wrong_number_auto_call": NON_OVERRIDEABLE,
    "recording_without_consent": NON_OVERRIDEABLE,
    "emergency_to_sales_flow": NON_OVERRIDEABLE,
    "sensitive_without_identity": NON_OVERRIDEABLE,
    "bulk_campaign_without_compliance": NON_OVERRIDEABLE,
}

OVERRIDE_ROLES = {SOFT_BLOCK: {"manager", "owner", "admin"},
                  HARD_BLOCK: {"owner", "admin", "compliance"}}


@dataclass
class HumanOverride:
    tenant_id: str
    case_id: str
    block_type: str
    original_decision: str
    override_decision: str
    reason_text: str
    approved_by_user_id: str
    approved_by_role: str
    action_id: Optional[str] = None
    evidence_reference: Optional[str] = None
    scope: str = "this_action_only"
    one_time_only: bool = True
    used: bool = False
    expired: bool = False
    audit_event_id: Optional[str] = None
    id: str = field(default_factory=_uuid)


def decide_override(override: HumanOverride, audit) -> str:
    """APPROVED_OVERRIDE | REJECTED_OVERRIDE | REQUIRE_HIGHER_APPROVAL |
    NON_OVERRIDEABLE | EXPIRED — with mandatory reason + audit."""
    audit.append(event_type="HUMAN_OVERRIDE_REQUESTED",
                 actor=override.approved_by_user_id,
                 case_id=override.case_id,
                 payload={"block_type": override.block_type,
                          "role": override.approved_by_role})
    level = BLOCK_LEVELS.get(override.block_type, HARD_BLOCK)
    if level == NON_OVERRIDEABLE:
        audit.append(event_type="NON_OVERRIDEABLE_BLOCK_CONFIRMED",
                     actor="system", case_id=override.case_id,
                     payload={"block_type": override.block_type})
        return "NON_OVERRIDEABLE"
    if not override.reason_text.strip():
        return "REJECTED_OVERRIDE"
    if not override.approved_by_user_id \
            or override.approved_by_role == "ai_worker":
        return "REJECTED_OVERRIDE"          # no anonymous / AI self-approval
    if override.expired:
        return "EXPIRED"
    if override.approved_by_role not in OVERRIDE_ROLES[level]:
        return "REQUIRE_HIGHER_APPROVAL"
    if override.one_time_only and override.used:
        return "EXPIRED"
    override.used = True
    ev = audit.append(event_type="HUMAN_OVERRIDE_APPROVED",
                      actor=override.approved_by_user_id,
                      case_id=override.case_id,
                      payload={"block_type": override.block_type,
                               "reason": override.reason_text,
                               "scope": override.scope})
    override.audit_event_id = ev.id
    audit.append(event_type="BLOCK_OVERRIDE_APPLIED", actor="system",
                 case_id=override.case_id,
                 payload={"override_id": override.id})
    return "APPROVED_OVERRIDE"

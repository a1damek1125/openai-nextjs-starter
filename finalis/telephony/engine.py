"""Call Control Engine + MockTelephonyProvider.

The provider interface is what LiveKitTelephonyProvider / AsteriskProvider /
FreeSwitchProvider / GenericSipProvider implement later; the engine logic
(gating, consent, disposition, case integration) never changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol

from ..audit import AuditLog
from ..case_services import CaseGraphService, CompletionLoopService
from ..voice.conversation_intelligence import (ConversationIntelligence,
                                               DiarizedSegment)
from .gates import (AntiHarassmentGuard, CallPermissionGate,
                    disposition_confidence, human_handoff_score)
from .models import (DISPOSITIONS, CallConsent, CallSession,
                     ContactCallState)


class TelephonyProvider(Protocol):
    name: str
    is_mock: bool
    def dial(self, session: CallSession, scenario: str) -> str: ...
    def hangup(self, session: CallSession) -> None: ...


class MockTelephonyProvider:
    """Simulates the full call lifecycle. Scenario-driven and deterministic.

    Scenarios: answered | busy | no_answer | voicemail | failed |
    answered_then_human | answered_wrong_number | abandoned.
    """
    name = "mock-telephony"
    is_mock = True

    def dial(self, session: CallSession, scenario: str) -> str:
        session.provider_call_id = f"mock-{session.id[:8]}"
        outcomes = {"answered": "ANSWERED", "busy": "BUSY",
                    "no_answer": "NO_ANSWER", "voicemail": "VOICEMAIL",
                    "failed": "FAILED", "answered_then_human": "ANSWERED",
                    "answered_wrong_number": "ANSWERED",
                    "abandoned": "ABANDONED"}
        return outcomes.get(scenario, "FAILED")

    def hangup(self, session: CallSession) -> None:
        session.ended_at = datetime.utcnow()


@dataclass
class CallResult:
    session: CallSession
    permission: str
    disposition: Optional[str]
    blocked_reason: Optional[str] = None
    handoff: bool = False
    retry: Optional[str] = None
    analysis: Optional[dict] = None


class CallControlEngine:
    def __init__(self, audit: AuditLog,
                 provider: Optional[TelephonyProvider] = None,
                 graph: Optional[CaseGraphService] = None) -> None:
        self.audit = audit
        self.provider = provider or MockTelephonyProvider()
        self.gate = CallPermissionGate()
        self.guard = AntiHarassmentGuard()
        self.graph = graph or CaseGraphService(audit)
        self.loop = CompletionLoopService(audit)
        self.sessions: dict[str, CallSession] = {}
        self.number_index: dict[str, str] = {}   # phone -> case_id

    # -- inbound -----------------------------------------------------------------
    def simulate_inbound(self, *, tenant_id: str, caller_number: str,
                         segments: list[dict],
                         recording_consent: str = "granted",
                         emergency: bool = False,
                         asks_for_human: bool = False,
                         now: Optional[datetime] = None) -> CallResult:
        now = now or datetime.utcnow()
        session = CallSession(tenant_id=tenant_id, direction="inbound",
                              source_number=caller_number,
                              destination_number="tenant-line",
                              provider=self.provider.name,
                              status="INBOUND_RINGING", started_at=now)
        self.sessions[session.id] = session
        session.add_event("INBOUND_RINGING", audit=self.audit)

        # Caller matching: known number → attach; unknown → NEW_CONTACT case.
        case_id = self.number_index.get(caller_number)
        if case_id is None:
            case = self.graph.create_case(tenant_id=tenant_id,
                                          title="Inbound call intake",
                                          source_channel="phone")
            case_id = case.id
            self.number_index[caller_number] = case_id
            session.add_event("NEW_CONTACT_CASE_CREATED",
                              {"case_id": case_id}, audit=self.audit)
        session.case_id = case_id
        session.status = "INBOUND_ACCEPTED"

        # Consent (recording ≠ transcription — separate decisions).
        session.add_event("CONSENT_REQUESTED", audit=self.audit)
        session.recording_allowed = recording_consent == "granted"
        session.transcription_allowed = recording_consent != "declined_all"
        consent = CallConsent(tenant_id=tenant_id,
                              call_session_id=session.id,
                              consent_type="recording",
                              status=("granted" if session.recording_allowed
                                      else "declined"))
        session.add_event("CONSENT_" + consent.status.upper(),
                          audit=self.audit)
        if session.recording_allowed:
            session.recording_uri = f"local://recordings/{session.id}.wav"

        # Emergency: never continue normal intake/sales flow.
        if emergency:
            session.status = "HUMAN_TRANSFER_REQUESTED"
            session.human_handoff_required = True
            session.outcome = "EMERGENCY_OR_UNSAFE_ESCALATION"
            session.outcome_reason = "emergency_detected"
            session.disposition_confidence = 1.0
            session.add_event("EMERGENCY_ESCALATION", audit=self.audit)
            self._end(session, now)
            return CallResult(session, "ALLOW",
                              session.outcome, handoff=True)

        session.status = "AI_ACTIVE"
        session.add_event("AI_ACTIVE", audit=self.audit)

        # Explicit human request → immediate handoff (score bypass).
        if asks_for_human:
            score, immediate = human_handoff_score(
                frustration=0, sensitive_topic=0, low_understanding=0,
                high_value=0, repeated_misunderstanding=0, payment_issue=0,
                explicit_human_request=True)
            assert immediate
            session.status = "HUMAN_TRANSFERRED"
            session.human_handoff_required = True
            session.outcome = "ANSWERED_HUMAN_TRANSFER"
            session.disposition_confidence = 1.0
            session.add_event("HUMAN_TRANSFER", audit=self.audit)
            self._end(session, now)
            return CallResult(session, "ALLOW", session.outcome,
                              handoff=True)

        # Transcript → Conversation Intelligence → Case Graph → Loop.
        analysis = None
        if session.transcription_allowed and segments:
            ci = ConversationIntelligence(self.audit, tenant_id=tenant_id)
            diarized = [DiarizedSegment(**s) for s in segments]
            result = ci.analyze(session.id, diarized, case_id=case_id)
            session.transcript_session_id = session.id
            analysis = result.case_update_payload
            case = self.graph.cases.get(case_id)
            if case is not None:
                from ..models import MissingItem
                existing = {m.field_key for m in case.missing_items}
                for m in result.missing_items:
                    if m["type"] not in existing:
                        case.missing_items.append(MissingItem(
                            field_key=m["type"], label=m["type"],
                            weight=0.9 if m["severity"] == "high" else 0.5,
                            blocks_quote=(m["blocks"]
                                          == "quote_preparation")))
                self.loop.run_case(case, now=now)

        session.status = "CALL_COMPLETED"
        session.outcome = "ANSWERED_COMPLETED"
        # Clean, fully processed inbound call with transcript evidence:
        # 0.95·0.95·0.95·1.0·0.95 ≈ 0.815 (≥ 0.70 review threshold).
        session.disposition_confidence = disposition_confidence(
            evidence_quality=0.95, signal_clarity=0.95, completeness=0.95,
            provider_reliability=1.0, transcript_confidence=0.95)
        self._end(session, now)
        return CallResult(session, "ALLOW", session.outcome,
                          analysis=analysis)

    # -- outbound -----------------------------------------------------------------
    def request_outbound(self, *, tenant_id: str, case_id: Optional[str],
                         destination: str, contact: ContactCallState,
                         business_purpose: str, scenario: str = "answered",
                         urgent: bool = False,
                         sensitive_topic: bool = False,
                         human_approval_granted: bool = False,
                         segments: Optional[list[dict]] = None,
                         now: Optional[datetime] = None) -> CallResult:
        now = now or datetime.utcnow()
        session = CallSession(tenant_id=tenant_id, direction="outbound",
                              source_number="tenant-line",
                              destination_number=destination,
                              provider=self.provider.name,
                              case_id=case_id, started_at=now)
        self.sessions[session.id] = session
        session.add_event("OUTBOUND_REQUESTED",
                          {"purpose": business_purpose}, audit=self.audit)

        perm = self.gate.evaluate(
            contact=contact, case_id=case_id,
            business_purpose=business_purpose,
            tenant_allows_outbound=True, now=now, urgent=urgent,
            sensitive_topic=sensitive_topic,
            human_approval_granted=human_approval_granted,
            audit=self.audit)
        session.status = "PERMISSION_CHECKED"
        if perm.result != "ALLOW":
            session.status = "CANCELLED" if perm.result == "BLOCK" \
                else "SCHEDULED"
            session.outcome = "FAILED_PERMISSION_BLOCK" \
                if perm.result == "BLOCK" else None
            if perm.result == "BLOCK":
                session.outcome_reason = ";".join(perm.hard_blockers)
                session.disposition_confidence = 1.0
                self._end(session, now)
            return CallResult(session, perm.result, session.outcome,
                              blocked_reason=", ".join(perm.reasons))

        ok, guard_reason = self.guard.check(contact, audit=self.audit,
                                            case_id=case_id)
        if not ok:
            session.status = "CANCELLED"
            session.outcome = "FAILED_PERMISSION_BLOCK"
            session.outcome_reason = f"anti_harassment:{guard_reason}"
            session.disposition_confidence = 1.0
            self._end(session, now)
            return CallResult(session, "BLOCK", session.outcome,
                              blocked_reason=guard_reason)

        # Dial via provider (mock or real — same interface).
        session.status = "DIALING"
        session.add_event("DIALING", audit=self.audit)
        outcome = self.provider.dial(session, scenario)
        contact.calls_today += 1
        contact.attempts_in_sequence += 1
        contact.last_attempt_hours_ago = 0.0

        if outcome == "ANSWERED":
            session.answered_at = now
            session.status = "AI_ACTIVE"
            # Transparent AI self-identification (policy default).
            session.add_event("AI_DISCLOSURE",
                              {"text": "Dzień dobry, dzwoni automatyczny "
                                       "asystent firmy w sprawie Pana "
                                       "zapytania."}, audit=self.audit)
            if scenario == "answered_wrong_number":
                contact.wrong_number = True
                session.outcome = "ANSWERED_WRONG_NUMBER"
                session.add_event("WRONG_NUMBER", audit=self.audit)
            elif scenario == "answered_then_human":
                session.human_handoff_required = True
                session.outcome = "ANSWERED_HUMAN_TRANSFER"
                session.add_event("HUMAN_TRANSFER", audit=self.audit)
            else:
                contact.consecutive_no_answer = 0
                session.outcome = "ANSWERED_COMPLETED"
                if segments:
                    ci = ConversationIntelligence(self.audit,
                                                  tenant_id=tenant_id)
                    ci.analyze(session.id,
                               [DiarizedSegment(**s) for s in segments],
                               case_id=case_id)
            session.disposition_confidence = 0.9
        elif outcome == "VOICEMAIL":
            contact.voicemails_left += 1
            session.status = "VOICEMAIL"
            # Voicemail: short, no sensitive details, audited.
            session.add_event("VOICEMAIL_LEFT",
                              {"text": "Dzień dobry, tu asystent firmy w "
                                       "sprawie Pana zapytania. Prosimy o "
                                       "kontakt w dogodnym momencie."},
                              audit=self.audit)
            session.outcome = "VOICEMAIL_LEFT"
            session.disposition_confidence = 0.9
        elif outcome in ("NO_ANSWER", "BUSY"):
            contact.consecutive_no_answer += 1
            session.status = outcome
            session.outcome = outcome
            session.disposition_confidence = 0.95
        elif outcome == "ABANDONED":
            session.status = "CALL_ABANDONED"
            session.outcome = "ABANDONED_BY_CALLER"
            session.disposition_confidence = 0.8
        else:
            session.status = "FAILED"
            session.outcome = "FAILED_PROVIDER"
            session.disposition_confidence = 1.0

        self._end(session, now)
        from .gates import retry_decision, retry_score
        rs = retry_score(case_value=0.6, urgency=0.5,
                         positive_engagement=0.5,
                         missing_info_importance=0.6, promise_due=0.5,
                         time_window_fit=0.7, channel_fit=0.6,
                         failed_attempts=contact.consecutive_no_answer,
                         annoyance_risk=min(
                             1.0, contact.attempts_in_sequence / 3),
                         refused_or_opted_out=contact.explicit_refusal
                         or contact.opted_out)
        retry = retry_decision(contact=contact, retry_score=rs) \
            if session.outcome in ("NO_ANSWER", "BUSY", "VOICEMAIL_LEFT",
                                   "FAILED_PROVIDER") else None
        return CallResult(session, "ALLOW", session.outcome, retry=retry,
                          handoff=session.human_handoff_required)

    def _end(self, session: CallSession, now: datetime) -> None:
        session.ended_at = now
        # Disposition is MANDATORY at end; low confidence → review.
        if session.outcome is None:
            session.outcome = "UNKNOWN_REQUIRES_REVIEW"
        if session.disposition_confidence < 0.70:
            session.outcome = "UNKNOWN_REQUIRES_REVIEW"
            session.add_event("DISPOSITION_REVIEW_REQUIRED",
                              audit=self.audit)
        assert session.outcome in DISPOSITIONS
        session.add_event("DISPOSITION_SET",
                          {"disposition": session.outcome,
                           "confidence": session.disposition_confidence},
                          audit=self.audit)

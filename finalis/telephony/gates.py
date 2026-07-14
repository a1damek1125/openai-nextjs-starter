"""Telephony algorithmic layer — permission gate, scores, retry, handoff,
disposition confidence, anti-harassment. Hard blockers override all scores."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .models import ContactCallState


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


@dataclass
class PermissionResult:
    result: str                        # ALLOW | BLOCK | REQUIRE_HUMAN_APPROVAL | SCHEDULE_LATER
    reasons: list[str] = field(default_factory=list)
    hard_blockers: list[str] = field(default_factory=list)
    allowed_after: Optional[datetime] = None
    audit_event_id: Optional[str] = None


class CallPermissionGate:
    """No call may be placed unless this gate passes. Hard blockers first."""

    def __init__(self, *, max_calls_per_day: int = 2,
                 max_sequence_attempts: int = 3,
                 cooldown_hours: float = 4.0,
                 business_hours: tuple[int, int] = (8, 20)) -> None:
        self.max_calls_per_day = max_calls_per_day
        self.max_sequence_attempts = max_sequence_attempts
        self.cooldown_hours = cooldown_hours
        self.business_hours = business_hours

    def evaluate(self, *, contact: ContactCallState, case_id: Optional[str],
                 business_purpose: str, tenant_allows_outbound: bool,
                 now: datetime, urgent: bool = False,
                 sensitive_topic: bool = False,
                 human_approval_granted: bool = False,
                 audit=None) -> PermissionResult:
        hb: list[str] = []
        if contact.opted_out:
            hb.append("client_opted_out")
        if contact.do_not_call:
            hb.append("do_not_call")
        if contact.explicit_refusal:
            hb.append("explicit_refusal")
        if contact.wrong_number:
            hb.append("wrong_number")
        if not business_purpose:
            hb.append("no_valid_business_purpose")
        if case_id is None:
            hb.append("no_case_id")
        if not tenant_allows_outbound:
            hb.append("tenant_outbound_disabled")
        if contact.calls_today >= self.max_calls_per_day:
            hb.append("max_daily_calls_exceeded")
        if contact.attempts_in_sequence >= self.max_sequence_attempts:
            hb.append("max_sequence_attempts_exceeded")
        if contact.open_complaint:
            hb.append("open_complaint_requires_human")
        if sensitive_topic and not contact.identity_verified:
            hb.append("sensitive_topic_without_identity_verification")

        result: PermissionResult
        if hb:
            result = PermissionResult("BLOCK", reasons=list(hb),
                                      hard_blockers=hb)
        else:
            start, end = self.business_hours
            in_hours = start <= now.hour < end
            if not in_hours and not urgent:
                allowed = now.replace(hour=start, minute=0, second=0)
                if now.hour >= end:
                    from datetime import timedelta
                    allowed += timedelta(days=1)
                result = PermissionResult("SCHEDULE_LATER",
                                          reasons=["outside_business_hours"],
                                          allowed_after=allowed)
            elif contact.last_attempt_hours_ago < self.cooldown_hours:
                result = PermissionResult("SCHEDULE_LATER",
                                          reasons=["cooldown_active"])
            elif sensitive_topic and not human_approval_granted:
                result = PermissionResult("REQUIRE_HUMAN_APPROVAL",
                                          reasons=["sensitive_topic"])
            else:
                result = PermissionResult("ALLOW", reasons=["all_checks_ok"])
        if audit is not None:
            ev = audit.append(event_type="CALL_PERMISSION_CHECKED",
                              actor="telephony", case_id=case_id,
                              payload={"result": result.result,
                                       "reasons": result.reasons})
            result.audit_event_id = ev.id
        return result


def call_priority_score(*, case_urgency: float, deal_value: float,
                        client_intent: float, time_sensitivity: float,
                        missing_info_importance: float,
                        promise_due: float, channel_fit: float,
                        annoyance_risk: float = 0.0,
                        recent_failed_penalty: float = 0.0,
                        compliance_risk: float = 0.0) -> float:
    return _clamp(0.25 * _clamp(case_urgency) + 0.20 * _clamp(deal_value)
                  + 0.15 * _clamp(client_intent)
                  + 0.15 * _clamp(time_sensitivity)
                  + 0.10 * _clamp(missing_info_importance)
                  + 0.10 * _clamp(promise_due) + 0.05 * _clamp(channel_fit)
                  - 0.20 * _clamp(annoyance_risk)
                  - 0.15 * _clamp(recent_failed_penalty)
                  - 0.15 * _clamp(compliance_risk))


def retry_decision(*, contact: ContactCallState, retry_score: float,
                   high_value: bool = False) -> str:
    """RETRY_NOW | RETRY_LATER | USE_OTHER_CHANNEL | HUMAN_REVIEW | STOP."""
    if contact.opted_out or contact.explicit_refusal or contact.wrong_number:
        return "STOP"
    if contact.attempts_in_sequence >= 3 \
            or contact.calls_today >= 2:
        return "HUMAN_REVIEW" if high_value else "STOP"
    if contact.consecutive_no_answer >= 2:
        return "USE_OTHER_CHANNEL"
    if retry_score < 0.3:
        return "USE_OTHER_CHANNEL"
    if contact.last_attempt_hours_ago < 4:
        return "RETRY_LATER"
    return "RETRY_NOW"


def retry_score(*, case_value: float, urgency: float,
                positive_engagement: float, missing_info_importance: float,
                promise_due: float, time_window_fit: float,
                channel_fit: float, failed_attempts: int,
                annoyance_risk: float,
                refused_or_opted_out: bool = False) -> float:
    if refused_or_opted_out:
        return 0.0
    return _clamp(0.25 * _clamp(case_value) + 0.20 * _clamp(urgency)
                  + 0.15 * _clamp(positive_engagement)
                  + 0.15 * _clamp(missing_info_importance)
                  + 0.10 * _clamp(promise_due)
                  + 0.10 * _clamp(time_window_fit)
                  + 0.05 * _clamp(channel_fit)
                  - 0.25 * _clamp(failed_attempts / 3.0)
                  - 0.25 * _clamp(annoyance_risk))


def human_handoff_score(*, frustration: float, sensitive_topic: float,
                        low_understanding: float, high_value: float,
                        repeated_misunderstanding: float,
                        payment_issue: float,
                        explicit_human_request: bool = False,
                        emergency: bool = False,
                        angry: bool = False) -> tuple[float, bool]:
    """(score, immediate). Immediate triggers bypass the threshold."""
    immediate = explicit_human_request or emergency or angry
    score = _clamp(0.25 * _clamp(frustration)
                   + 0.20 * _clamp(sensitive_topic)
                   + 0.15 * _clamp(low_understanding)
                   + 0.15 * _clamp(high_value)
                   + 0.10 * _clamp(repeated_misunderstanding)
                   + 0.10 * _clamp(payment_issue)
                   + (0.05 if explicit_human_request else 0.0))
    return (1.0 if immediate else score), immediate


def disposition_confidence(*, evidence_quality: float, signal_clarity: float,
                           completeness: float, provider_reliability: float,
                           transcript_confidence: float) -> float:
    return (_clamp(evidence_quality) * _clamp(signal_clarity)
            * _clamp(completeness) * _clamp(provider_reliability)
            * _clamp(transcript_confidence))


def call_quality_score(*, asr_confidence: float, low_noise: float,
                       speaker_clarity: float, goal_completed: float,
                       sentiment: float, no_interruption_problems: float,
                       evidence_completeness: float,
                       no_escalation: float) -> float:
    return _clamp(0.20 * _clamp(asr_confidence) + 0.15 * _clamp(low_noise)
                  + 0.15 * _clamp(speaker_clarity)
                  + 0.15 * _clamp(goal_completed)
                  + 0.10 * _clamp(sentiment)
                  + 0.10 * _clamp(no_interruption_problems)
                  + 0.10 * _clamp(evidence_completeness)
                  + 0.05 * _clamp(no_escalation))


class AntiHarassmentGuard:
    """Reputation + harassment protection; blocks are audited, never silent."""

    LIMITS = {"max_calls_per_case_per_day": 2,
              "max_calls_per_contact_per_day": 2,
              "max_calls_per_sequence": 3, "min_cooldown_hours": 4,
              "max_voicemails": 2, "max_failed_before_stop": 3}

    def check(self, contact: ContactCallState, *, audit=None,
              case_id: Optional[str] = None) -> tuple[bool, str]:
        L = self.LIMITS
        reason = None
        if contact.calls_today >= L["max_calls_per_contact_per_day"]:
            reason = "daily_contact_limit"
        elif contact.attempts_in_sequence >= L["max_calls_per_sequence"]:
            reason = "sequence_limit"
        elif contact.last_attempt_hours_ago < L["min_cooldown_hours"]:
            reason = "cooldown"
        elif contact.voicemails_left >= L["max_voicemails"]:
            reason = "voicemail_limit"
        elif contact.consecutive_no_answer >= L["max_failed_before_stop"]:
            reason = "repeated_no_answer"
        if reason and audit is not None:
            audit.append(event_type="CALL_BLOCKED_ANTI_HARASSMENT",
                         actor="telephony", case_id=case_id,
                         payload={"reason": reason})
        return (reason is None), (reason or "ok")


# Bulk campaigns are DISABLED until compliance setup exists (tested).
def campaign_calls_allowed(tenant_config: dict) -> bool:
    return bool(tenant_config.get("campaigns_enabled")
                and tenant_config.get("compliance_setup_complete")
                and tenant_config.get("campaign_human_approved"))

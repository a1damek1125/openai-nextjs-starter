"""Telephony & Call Control Engine tests — permission gate, safety,
dispositions, retries, handoff, overrides, integration with the case core."""
import random
from datetime import datetime

import pytest

from finalis.audit import AuditLog
from finalis.telephony.engine import CallControlEngine, MockTelephonyProvider
from finalis.telephony.gates import (AntiHarassmentGuard, CallPermissionGate,
                                     call_priority_score,
                                     call_quality_score,
                                     campaign_calls_allowed,
                                     disposition_confidence,
                                     human_handoff_score, retry_decision,
                                     retry_score)
from finalis.telephony.models import (BLOCK_LEVELS, DISPOSITIONS,
                                      ContactCallState, HumanOverride,
                                      NON_OVERRIDEABLE, decide_override)

DAY = datetime(2026, 7, 8, 10, 0)   # inside business hours
NIGHT = datetime(2026, 7, 8, 23, 0)

SEGMENTS = [
    {"speaker": "SPEAKER_00", "text": "Hi, I'd like a quote for a heat pump "
     "installation.", "start_ms": 0, "end_ms": 3000,
     "asr_confidence": 0.95, "diar_confidence": 0.95, "language": "en"},
    {"speaker": "SPEAKER_00", "text": "I'll send you the photos tomorrow.",
     "start_ms": 3200, "end_ms": 5400, "asr_confidence": 0.92,
     "diar_confidence": 0.95, "language": "en"},
]


def engine():
    return CallControlEngine(AuditLog())


def contact(**kw):
    return ContactCallState(**kw)


class TestInboundCalls:
    def test_1_inbound_creates_session_and_events(self):
        eng = engine()
        r = eng.simulate_inbound(tenant_id="t1",
                                 caller_number="+48600000001",
                                 segments=SEGMENTS, now=DAY)
        assert r.session.direction == "inbound"
        assert r.disposition == "ANSWERED_COMPLETED"
        types = {e.event_type for e in r.session.events}
        assert {"INBOUND_RINGING", "CONSENT_REQUESTED",
                "AI_ACTIVE", "DISPOSITION_SET"} <= types
        assert eng.audit.verify_chain()

    def test_2_unknown_caller_creates_new_contact_case(self):
        eng = engine()
        r = eng.simulate_inbound(tenant_id="t1",
                                 caller_number="+48600000002",
                                 segments=SEGMENTS, now=DAY)
        assert r.session.case_id in eng.graph.cases
        assert any(e.event_type == "NEW_CONTACT_CASE_CREATED"
                   for e in r.session.events)

    def test_3_known_caller_attaches_to_existing_case(self):
        eng = engine()
        r1 = eng.simulate_inbound(tenant_id="t1",
                                  caller_number="+48600000003",
                                  segments=SEGMENTS, now=DAY)
        r2 = eng.simulate_inbound(tenant_id="t1",
                                  caller_number="+48600000003",
                                  segments=SEGMENTS, now=DAY)
        assert r2.session.case_id == r1.session.case_id
        assert not any(e.event_type == "NEW_CONTACT_CASE_CREATED"
                       for e in r2.session.events)

    def test_17_transcript_reaches_conversation_intelligence(self):
        eng = engine()
        r = eng.simulate_inbound(tenant_id="t1",
                                 caller_number="+48600000004",
                                 segments=SEGMENTS, now=DAY)
        assert r.analysis is not None
        assert r.analysis["intent"] == "request_quote"
        assert r.analysis["promises"][0]["what"] == "send photos"
        assert eng.audit.events(event_type="CONVERSATION_ANALYZED")

    def test_18_completion_loop_runs_after_call(self):
        eng = engine()
        eng.simulate_inbound(tenant_id="t1", caller_number="+48600000005",
                             segments=SEGMENTS, now=DAY)
        assert eng.audit.events(event_type="NEXT_ACTION_CREATED")


class TestConsentAndRecording:
    def test_8_recording_blocked_without_consent(self):
        eng = engine()
        r = eng.simulate_inbound(tenant_id="t1",
                                 caller_number="+48600000010",
                                 segments=SEGMENTS,
                                 recording_consent="declined", now=DAY)
        assert r.session.recording_allowed is False
        assert r.session.recording_uri is None
        assert any(e.event_type == "CONSENT_DECLINED"
                   for e in r.session.events)
        # Transcription is a SEPARATE consent: still allowed here.
        assert r.session.transcription_allowed is True

    def test_9_recording_allowed_with_consent(self):
        eng = engine()
        r = eng.simulate_inbound(tenant_id="t1",
                                 caller_number="+48600000011",
                                 segments=SEGMENTS,
                                 recording_consent="granted", now=DAY)
        assert r.session.recording_allowed is True
        assert r.session.recording_uri

    def test_declined_all_blocks_transcription_too(self):
        eng = engine()
        r = eng.simulate_inbound(tenant_id="t1",
                                 caller_number="+48600000012",
                                 segments=SEGMENTS,
                                 recording_consent="declined_all", now=DAY)
        assert r.session.transcription_allowed is False
        assert r.analysis is None            # no transcript processing


class TestHumanHandoffAndEmergency:
    def test_10_client_asks_for_human(self):
        eng = engine()
        r = eng.simulate_inbound(tenant_id="t1",
                                 caller_number="+48600000020",
                                 segments=[], asks_for_human=True, now=DAY)
        assert r.handoff is True
        assert r.disposition == "ANSWERED_HUMAN_TRANSFER"

    def test_11_angry_client_immediate_handoff_score(self):
        score, immediate = human_handoff_score(
            frustration=.9, sensitive_topic=0, low_understanding=0,
            high_value=0, repeated_misunderstanding=0, payment_issue=0,
            angry=True)
        assert immediate and score == 1.0

    def test_emergency_never_continues_sales_flow(self):
        eng = engine()
        r = eng.simulate_inbound(tenant_id="t1",
                                 caller_number="+48600000021",
                                 segments=SEGMENTS, emergency=True, now=DAY)
        assert r.disposition == "EMERGENCY_OR_UNSAFE_ESCALATION"
        assert r.handoff is True
        assert r.analysis is None            # intake flow did NOT run


class TestOutboundPermissionGate:
    def outbound(self, eng, c, **kw):
        return eng.request_outbound(
            tenant_id="t1", case_id=kw.pop("case_id", "case-1"),
            destination="+48600000030", contact=c,
            business_purpose=kw.pop("purpose", "follow up on quote"),
            now=kw.pop("now", DAY), **kw)

    def test_5_optout_blocks_call(self):
        r = self.outbound(engine(), contact(opted_out=True))
        assert r.permission == "BLOCK"
        assert "client_opted_out" in r.session.outcome_reason

    def test_do_not_call_blocks(self):
        r = self.outbound(engine(), contact(do_not_call=True))
        assert r.permission == "BLOCK"

    def test_no_case_id_blocks(self):
        r = self.outbound(engine(), contact(), case_id=None)
        assert r.permission == "BLOCK"
        assert "no_case_id" in r.blocked_reason

    def test_6_outside_business_hours_schedules_later(self):
        r = self.outbound(engine(), contact(), now=NIGHT)
        assert r.permission == "SCHEDULE_LATER"
        assert r.session.status == "SCHEDULED"

    def test_7_valid_purpose_allows(self):
        r = self.outbound(engine(), contact())
        assert r.permission == "ALLOW"
        assert r.disposition == "ANSWERED_COMPLETED"

    def test_sensitive_topic_needs_identity_verification(self):
        r = self.outbound(engine(), contact(identity_verified=False),
                          sensitive_topic=True)
        assert r.permission == "BLOCK"
        assert "identity" in r.blocked_reason

    def test_sensitive_verified_needs_human_approval(self):
        r = self.outbound(engine(), contact(identity_verified=True),
                          sensitive_topic=True)
        assert r.permission == "REQUIRE_HUMAN_APPROVAL"
        r2 = self.outbound(engine(), contact(identity_verified=True),
                           sensitive_topic=True,
                           human_approval_granted=True)
        assert r2.permission == "ALLOW"

    def test_ai_discloses_itself_on_answer(self):
        eng = engine()
        r = self.outbound(eng, contact())
        assert any(e.event_type == "AI_DISCLOSURE"
                   for e in r.session.events)


class TestDispositionsAndRetry:
    def outbound(self, eng, c, scenario):
        return eng.request_outbound(tenant_id="t1", case_id="case-1",
                                    destination="+48600000040", contact=c,
                                    business_purpose="follow up",
                                    scenario=scenario, now=DAY)

    def test_12_voicemail_disposition_and_no_sensitive_info(self):
        eng = engine()
        r = self.outbound(eng, contact(), "voicemail")
        assert r.disposition == "VOICEMAIL_LEFT"
        vm = next(e for e in r.session.events
                  if e.event_type == "VOICEMAIL_LEFT")
        assert "faktur" not in vm.payload["text"].lower()   # no invoice talk
        assert "umow" not in vm.payload["text"].lower()     # no contract talk

    def test_13_no_answer_schedules_safe_retry(self):
        eng = engine()
        c = contact()
        r = self.outbound(eng, c, "no_answer")
        assert r.disposition == "NO_ANSWER"
        assert r.retry in ("RETRY_LATER", "RETRY_NOW", "USE_OTHER_CHANNEL")

    def test_repeated_no_answer_switches_channel(self):
        c = contact(consecutive_no_answer=2, last_attempt_hours_ago=24)
        assert retry_decision(contact=c, retry_score=0.6) \
            == "USE_OTHER_CHANNEL"

    def test_14_explicit_refusal_blocks_retry(self):
        c = contact(explicit_refusal=True)
        assert retry_decision(contact=c, retry_score=0.9) == "STOP"
        assert retry_score(case_value=1, urgency=1, positive_engagement=1,
                           missing_info_importance=1, promise_due=1,
                           time_window_fit=1, channel_fit=1,
                           failed_attempts=0, annoyance_risk=0,
                           refused_or_opted_out=True) == 0.0

    def test_wrong_number_blocks_future_calls(self):
        eng = engine()
        c = contact()
        r = self.outbound(eng, c, "answered_wrong_number")
        assert r.disposition == "ANSWERED_WRONG_NUMBER"
        assert c.wrong_number is True
        # Next call attempt is hard-blocked.
        c.last_attempt_hours_ago = 48
        r2 = self.outbound(eng, c, "answered")
        assert r2.permission == "BLOCK"
        assert "wrong_number" in r2.session.outcome_reason

    def test_16_every_call_gets_final_disposition(self):
        eng = engine()
        for scenario in ["answered", "busy", "no_answer", "voicemail",
                         "failed", "answered_then_human", "abandoned"]:
            c = contact(last_attempt_hours_ago=48)
            r = self.outbound(eng, c, scenario)
            assert r.disposition in DISPOSITIONS, scenario

    def test_low_confidence_becomes_review(self):
        assert disposition_confidence(
            evidence_quality=.9, signal_clarity=.6, completeness=.9,
            provider_reliability=1, transcript_confidence=.9) < 0.70


class TestAntiHarassment:
    def test_20_guard_blocks_excessive_calls(self):
        audit = AuditLog()
        guard = AntiHarassmentGuard()
        ok, reason = guard.check(contact(calls_today=2), audit=audit)
        assert not ok and reason == "daily_contact_limit"
        ok2, r2 = guard.check(contact(voicemails_left=2), audit=audit)
        assert not ok2 and r2 == "voicemail_limit"
        ok3, r3 = guard.check(contact(last_attempt_hours_ago=1), audit=audit)
        assert not ok3 and r3 == "cooldown"
        assert len(audit.events(
            event_type="CALL_BLOCKED_ANTI_HARASSMENT")) == 3

    def test_campaigns_disabled_by_default(self):
        assert not campaign_calls_allowed({})
        assert not campaign_calls_allowed({"campaigns_enabled": True})
        assert campaign_calls_allowed({"campaigns_enabled": True,
                                       "compliance_setup_complete": True,
                                       "campaign_human_approved": True})

    def test_priority_score_never_overrides_gate(self):
        """Property: hard blocker blocks even with a perfect score."""
        gate = CallPermissionGate()
        score = call_priority_score(case_urgency=1, deal_value=1,
                                    client_intent=1, time_sensitivity=1,
                                    missing_info_importance=1,
                                    promise_due=1, channel_fit=1)
        assert score >= 0.9
        result = gate.evaluate(contact=contact(opted_out=True),
                               case_id="c", business_purpose="x",
                               tenant_allows_outbound=True, now=DAY)
        assert result.result == "BLOCK"


class TestCallQuality:
    def test_quality_bounds_and_low_quality_flag(self):
        high = call_quality_score(asr_confidence=1, low_noise=1,
                                  speaker_clarity=1, goal_completed=1,
                                  sentiment=1, no_interruption_problems=1,
                                  evidence_completeness=1, no_escalation=1)
        assert high == 1.0
        low = call_quality_score(asr_confidence=.3, low_noise=.4,
                                 speaker_clarity=.3, goal_completed=.2,
                                 sentiment=.5, no_interruption_problems=.5,
                                 evidence_completeness=.3, no_escalation=1)
        assert low < 0.5


class TestHumanOverrides:
    def make(self, block, role, reason="client asked for extra contact",
             **kw):
        return HumanOverride(tenant_id="t1", case_id="c1", block_type=block,
                             original_decision="BLOCK",
                             override_decision="ALLOW", reason_text=reason,
                             approved_by_user_id="u1",
                             approved_by_role=role, **kw)

    def test_1_soft_block_manager_can_override(self):
        audit = AuditLog()
        assert decide_override(self.make("low_confidence_field", "manager"),
                               audit) == "APPROVED_OVERRIDE"
        assert audit.events(event_type="HUMAN_OVERRIDE_APPROVED")
        assert audit.events(event_type="BLOCK_OVERRIDE_APPLIED")
        assert audit.verify_chain()

    def test_2_hard_block_requires_owner(self):
        audit = AuditLog()
        assert decide_override(self.make("reopen_final_case", "manager"),
                               audit) == "REQUIRE_HIGHER_APPROVAL"
        assert decide_override(self.make("reopen_final_case", "owner"),
                               audit) == "APPROVED_OVERRIDE"

    def test_3_operator_cannot_override_hard(self):
        audit = AuditLog()
        assert decide_override(self.make("manual_payment_correction",
                                         "operator"), audit) \
            == "REQUIRE_HIGHER_APPROVAL"

    def test_4_ai_cannot_approve_own_action(self):
        audit = AuditLog()
        assert decide_override(self.make("low_confidence_field",
                                         "ai_worker"), audit) \
            == "REJECTED_OVERRIDE"

    def test_5_reason_required(self):
        audit = AuditLog()
        assert decide_override(self.make("low_confidence_field", "owner",
                                         reason="  "), audit) \
            == "REJECTED_OVERRIDE"

    def test_7_one_time_by_default(self):
        audit = AuditLog()
        ov = self.make("low_confidence_field", "owner")
        assert decide_override(ov, audit) == "APPROVED_OVERRIDE"
        assert decide_override(ov, audit) == "EXPIRED"     # second use

    def test_8_expired_override_unusable(self):
        audit = AuditLog()
        ov = self.make("low_confidence_field", "owner", expired=True)
        assert decide_override(ov, audit) == "EXPIRED"

    @pytest.mark.parametrize("block", [
        "opt_out", "do_not_call", "recording_without_consent",
        "wrong_number_auto_call", "emergency_to_sales_flow",
        "sensitive_without_identity", "bulk_campaign_without_compliance"])
    def test_10_to_14_non_overrideable_safety_blocks(self, block):
        audit = AuditLog()
        assert decide_override(self.make(block, "owner"), audit) \
            == "NON_OVERRIDEABLE"
        assert audit.events(event_type="NON_OVERRIDEABLE_BLOCK_CONFIRMED")

    def test_15_reopen_final_needs_owner(self):
        assert BLOCK_LEVELS["reopen_final_case"] != NON_OVERRIDEABLE
        audit = AuditLog()
        assert decide_override(self.make("reopen_final_case", "admin"),
                               audit) == "APPROVED_OVERRIDE"

    def test_17_pricing_message_after_owner_approval(self):
        audit = AuditLog()
        assert decide_override(self.make("pricing_message", "owner"),
                               audit) == "APPROVED_OVERRIDE"

    def test_19_audit_chain_valid_after_overrides(self):
        audit = AuditLog()
        decide_override(self.make("low_confidence_field", "owner"), audit)
        decide_override(self.make("opt_out", "owner"), audit)
        assert audit.verify_chain()


class TestPropertySeededTelephony:
    def test_hard_blockers_always_block(self):
        rng = random.Random(2026)
        gate = CallPermissionGate()
        for _ in range(300):
            c = contact(opted_out=rng.random() < .3,
                        do_not_call=rng.random() < .3,
                        explicit_refusal=rng.random() < .3,
                        wrong_number=rng.random() < .3,
                        calls_today=rng.randint(0, 3),
                        attempts_in_sequence=rng.randint(0, 4),
                        last_attempt_hours_ago=rng.uniform(0, 48))
            r = gate.evaluate(contact=c, case_id="c",
                              business_purpose="p",
                              tenant_allows_outbound=True, now=DAY)
            has_hard = (c.opted_out or c.do_not_call or c.explicit_refusal
                        or c.wrong_number or c.calls_today >= 2
                        or c.attempts_in_sequence >= 3)
            if has_hard:
                assert r.result == "BLOCK"
                assert r.hard_blockers

    def test_all_scenarios_end_with_disposition(self):
        rng = random.Random(7)
        eng = engine()
        scenarios = ["answered", "busy", "no_answer", "voicemail", "failed",
                     "answered_then_human", "answered_wrong_number",
                     "abandoned"]
        for i in range(60):
            c = contact(last_attempt_hours_ago=48)
            r = eng.request_outbound(
                tenant_id="t1", case_id=f"case-{i}",
                destination=f"+4860000{i:04d}", contact=c,
                business_purpose="p", scenario=rng.choice(scenarios),
                now=DAY)
            assert r.session.outcome in DISPOSITIONS
        assert eng.audit.verify_chain()

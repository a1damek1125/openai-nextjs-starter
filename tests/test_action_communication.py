"""Action & Communication Engine tests — 20 mandated cases + 3 E2E scenarios."""
from datetime import datetime, timedelta

import pytest

from finalis.audit import AuditLog
from finalis.case_services import MissingInfoService
from finalis.models import Case, MissingItem
from finalis.actions.engine import ActionCommunicationEngine
from finalis.actions.models import (ActionRequest, ChannelPreference,
                                    ConsentPreference)
from finalis.actions.services import (ChannelRouter, MessageComposeError,
                                      MessageComposer,
                                      UploadLinkGenerator)

T0 = datetime(2026, 7, 7, 11, 0)   # inside business hours


def make_engine():
    return ActionCommunicationEngine(AuditLog())


def make_case(level=3, **kw):
    case = Case(tenant_id="hvac-1", autonomy_level=level, **kw)
    case.next_best_action = {"type": "noop"}
    case.next_action_due_at = T0
    return case


def prefs(**kw):
    return ChannelPreference(tenant_id="hvac-1", party_id="p1", **kw)


def req(action_type, risk="low", **payload):
    return ActionRequest(tenant_id="hvac-1", case_id="", action_type=action_type,
                         reason="test", risk_level=risk, payload=payload)


class TestActionRequestAndGate:
    def test_1_action_request_created_and_audited(self):
        eng = make_engine()
        case = make_case()
        out = eng.handle(case, req("send_follow_up_after_offer",
                                   recipient="+48600100200"),
                         prefs=prefs(), consents=[], now=T0)
        assert out.status == "executed"
        assert eng.audit.events(event_type="ACTION_REQUESTED")

    def test_2_gate_allow_low_risk(self):
        eng = make_engine()
        out = eng.handle(make_case(), req("send_photo_request"),
                         prefs=prefs(), consents=[], now=T0)
        assert out.status == "executed"

    def test_3_gate_block_on_optout_case(self):
        eng = make_engine()
        case = make_case()
        case.opted_out = True
        out = eng.handle(case, req("send_follow_up_after_offer"),
                         prefs=prefs(), consents=[], now=T0)
        assert out.status == "blocked"

    def test_4_gate_requires_approval_for_high_risk(self):
        eng = make_engine()
        out = eng.handle(make_case(5), req("send_price_negotiation",
                                           risk="high"),
                         prefs=prefs(), consents=[], now=T0)
        assert out.status == "pending_approval"
        assert eng.audit.events(event_type="HUMAN_APPROVAL_REQUESTED")


class TestChannelRouter:
    def test_5_prefers_client_channel(self):
        r = ChannelRouter().route("send_photo_request",
                                  prefs(preferred_channel="sms"), [])
        assert r.channel == "sms" and r.fallback == "whatsapp"

    def test_6_falls_back_when_preferred_unavailable(self):
        p = prefs(preferred_channel="whatsapp",
                  available_channels=("sms", "email"))
        r = ChannelRouter().route("send_photo_request", p, [])
        assert r.channel == "sms"

    def test_optout_channel_excluded(self):
        consents = [ConsentPreference(tenant_id="hvac-1", party_id="p1",
                                      channel="whatsapp",
                                      status="opted_out")]
        r = ChannelRouter().route("send_photo_request", prefs(), consents)
        assert r.channel == "sms"


class TestMessageComposer:
    def test_7_missing_photo_message_polish_with_link(self):
        d = MessageComposer().compose(
            "send_photo_request", language="pl", channel="whatsapp",
            tenant_id="t", case_id="c", action_request_id="a",
            variables={"upload_link": "https://upload.finalis.example/u/x"})
        assert "zdjęcia obecnej instalacji" in d.text
        assert "tabliczki znamionowej" in d.text
        assert "https://upload.finalis.example/u/x" in d.text

    def test_8_composer_never_invents_price(self):
        d = MessageComposer().compose(
            "send_follow_up_after_offer", language="pl", channel="sms",
            tenant_id="t", case_id="c", action_request_id="a")
        import re
        assert not re.search(r"\d+\s*(zł|PLN|EUR|€)", d.text)
        # And injected price-like variables are rejected outright.
        with pytest.raises(MessageComposeError):
            MessageComposer().compose(
                "ask_for_missing_info", language="pl", channel="sms",
                tenant_id="t", case_id="c", action_request_id="a",
                variables={"items": ["rabat 500 zł"]})


class TestConsentAndRateLimits:
    def test_9_consent_gate_blocks_optout(self):
        eng = make_engine()
        consents = [ConsentPreference(tenant_id="hvac-1", party_id="p1",
                                      channel="any", status="opted_out")]
        out = eng.handle(make_case(), req("send_photo_request"),
                         prefs=prefs(), consents=consents, now=T0)
        assert out.status == "blocked"
        assert out.reason == "no_permitted_channel"

    def test_business_hours_defer_via_temporal(self):
        eng = make_engine()
        night = T0.replace(hour=23)
        out = eng.handle(make_case(), req("send_photo_request"),
                         prefs=prefs(), consents=[], now=night)
        assert out.status == "deferred"
        assert eng.temporal.scheduled       # durable deferred send
        assert eng.audit.events(event_type="ACTION_SCHEDULED")

    def test_10_rate_limit_prevents_duplicate_followup(self):
        eng = make_engine()
        case = make_case()
        first = eng.handle(case, req("send_photo_request"),
                           prefs=prefs(), consents=[], now=T0)
        second = eng.handle(case, req("send_photo_request"),
                            prefs=prefs(), consents=[],
                            now=T0 + timedelta(hours=1))
        assert first.status == "executed"
        assert second.status == "blocked"
        assert second.reason.startswith("rate_limited")
        assert eng.audit.events(event_type="FOLLOW_UP_RATE_LIMITED")

    def test_client_reply_pauses_followups(self):
        eng = make_engine()
        case = make_case()
        out = eng.handle(case, req("send_follow_up_after_offer"),
                         prefs=prefs(), consents=[], now=T0)
        eng.record_delivery(out.execution, status="replied",
                            provider_message_id="novu-1")
        nxt = eng.handle(case, req("send_follow_up_after_offer"),
                         prefs=prefs(), consents=[],
                         now=T0 + timedelta(days=2))
        assert nxt.status == "blocked"
        assert "paused_client_replied" in nxt.reason


class TestUploadLinks:
    def test_11_expiring_link_lifecycle(self):
        audit = AuditLog()
        gen = UploadLinkGenerator(audit)
        link, url = gen.create(tenant_id="t", case_id="c",
                               purpose="installation_photo", now=T0)
        token = url.rsplit("/", 1)[1]
        assert link.status == "CREATED"
        assert gen.open(token, T0 + timedelta(hours=1)) is not None
        assert gen.use(token, T0 + timedelta(hours=2),
                       mime="image/jpeg", size_mb=4)
        assert link.status == "USED"
        # Expired link refuses.
        link2, url2 = gen.create(tenant_id="t", case_id="c",
                                 purpose="doc", now=T0, ttl_hours=1)
        token2 = url2.rsplit("/", 1)[1]
        assert gen.open(token2, T0 + timedelta(days=1)) is None
        assert link2.status == "EXPIRED"
        # Bad mime refused.
        link3, url3 = gen.create(tenant_id="t", case_id="c",
                                 purpose="doc", now=T0)
        assert not gen.use(url3.rsplit("/", 1)[1], T0,
                           mime="application/x-msdownload", size_mb=1)


class TestAdapters:
    def test_12_temporal_mock_schedules_and_fires(self):
        eng = make_engine()
        case = make_case()
        eng.handle(case, req("send_photo_request"), prefs=prefs(),
                   consents=[], now=T0)
        assert eng.temporal.scheduled       # follow-up cadence scheduled
        due = eng.temporal.advance_to(T0 + timedelta(days=2))
        assert due and due[0]["workflow"] == "FollowUpWorkflow"
        assert eng.audit.events(event_type="TEMPORAL_WORKFLOW_COMPLETED")

    def test_13_novu_mock_sends(self):
        eng = make_engine()
        out = eng.handle(make_case(), req("notify_owner", owner="boss"),
                         prefs=prefs(), consents=[], now=T0)
        assert out.status == "executed"
        assert eng.novu.sent[0]["channel"] == "inbox"

    def test_14_chatwoot_mock_creates_handoff(self):
        eng = make_engine()
        out = eng.handle(make_case(),
                         req("handoff_to_human", recipient="+48600100200",
                             summary="Angry client, wants a manager"),
                         prefs=prefs(), consents=[], now=T0)
        assert out.status == "executed"
        conv = eng.chatwoot.conversations[0]
        assert conv["private_note"].startswith("Angry client")
        assert eng.audit.events(event_type="CHATWOOT_HANDOFF_CREATED")

    def test_provider_failure_uses_fallback_channel(self):
        eng = make_engine()
        eng.novu.fail_channels = {"whatsapp"}
        out = eng.handle(make_case(), req("send_photo_request"),
                         prefs=prefs(), consents=[], now=T0)
        assert out.status == "executed"
        assert out.execution.channel == "sms"     # fell back
        assert out.execution.retry_count == 1

    def test_15_delivery_event_updates_status(self):
        eng = make_engine()
        out = eng.handle(make_case(), req("send_photo_request"),
                         prefs=prefs(), consents=[], now=T0)
        ev = eng.record_delivery(out.execution, status="delivered",
                                 provider_message_id="novu-1")
        assert out.execution.status == "delivered"
        assert eng.audit.events(event_type="MESSAGE_DELIVERED")


class TestHumanApproval:
    def test_16_approve_edit_and_send(self):
        eng = make_engine()
        case = make_case(5)
        out = eng.handle(case, req("send_price_negotiation", risk="high",
                                   recipient="+48600100200"),
                         prefs=prefs(), consents=[], now=T0)
        assert out.status == "pending_approval"
        final = eng.decide_approval(out.approval_id, approver="owner-1",
                                    decision="approve", now=T0,
                                    edited_text="Dzień dobry, wracam do "
                                                "tematu oferty — zapraszam "
                                                "do kontaktu.")
        assert final.status == "executed"
        assert final.draft.approval_status == "APPROVED"
        assert final.draft.final_text.startswith("Dzień dobry, wracam")
        assert eng.audit.events(event_type="HUMAN_APPROVAL_GRANTED")

    def test_reject_records_reason(self):
        eng = make_engine()
        out = eng.handle(make_case(5), req("send_contract_response",
                                           risk="high"),
                         prefs=prefs(), consents=[], now=T0)
        final = eng.decide_approval(out.approval_id, approver="owner-1",
                                    decision="reject", now=T0,
                                    reason="needs lawyer")
        assert final.status == "blocked"
        assert final.draft.approval_status == "REJECTED"
        assert eng.audit.events(event_type="HUMAN_APPROVAL_REJECTED")


class TestE2EScenarios:
    def test_17_e2e_missing_photo_followup(self):
        """Scenario 1: full missing-photo flow with upload link + resolution."""
        eng = make_engine()
        case = make_case()
        case.missing_items = [
            MissingItem(field_key="installation_photo", label="photo",
                        weight=0.9, blocks_quote=True),
            MissingItem(field_key="address", label="address", weight=0.9,
                        blocks_quote=True)]

        out = eng.handle(case, req("send_photo_request",
                                   recipient="+48600100200",
                                   purpose="installation_photo"),
                         prefs=prefs(), consents=[], now=T0)
        assert out.status == "executed"
        assert out.upload_url and "upload.finalis.example" in out.upload_url
        assert out.upload_url in out.draft.final_text
        # Delivery + client opens + uploads.
        eng.record_delivery(out.execution, status="delivered",
                            provider_message_id="novu-1")
        token = out.upload_url.rsplit("/", 1)[1]
        assert eng.uploads.open(token, T0 + timedelta(hours=3))
        assert eng.uploads.use(token, T0 + timedelta(hours=4),
                               mime="image/jpeg", size_mb=3.2)
        # Case Graph update: missing item resolved, loop notified.
        assert MissingInfoService.resolve(case, "installation_photo",
                                          audit=eng.audit, source="upload")
        still = [m.field_key for m in case.missing_items
                 if m.status != "received"]
        assert still == ["address"]
        for ev in ["ACTION_REQUESTED", "UPLOAD_LINK_CREATED",
                   "MESSAGE_DRAFT_CREATED", "MESSAGE_SENT",
                   "MESSAGE_DELIVERED", "UPLOAD_LINK_OPENED",
                   "UPLOAD_LINK_USED", "MISSING_INFO_RESOLVED"]:
            assert eng.audit.events(event_type=ev), ev
        assert eng.audit.verify_chain()

    def test_18_e2e_offer_followup_after_72h(self):
        """Scenario 2: offer sent, no response → low-risk follow-up sent."""
        eng = make_engine()
        case = make_case()
        t = T0 + timedelta(hours=72)
        out = eng.handle(case, req("send_follow_up_after_offer",
                                   recipient="+48600100200"),
                         prefs=prefs(preferred_channel="email"),
                         consents=[], now=t)
        assert out.status == "executed"
        assert out.execution.channel == "email"
        assert "ofert" in out.draft.final_text
        assert not eng.approval_queue            # low risk: no approval
        assert eng.audit.verify_chain()

    def test_19_e2e_high_risk_approval_flow(self):
        """Scenario 3: price negotiation on a high-value case → approval."""
        eng = make_engine()
        case = make_case(4)
        case.value_estimate = 25000
        out = eng.handle(case, req("send_price_negotiation", risk="high",
                                   recipient="+48600100200"),
                         prefs=prefs(), consents=[], now=T0)
        assert out.status == "pending_approval"
        final = eng.decide_approval(out.approval_id, approver="owner-1",
                                    decision="approve", now=T0)
        assert final.status == "executed"
        for ev in ["HUMAN_APPROVAL_REQUESTED", "HUMAN_APPROVAL_GRANTED",
                   "MESSAGE_SENT"]:
            assert eng.audit.events(event_type=ev), ev

    def test_20_audit_written_for_all_important_steps(self):
        eng = make_engine()
        case = make_case()
        eng.handle(case, req("send_photo_request", recipient="x"),
                   prefs=prefs(), consents=[], now=T0)
        types = {e.event_type for e in eng.audit.events()}
        assert {"ACTION_REQUESTED", "ACTION_CREATED",
                "UPLOAD_LINK_CREATED", "MESSAGE_DRAFT_CREATED",
                "MESSAGE_SENT", "NOVU_NOTIFICATION_TRIGGERED",
                "TEMPORAL_WORKFLOW_STARTED"} <= types
        assert eng.audit.verify_chain()

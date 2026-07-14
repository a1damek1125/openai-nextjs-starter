"""Scheduling engine tests — availability, booking, states, lifecycle
integration, no-show, tokens, isolation-relevant invariants."""
import random
from datetime import datetime, timedelta

import pytest

from finalis.audit import AuditLog
from finalis.lifecycle.vector import (DealState, FulfillmentState,
                                      LifecycleVector, TransactionState)
from finalis.scheduling.engine import (APPOINTMENT_TYPES, SchedulingEngine,
                                       no_show_risk, slot_score)

DAY = datetime(2026, 7, 9, 0, 0)
AT10 = DAY.replace(hour=10)


def engine():
    return SchedulingEngine(AuditLog())


class TestAvailability:
    def test_1_slots_respect_business_hours(self):
        slots = engine().available_slots(day=DAY,
                                         appointment_type="VIDEO_CALL",
                                         limit=100)
        assert slots
        for s in slots:
            assert 8 <= s["start_at"].hour
            assert s["end_at"].hour <= 18

    def test_2_3_double_booking_and_buffers_blocked(self):
        eng = engine()
        eng.book(tenant_id="t1", case_id="c1",
                 appointment_type="TECHNICIAN_VISIT", start_at=AT10,
                 resource_id="tech-1")
        # Same resource overlapping → blocked.
        with pytest.raises(ValueError, match="double booking"):
            eng.book(tenant_id="t1", case_id="c2",
                     appointment_type="TECHNICIAN_VISIT",
                     start_at=AT10 + timedelta(hours=1),
                     resource_id="tech-1")
        # Inside the 15-min buffer after the 2h visit → still blocked.
        with pytest.raises(ValueError, match="double booking"):
            eng.book(tenant_id="t1", case_id="c3",
                     appointment_type="CALLBACK",
                     start_at=AT10 + timedelta(hours=2, minutes=5),
                     resource_id="tech-1")
        # After the buffer → allowed.
        appt, _ = eng.book(tenant_id="t1", case_id="c3",
                           appointment_type="CALLBACK",
                           start_at=AT10 + timedelta(hours=2, minutes=30),
                           resource_id="tech-1")
        assert appt.status == "CONFIRMED"

    def test_outside_hours_blocked(self):
        with pytest.raises(ValueError, match="business hours"):
            engine().book(tenant_id="t1", case_id="c1",
                          appointment_type="CALLBACK",
                          start_at=DAY.replace(hour=22))

    def test_resource_required(self):
        with pytest.raises(ValueError, match="resource required"):
            engine().book(tenant_id="t1", case_id="c1",
                          appointment_type="TECHNICIAN_VISIT",
                          start_at=AT10)

    def test_slots_exclude_booked_times(self):
        eng = engine()
        eng.book(tenant_id="t1", case_id="c1",
                 appointment_type="VIDEO_CALL", start_at=AT10,
                 user_id="u1")
        slots = eng.available_slots(day=DAY, appointment_type="VIDEO_CALL",
                                    user_id="u1", limit=100)
        for s in slots:
            assert not (s["start_at"] < AT10 + timedelta(minutes=45)
                        and s["end_at"] > AT10 - timedelta(minutes=15))


class TestBookingLifecycle:
    def test_5_6_book_and_confirm_video_call(self):
        eng = engine()
        appt, token = eng.book(tenant_id="t1", case_id="c1",
                               appointment_type="VIDEO_CALL",
                               start_at=AT10, user_id="u1")
        assert appt.status == "PENDING_CLIENT_CONFIRMATION"
        assert token and appt.confirmation_token_hash
        assert token not in appt.confirmation_token_hash    # hashed
        # 12: mock video link created and attached.
        assert appt.video_meeting_url.startswith(
            "https://meet.finalis.example/")
        confirmed = eng.confirm(token, now=AT10 - timedelta(hours=2))
        assert confirmed.status == "CONFIRMED"
        assert eng.audit.events(event_type="APPOINTMENT_CONFIRMED")

    def test_16_confirmation_token_expires_after_start(self):
        eng = engine()
        appt, token = eng.book(tenant_id="t1", case_id="c1",
                               appointment_type="VIDEO_CALL",
                               start_at=AT10, user_id="u1")
        assert eng.confirm(token, now=AT10 + timedelta(hours=1)) is None
        assert appt.status == "EXPIRED"
        assert eng.confirm("bogus-token", now=AT10) is None

    def test_7_reschedule_preserves_audit(self):
        eng = engine()
        appt, _ = eng.book(tenant_id="t1", case_id="c1",
                           appointment_type="CALLBACK", start_at=AT10)
        eng.reschedule(appt.id, new_start=AT10 + timedelta(hours=3),
                       actor="client")
        assert appt.status == "RESCHEDULED"
        assert appt.reschedule_count == 1
        ev = eng.audit.events(event_type="APPOINTMENT_RESCHEDULED")[0]
        assert "from" in ev.payload and "to" in ev.payload

    def test_8_cancel_requires_reason(self):
        eng = engine()
        appt, _ = eng.book(tenant_id="t1", case_id="c1",
                           appointment_type="CALLBACK", start_at=AT10)
        with pytest.raises(ValueError, match="reason"):
            eng.cancel(appt.id, reason="  ", by="client")
        eng.cancel(appt.id, reason="client unavailable", by="client")
        assert appt.status == "CANCELLED_BY_CLIENT"

    def test_9_no_show_flags_completion_loop(self):
        eng = engine()
        appt, _ = eng.book(tenant_id="t1", case_id="c1",
                           appointment_type="CALLBACK", start_at=AT10)
        eng.no_show(appt.id)
        ev = eng.audit.events(event_type="APPOINTMENT_NO_SHOW")[0]
        assert ev.payload["triggers_completion_loop"] is True


class TestLifecycleIntegration:
    def test_10_technician_visit_schedules_fulfillment(self):
        eng = engine()
        vector = LifecycleVector(deal=DealState.WON,
                                 transaction=TransactionState.PAID,
                                 fulfillment=FulfillmentState.REQUIRED)
        eng.book(tenant_id="t1", case_id="c1",
                 appointment_type="TECHNICIAN_VISIT", start_at=AT10,
                 resource_id="tech-1", vector=vector)
        assert vector.fulfillment is FulfillmentState.SCHEDULED
        assert vector.derived_outcome_view() == "WON_PAID_NOT_DELIVERED"
        assert eng.audit.events(event_type="FULFILLMENT_SCHEDULED")

    def test_11_completed_visit_completes_fulfillment(self):
        eng = engine()
        vector = LifecycleVector(deal=DealState.WON,
                                 transaction=TransactionState.PAID,
                                 fulfillment=FulfillmentState.REQUIRED)
        appt, _ = eng.book(tenant_id="t1", case_id="c1",
                           appointment_type="TECHNICIAN_VISIT",
                           start_at=AT10, resource_id="tech-1",
                           vector=vector)
        eng.complete(appt.id, vector=vector)
        assert vector.fulfillment is FulfillmentState.COMPLETED
        assert vector.derived_outcome_view() == "WON_COMPLETED"

    def test_video_call_does_not_touch_fulfillment(self):
        eng = engine()
        vector = LifecycleVector(fulfillment=FulfillmentState.REQUIRED)
        appt, _ = eng.book(tenant_id="t1", case_id="c1",
                           appointment_type="VIDEO_CALL", start_at=AT10,
                           vector=vector)
        eng.complete(appt.id, vector=vector)
        assert vector.fulfillment is FulfillmentState.REQUIRED


class TestScores:
    def test_no_show_risk_bounds(self):
        high = no_show_risk(prior_no_shows=1, unconfirmed=True,
                            days_until=14, low_engagement=1, weak_intent=1,
                            no_reminder=True, bad_time_fit=1)
        assert high == 1.0
        assert no_show_risk(prior_no_shows=0, unconfirmed=False,
                            days_until=0, low_engagement=0, weak_intent=0,
                            no_reminder=False, bad_time_fit=0) == 0.0

    def test_slot_score_penalties(self):
        base = slot_score(client_pref_fit=1, resource_fit=1, urgency_fit=1,
                          travel_efficiency=1, hours_fit=1, case_priority=1,
                          buffer_health=1, provider_reliability=1)
        risky = slot_score(client_pref_fit=1, resource_fit=1, urgency_fit=1,
                           travel_efficiency=1, hours_fit=1,
                           case_priority=1, buffer_health=1,
                           provider_reliability=1, conflict_risk=1,
                           no_show=1)
        assert base == 1.0 and risky < base

    def test_17_no_double_booking_property(self):
        """Property: random booking storms never produce an overlap on the
        same resource."""
        rng = random.Random(2026)
        eng = engine()
        booked = []
        for _ in range(80):
            hour = rng.randint(8, 15)
            minute = rng.choice([0, 30])
            start = DAY.replace(hour=hour, minute=minute)
            try:
                appt, _ = eng.book(tenant_id="t1",
                                   case_id=f"c{rng.randint(1, 9)}",
                                   appointment_type="VIDEO_CALL",
                                   start_at=start, user_id="u1")
                booked.append(appt)
            except ValueError:
                pass
        buffer = timedelta(minutes=15)
        for i, a in enumerate(booked):
            for b in booked[i + 1:]:
                assert a.start_at >= b.end_at + buffer \
                    or b.start_at >= a.end_at + buffer
        assert eng.audit.verify_chain()


class TestDemoFlow:
    def test_full_scheduling_demo(self):
        """Book → video link → client confirms → complete → lifecycle →
        audit chain verifies (the mandated local demo, engine-level)."""
        eng = engine()
        vector = LifecycleVector(deal=DealState.WON,
                                 transaction=TransactionState.PAID,
                                 fulfillment=FulfillmentState.REQUIRED)
        slots = eng.available_slots(day=DAY,
                                    appointment_type="TECHNICIAN_VISIT",
                                    resource_id="tech-1")
        assert slots
        appt, token = eng.book(tenant_id="t1", case_id="case-9",
                               appointment_type="TECHNICIAN_VISIT",
                               start_at=slots[0]["start_at"],
                               resource_id="tech-1", vector=vector)
        assert appt.status == "PENDING_CLIENT_CONFIRMATION"
        eng.confirm(token, now=slots[0]["start_at"] - timedelta(hours=4))
        assert appt.status == "CONFIRMED"
        eng.complete(appt.id, vector=vector)
        assert vector.derived_outcome_view() == "WON_COMPLETED"
        types = {e.event_type for e in eng.audit.events()}
        assert {"APPOINTMENT_BOOKED", "FULFILLMENT_SCHEDULED",
                "APPOINTMENT_CONFIRMED", "FULFILLMENT_COMPLETED",
                "APPOINTMENT_COMPLETED"} <= types
        booked_ev = eng.audit.events(event_type="APPOINTMENT_BOOKED")[0]
        assert booked_ev.payload["provider_is_mock"] is True
        assert eng.audit.verify_chain()

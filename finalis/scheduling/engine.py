"""Scheduling engine: availability, slots, appointments, video links,
no-show risk, and case/lifecycle integration."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Optional

from ..audit import AuditLog
from ..lifecycle.vector import FulfillmentState, LifecycleVector


def _uuid() -> str:
    return str(uuid.uuid4())


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


APPOINTMENT_TYPES = {
    "CALLBACK": {"duration_min": 15, "video": False, "resource": False,
                 "confirm": False, "advances_fulfillment": False},
    "VIDEO_CALL": {"duration_min": 30, "video": True, "resource": False,
                   "confirm": True, "advances_fulfillment": False},
    "PHONE_CALL": {"duration_min": 15, "video": False, "resource": False,
                   "confirm": False, "advances_fulfillment": False},
    "TECHNICIAN_VISIT": {"duration_min": 120, "video": False,
                         "resource": True, "confirm": True,
                         "advances_fulfillment": True},
    "SALES_CONSULTATION": {"duration_min": 45, "video": True,
                           "resource": False, "confirm": True,
                           "advances_fulfillment": False},
    "OFFER_REVIEW": {"duration_min": 30, "video": True, "resource": False,
                     "confirm": True, "advances_fulfillment": False},
    "SERVICE_DELIVERY": {"duration_min": 240, "video": False,
                         "resource": True, "confirm": True,
                         "advances_fulfillment": True},
    "POST_SALE_CHECKIN": {"duration_min": 15, "video": False,
                          "resource": False, "confirm": False,
                          "advances_fulfillment": False},
    "REVIEW_REQUEST": {"duration_min": 5, "video": False, "resource": False,
                       "confirm": False, "advances_fulfillment": False},
    "RECOVERY_LATER": {"duration_min": 15, "video": False,
                       "resource": False, "confirm": False,
                       "advances_fulfillment": False},
    "UPSELL_FOLLOWUP": {"duration_min": 20, "video": False,
                        "resource": False, "confirm": False,
                        "advances_fulfillment": False},
    "INTERNAL_TASK": {"duration_min": 30, "video": False, "resource": False,
                      "confirm": False, "advances_fulfillment": False},
}

STATES = {"PROPOSED", "HOLD_PLACED", "PENDING_CLIENT_CONFIRMATION",
          "CONFIRMED", "RESCHEDULE_REQUESTED", "RESCHEDULED",
          "CANCELLED_BY_CLIENT", "CANCELLED_BY_COMPANY", "NO_SHOW",
          "COMPLETED", "FAILED", "EXPIRED", "HUMAN_REVIEW_REQUIRED"}


@dataclass
class Appointment:
    tenant_id: str
    case_id: str
    appointment_type: str
    start_at: datetime
    end_at: datetime
    status: str = "PROPOSED"
    assigned_user_id: Optional[str] = None
    assigned_resource_id: Optional[str] = None
    video_meeting_url: Optional[str] = None
    requires_confirmation: bool = False
    confirmation_token_hash: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    reschedule_count: int = 0
    provider: str = "mock"
    provider_event_id: Optional[str] = None
    id: str = field(default_factory=_uuid)


class MockCalendarProvider:
    name = "mock-calendar"
    is_mock = True

    def create_event(self, appt: Appointment) -> str:
        return f"mockcal-{appt.id[:8]}"

    def delete_event(self, provider_event_id: str) -> None:
        pass


class MockVideoMeetingProvider:
    name = "mock-video"
    is_mock = True

    def create_meeting(self, appt: Appointment) -> str:
        return f"https://meet.finalis.example/room/{appt.id[:12]}"


def no_show_risk(*, prior_no_shows: float, unconfirmed: bool,
                 days_until: float, low_engagement: float,
                 weak_intent: float, no_reminder: bool,
                 bad_time_fit: float) -> float:
    return _clamp(0.25 * _clamp(prior_no_shows)
                  + (0.20 if unconfirmed else 0.0)
                  + 0.15 * _clamp(days_until / 14.0)
                  + 0.15 * _clamp(low_engagement)
                  + 0.10 * _clamp(weak_intent)
                  + (0.10 if no_reminder else 0.0)
                  + 0.05 * _clamp(bad_time_fit))


def slot_score(*, client_pref_fit: float, resource_fit: float,
               urgency_fit: float, travel_efficiency: float,
               hours_fit: float, case_priority: float,
               buffer_health: float, provider_reliability: float,
               conflict_risk: float = 0.0,
               no_show: float = 0.0) -> float:
    return _clamp(0.20 * _clamp(client_pref_fit)
                  + 0.20 * _clamp(resource_fit)
                  + 0.15 * _clamp(urgency_fit)
                  + 0.15 * _clamp(travel_efficiency)
                  + 0.10 * _clamp(hours_fit)
                  + 0.10 * _clamp(case_priority)
                  + 0.05 * _clamp(buffer_health)
                  + 0.05 * _clamp(provider_reliability)
                  - 0.20 * _clamp(conflict_risk)
                  - 0.15 * _clamp(no_show))


class SchedulingEngine:
    def __init__(self, audit: AuditLog,
                 business_hours: tuple[int, int] = (8, 18),
                 buffer_minutes: int = 15) -> None:
        self.audit = audit
        self.business_hours = business_hours
        self.buffer = timedelta(minutes=buffer_minutes)
        self.calendar = MockCalendarProvider()
        self.video = MockVideoMeetingProvider()
        self.appointments: dict[str, Appointment] = {}
        self._tokens: dict[str, str] = {}   # token_hash -> appointment_id

    # -- availability ------------------------------------------------------------
    def _conflicts(self, *, start: datetime, end: datetime,
                   user_id: Optional[str],
                   resource_id: Optional[str]) -> bool:
        for a in self.appointments.values():
            if a.status in ("CANCELLED_BY_CLIENT", "CANCELLED_BY_COMPANY",
                            "EXPIRED", "FAILED"):
                continue
            same_target = (user_id and a.assigned_user_id == user_id) or \
                (resource_id and a.assigned_resource_id == resource_id)
            if not same_target:
                continue
            if start < a.end_at + self.buffer \
                    and end > a.start_at - self.buffer:
                return True
        return False

    def available_slots(self, *, day: datetime, appointment_type: str,
                        user_id: Optional[str] = None,
                        resource_id: Optional[str] = None,
                        limit: int = 6) -> list[dict]:
        spec = APPOINTMENT_TYPES[appointment_type]
        duration = timedelta(minutes=spec["duration_min"])
        start_h, end_h = self.business_hours
        slots = []
        cursor = day.replace(hour=start_h, minute=0, second=0,
                             microsecond=0)
        day_end = day.replace(hour=end_h, minute=0, second=0, microsecond=0)
        while cursor + duration <= day_end and len(slots) < limit:
            if not self._conflicts(start=cursor, end=cursor + duration,
                                   user_id=user_id,
                                   resource_id=resource_id):
                slots.append({"start_at": cursor,
                              "end_at": cursor + duration,
                              "score": slot_score(
                                  client_pref_fit=0.7, resource_fit=1.0,
                                  urgency_fit=0.7, travel_efficiency=0.8,
                                  hours_fit=1.0, case_priority=0.6,
                                  buffer_health=1.0,
                                  provider_reliability=1.0)})
            cursor += timedelta(minutes=30)
        return slots

    # -- booking -----------------------------------------------------------------
    def book(self, *, tenant_id: str, case_id: str, appointment_type: str,
             start_at: datetime, user_id: Optional[str] = None,
             resource_id: Optional[str] = None,
             vector: Optional[LifecycleVector] = None
             ) -> tuple[Appointment, Optional[str]]:
        spec = APPOINTMENT_TYPES[appointment_type]
        end_at = start_at + timedelta(minutes=spec["duration_min"])
        # Hard blockers: business hours + double booking + resource need.
        start_h, end_h = self.business_hours
        if not (start_h <= start_at.hour
                and (end_at.hour < end_h
                     or (end_at.hour == end_h and end_at.minute == 0))):
            raise ValueError("outside business hours")
        if spec["resource"] and resource_id is None:
            raise ValueError("resource required for this appointment type")
        if self._conflicts(start=start_at, end=end_at, user_id=user_id,
                           resource_id=resource_id):
            raise ValueError("double booking not allowed")

        appt = Appointment(tenant_id=tenant_id, case_id=case_id,
                           appointment_type=appointment_type,
                           start_at=start_at, end_at=end_at,
                           assigned_user_id=user_id,
                           assigned_resource_id=resource_id,
                           requires_confirmation=spec["confirm"])
        appt.provider_event_id = self.calendar.create_event(appt)
        confirmation_token = None
        if spec["video"]:
            appt.video_meeting_url = self.video.create_meeting(appt)
        if spec["confirm"]:
            confirmation_token = secrets.token_urlsafe(16)
            appt.confirmation_token_hash = hashlib.sha256(
                confirmation_token.encode()).hexdigest()
            self._tokens[appt.confirmation_token_hash] = appt.id
            appt.status = "PENDING_CLIENT_CONFIRMATION"
        else:
            appt.status = "CONFIRMED"
        self.appointments[appt.id] = appt
        # Lifecycle integration: technician/service booking schedules
        # fulfillment when the playbook's fulfillment applies.
        if spec["advances_fulfillment"] and vector is not None:
            vector.fulfillment = FulfillmentState.SCHEDULED
            self.audit.append(event_type="FULFILLMENT_SCHEDULED",
                              actor="scheduling", case_id=case_id,
                              payload={"appointment_id": appt.id})
        self.audit.append(event_type="APPOINTMENT_BOOKED", actor="system",
                          case_id=case_id,
                          payload={"appointment_id": appt.id,
                                   "type": appointment_type,
                                   "start_at": str(start_at),
                                   "video": bool(appt.video_meeting_url),
                                   "provider_is_mock": True})
        return appt, confirmation_token

    def confirm(self, token: str, now: datetime) -> Optional[Appointment]:
        h = hashlib.sha256(token.encode()).hexdigest()
        appt_id = self._tokens.get(h)
        if appt_id is None:
            return None
        appt = self.appointments[appt_id]
        if now > appt.start_at:            # token useless after start
            appt.status = "EXPIRED"
            return None
        appt.status = "CONFIRMED"
        appt.confirmed_at = now
        self.audit.append(event_type="APPOINTMENT_CONFIRMED",
                          actor="client", case_id=appt.case_id,
                          payload={"appointment_id": appt.id})
        return appt

    def reschedule(self, appt_id: str, *, new_start: datetime,
                   actor: str) -> Appointment:
        appt = self.appointments[appt_id]
        spec = APPOINTMENT_TYPES[appt.appointment_type]
        old = appt.start_at
        new_end = new_start + timedelta(minutes=spec["duration_min"])
        if self._conflicts(start=new_start, end=new_end,
                           user_id=appt.assigned_user_id,
                           resource_id=appt.assigned_resource_id):
            raise ValueError("double booking not allowed")
        appt.start_at, appt.end_at = new_start, new_end
        appt.reschedule_count += 1
        appt.status = "RESCHEDULED"
        self.audit.append(event_type="APPOINTMENT_RESCHEDULED", actor=actor,
                          case_id=appt.case_id,
                          payload={"appointment_id": appt.id,
                                   "from": str(old), "to": str(new_start)})
        return appt

    def cancel(self, appt_id: str, *, reason: str, by: str) -> Appointment:
        if not reason.strip():
            raise ValueError("cancellation requires a reason")
        appt = self.appointments[appt_id]
        appt.status = "CANCELLED_BY_CLIENT" if by == "client" \
            else "CANCELLED_BY_COMPANY"
        appt.cancellation_reason = reason
        appt.cancelled_at = datetime.utcnow()
        self.audit.append(event_type="APPOINTMENT_CANCELLED", actor=by,
                          case_id=appt.case_id,
                          payload={"appointment_id": appt.id,
                                   "reason": reason})
        return appt

    def complete(self, appt_id: str, *,
                 vector: Optional[LifecycleVector] = None) -> Appointment:
        appt = self.appointments[appt_id]
        appt.status = "COMPLETED"
        spec = APPOINTMENT_TYPES[appt.appointment_type]
        if spec["advances_fulfillment"] and vector is not None:
            vector.fulfillment = FulfillmentState.COMPLETED
            self.audit.append(event_type="FULFILLMENT_COMPLETED",
                              actor="scheduling", case_id=appt.case_id,
                              payload={"appointment_id": appt.id})
        self.audit.append(event_type="APPOINTMENT_COMPLETED",
                          actor="system", case_id=appt.case_id,
                          payload={"appointment_id": appt.id})
        return appt

    def no_show(self, appt_id: str) -> Appointment:
        appt = self.appointments[appt_id]
        appt.status = "NO_SHOW"
        self.audit.append(event_type="APPOINTMENT_NO_SHOW", actor="system",
                          case_id=appt.case_id,
                          payload={"appointment_id": appt.id,
                                   "triggers_completion_loop": True})
        return appt

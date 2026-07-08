# Calendar & Scheduling Engine — Founder/CTO Report

**Branch**: `claude/finalis-calendar-scheduling-engine` · Tests: **384 passed**
(17 scheduling tests added; 367 baseline intact).

## Provider decision
Google Calendar / Microsoft Graph / Cal.com(Cal.diy) / Easy!Appointments /
Rallly / Jitsi / LiveKit / Meet / Teams are **provider adapters, never the
brain**. Local-first: MockCalendarProvider + MockVideoMeetingProvider
(Implemented and tested, `is_mock` marked in audit events). Real adapters:
SCAFFOLDED by the provider interface shape only — BLOCKED_BY_CREDENTIALS.
Recommended production order: Google Calendar + Microsoft Graph first (they
are where clients' calendars live), Cal.com self-hosted only if the tenant
wants client-facing booking pages beyond ours, LiveKit for video (already
the telephony path), Jitsi as the zero-cost fallback.

## Implemented and tested
- **12 appointment types** with per-type duration/video/resource/
  confirmation/fulfillment-advancement contracts.
- **Availability + slots**: business hours, existing bookings, 15-min
  buffers, resource requirements; SlotScore + NoShowRisk (bounded, tested).
- **Hard blockers over scores**: outside-hours, double-booking (property-
  tested with an 80-booking random storm — zero overlaps survive), missing
  resource.
- **Appointment state machine**: PROPOSED→PENDING_CLIENT_CONFIRMATION→
  CONFIRMED→COMPLETED, RESCHEDULED (audit keeps from/to), cancel-requires-
  reason, NO_SHOW (flags the Completion Loop), token EXPIRED after start.
- **Client confirmation tokens**: hashed (never stored raw), single-purpose,
  expire at appointment start.
- **Case/lifecycle integration**: technician/service bookings set
  `fulfillment=SCHEDULED`; completion sets `COMPLETED` → the case can reach
  `WON_COMPLETED` (tested end-to-end at engine level); video calls provably
  do NOT touch fulfillment.
- **Mock video links** attached to appointments and audited.

## Not yet wired (honest)
Portal REST endpoints + UI tabs (booking modal, client booking page,
scheduling dashboard) — the engine is portal-ready but the HTTP layer is the
next sprint; Google/Microsoft/Cal.com webhooks; timezone conversion beyond
naive local; travel-time; reminders via ACE (seam exists: NoShowRisk).

## Blocks pilot: portal wiring + reminder loop. Blocks production: real
calendar/video providers (credentials), timezone hardening, webhooks.

## Top next tasks
1. Portal endpoints (/scheduling/*) + case-detail scheduling tab.
2. Client booking page (token-scoped, like the upload page).
3. Reminder loop: NoShowRisk → ACE confirmation message.
4. Google Calendar adapter (first real provider).
5. LiveKit video rooms replacing mock links.

"""Finalis Calendar & Scheduling Engine — case-integrated scheduling.

Not a standalone calendar widget: every appointment progresses a case,
resolves a blocker, supports fulfillment/post-sale, or creates a next
action. Local-first: MockCalendarProvider + MockVideoMeetingProvider behind
the same interfaces Google Calendar / Microsoft Graph / Cal.com / LiveKit /
Jitsi adapters implement later. Providers are adapters — the brain stays
Case Graph + Completion Loop + Lifecycle + Action Gate + Audit.
"""

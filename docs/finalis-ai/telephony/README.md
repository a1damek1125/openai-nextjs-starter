# Finalis Telephony & Call Control Engine

Not the Voice Engine (what the AI says) — the call-control layer: how calls
are received, placed, gated, routed, retried, recorded-with-consent,
dispositioned, audited, and attached to cases.

**Status**: call-control logic **Implemented and tested** (49 tests +
6 API-level tests; 346 repo-wide) over **MockTelephonyProvider**. Real
telephony (LiveKit SIP) = Scaffolded interface, requires trunk + number.

Docs: architecture.md · provider-decision-record.md · call-state-machine.md ·
local-dev-simulation.md · security-consent-recording.md · founder-cto-report.md

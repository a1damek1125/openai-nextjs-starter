"""Finalis Telephony & Call Control Engine.

Not the Voice Engine (what the AI says) — the call-control layer (how calls
are received, placed, gated, routed, retried, recorded-with-consent,
dispositioned, audited, and attached to cases).

Production path: LiveKit SIP + LiveKit Agents (ADR in docs/finalis-ai/
telephony/). Local dev: MockTelephonyProvider behind the same interface —
no phone numbers, trunks, or credentials required. Asterisk/FreePBX/
FreeSWITCH remain optional adapters; Kamailio only for future SIP edge scale.
"""

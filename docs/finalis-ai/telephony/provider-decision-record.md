# Telephony Provider Decision Record

**Decision: LiveKit SIP + LiveKit Agents = preferred production path.**
Rationale (verified in the voice-stack research pass): Apache-2.0 end to end,
livekit/sip is a purpose-built SIP↔room bridge into the same media server the
voice agents use; avoids operating a GPL PBX; Pipecat pipelines attach via
the native LiveKit transport.

- **Local now**: MockTelephonyProvider (Implemented and tested) — full
  lifecycle simulation (answered/busy/no-answer/voicemail/failed/handoff/
  wrong-number/abandoned), deterministic scenarios.
- **Optional adapters (Scaffolded interfaces only)**: Asterisk (GPL-2, as a
  separate process), FreePBX, FreeSWITCH (MPL-1.1), GenericSipProvider — only
  for customers with existing PBX. Kamailio: future SIP edge at scale only.
- **Commercial benchmarks (Vapi/Retell/Bland)**: comparison references only,
  never Finalis core — the brain (gates/consent/audit) must stay ours.
- **Requires later**: SIP trunk contract, phone numbers, LiveKit server
  deployment (already in docker-compose path), per-tenant number mapping.

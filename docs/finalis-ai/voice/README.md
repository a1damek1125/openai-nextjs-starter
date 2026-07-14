# Finalis Voice Engine — Documentation Set

> Branch: `claude/finalis-voice-engine-open-core` · Status date: 2026-07-07

## Mission

Finalis Voice is **self-hosted, open-source, voice-first case intake — not a voice
bot**. A call is not a conversation to be survived; it is the first structured event
in a case's life. The engine's job is to turn spoken client contact (WebRTC or a
phone call) into a Case Graph entry with verified facts, explicit unknowns
(missing items), captured promises, and a next best action — under the same audit,
autonomy-gate, and no-hallucination rules as every other Finalis channel. Every
component in the stack is open source and runs on infrastructure we control; no
audio, transcript, or case data ever leaves the tenant's deployment.

## Current honest status

| Layer | Status |
|---|---|
| Transcript-level voice scaffold (`finalis/voice/`) | **Implemented and tested** — session lifecycle, ASR/TTS routing with failover, dialogue policy, understanding extraction, barge-in handling, human handoff, Case Graph connection, audit chain. 26 passing tests over the 12 mandated call scenarios. |
| Real audio path (WebRTC/SIP transport, VAD, turn detection, real ASR/TTS engines) | **Designed** — component choices verified (see [open-source-stack.md](open-source-stack.md)); engines plug in behind protocols the scaffold already defines and tests. |
| Latency metrics | **Honestly not measured** — `VoiceMetric.measured` is `False` and all latency fields are `None` in the transcript scaffold; they only become real numbers on the audio path. |

Test command and result (repo root):

```
python3 -m pytest tests/ -q          # 128 passed (repo-wide)
python3 -m pytest tests/test_voice_engine.py -q   # 26 passed (voice)
```

## Acceptance rule

**Nothing in this doc set is labeled "Implemented" unless it is executable code in
this repository covered by passing tests you can run with the command above.
Everything else is labeled "Designed".** Verified external research claims carry
tags: `[VP]` = verified against a primary source, `[S]` = corroborated search
snippet, `[U]` = unverified assumption that must be checked before GA.

## Two deployment modes

1. **WebRTC-first (default).** Browser/mobile client → self-hosted LiveKit server
   (Apache-2.0 SFU) → Pipecat pipeline. Zero telco dependency; for small
   single-tenant installs, Pipecat's `SmallWebRTCTransport` runs P2P with no
   external infra at all.
2. **Telephony (PSTN).** A SIP trunk from any carrier terminates on the
   Apache-2.0 `livekit/sip` bridge, which places the call into a LiveKit room —
   the pipeline is then identical to mode 1. No GPL PBX required.

In both modes, the scaffold's `channel` field (`webrtc | sip | test_transcript`)
records the entry point; `test_transcript` is the executable simulation lane used
by the test suite today.

## Doc set index (12 files)

| # | File | Contents | Status |
|---|---|---|---|
| 1 | [README.md](README.md) | This index, mission, status, acceptance rule | Written |
| 2 | [architecture.md](architecture.md) | 10 components, pipeline diagram, 16-step session flow, barge-in/turn handling | Written |
| 3 | [open-source-stack.md](open-source-stack.md) | Full stack decisions, license matrix, language routing, GA action items, R&D watchlist | Written |
| 4 | scaffold-implementation.md | File-by-file walkthrough of `finalis/voice/` and its seams | Planned |
| 5 | dialogue-policy.md | Question ordering, hard stops, price guard, playbook data format | Planned |
| 6 | language-support.md | PL/DE/ES/EN handling, mixed-language calls, extraction pattern tables per language | Planned |
| 7 | webrtc-deployment.md | LiveKit server + Pipecat deployment, TURN, scaling | Planned |
| 8 | telephony.md | SIP trunk setup, livekit/sip bridge, number provisioning, carrier notes | Planned |
| 9 | evaluation.md | The 12 mandated scenarios, audio-path eval plan, Full-Duplex-Bench-v3 alignment | Planned |
| 10 | security-privacy.md | Consent, recording policy, retention, tenant isolation, audit chain | Planned |
| 11 | operations.md | GPU/CPU sizing, model serving (vLLM/SGLang), monitoring, failover runbooks | Planned |
| 12 | roadmap.md | Transcript scaffold → audio alpha → telephony GA milestones | Planned |

Related pre-existing docs: `docs/finalis-ai/06-voice-architecture.md`,
`28-voice-verification-and-test-plan.md`, `41-voice-e2e-readiness-report.md`.

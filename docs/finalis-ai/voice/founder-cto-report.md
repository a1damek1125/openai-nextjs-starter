# Finalis Voice Engine — Founder / CTO Report

**Date**: 2026-07-07 · **Branch**: `claude/finalis-voice-engine-open-core`
**Test command**: `python3 -m pytest tests/ -q` → **128 passed** (26 voice-specific;
no network, GPU, or keys required).

Wording discipline: **Implemented and tested** = passing tests · **Mocked** = mock behind a
production interface · **Designed** = docs only · **Not production-ready** unless enterprise
criteria pass.

---

## The 16 direct answers

**1. What was implemented?**
The transcript-level voice engine core, executable and tested: `VoiceSession`/`Utterance`/
`VoiceExtraction`/`VoiceMetric` models; **ASR Router** (primary→fallback failover on crash or
confidence <0.4, language normalization); **TTS Router** (language-aware selection, fallback
on error, barge-in `stop()`); **Understanding Extractor** (rule-based EN+PL: intent, service
type, name/address/date/brand with per-field confidence + status, urgency, corrections-
overwrite, promises with due dates, objections, handoff triggers, out-of-scope, returning-
client reference); **Dialogue policy** (greeting, one question at a time in priority order,
no-price-without-data line, out-of-scope decline, handoff line); **Case Graph connector**
(creates/updates `Case`, writes `MissingItem`/`Promise` rows, sets `next_best_action` +
due time, creates follow-up tasks from photo promises); **audit events** on the shared
hash-chained log (CALL_STARTED, BARGE_IN, INTENT_DETECTED, MISSING_INFO_DETECTED,
PROMISE_DETECTED, NEXT_ACTION_CREATED, HUMAN_HANDOFF, CALL_ENDED); **human handoff** (request/
anger/legal/medical triggers, session `handed_off`, human-approval-required next action);
**consent flag** (no consent → nothing recorded); **ActionGate** via the existing autonomy
gate; **LGGT Phase-1 seam** (every session output certified by the NullAdapter with an
`audit_id`). All 12 mandated E2E scenarios pass, plus router, no-hallucination, consent, and
metrics-honesty tests.

**2. What is only documented?**
The real-time audio path end to end: WebRTC/SIP transport, audio preprocessing (VAD, noise
suppression, echo cancellation), real turn detection, streaming, latency behavior, the
`/voice/sessions` REST surface, PII redaction, quotas, observability. (architecture.md,
api-contracts.md, enterprise-controls.md)

**3. What is mocked?**
ASR (`MockASR` replays fixture annotations — text/confidence/language/uncertain-terms exactly
as a real ASR would emit them), TTS (`MockTTS` records spoken lines), and the LLM (the
dialogue policy is scripted; the extractor is rule-based). Each mock sits behind the
production protocol (`ASRService`, `TTSService`), so swapping in Parakeet/ZONOS2/vLLM changes
adapters, not logic.

**4. What is missing?**
Real engines (ASR/TTS/LLM), transports (LiveKit server, livekit/sip, Pipecat pipeline), the
REST API, persistence, audio fixtures, latency measurement, and the enterprise hardening
listed in enterprise-controls.md.

**5. Does real audio work?** **No.** Zero audio code exists. Transcript simulation only —
stated everywhere, per the critical rule.

**6. Does transcript simulation work?** **Yes — implemented and tested.** 12 scenarios + 
cross-cutting invariants, 26 tests passing.

**7. Does ASR work or is it mocked?** **Mocked** (fixture-driven), with the *router* logic
(failover, language normalization) implemented and tested. Production picks (verified
2026-07-07): **Parakeet TDT 0.6B v3** primary (CC-BY-4.0, Polish+DE+ES+EN, RTFx ~3300,
chunked not native-streaming), **faster-whisper large-v3** fallback (MIT, best open Polish
WER). Voxtral Realtime is Apache-2.0 and fast but has **no Polish** — DE/ES/EN lane only.

**8. Does TTS work or is it mocked?** **Mocked**, router tested. Production picks: **ZONOS2**
primary (MIT repo license, streaming server, **Polish Tier 3** — 3 weeks old, needs a Polish
quality bake-off + HF weights-license confirmation), **Piper** fallback (proven Polish
voices; original MIT build archived — successor is GPL-3.0, run as a separate process),
**Qwen3-TTS** for DE/ES/EN (Apache-2.0, 97 ms streaming, **no Polish**).

**9. Does the voice system understand calls?** At the **transcript level, yes, within the
rule-based envelope** — intents, fields with confidence, corrections, promises, objections,
handoff triggers, mixed PL/DE language detection — all tested. It does NOT do open-ended
LLM-grade understanding yet; that lands in VS4 (vLLM + Qwen3-30B-A3B) behind the same
extractor interface, with the rule layer retained as a validation net.

**10. Does it extract promises and missing info?** **Yes — implemented and tested.** "I'll
send you the photos tomorrow" → `Promise{who: client, what: send photos, due: tomorrow,
confidence 0.87}` + a `followup_if_no_photos` task + PROMISE_DETECTED audit. Missing items
derive from the HVAC required-field playbook; an uncertain value stays a missing item
(`value_present_but_uncertain`).

**11. Does it update Case Graph?** **Yes — implemented and tested.** Sessions create or link
a `Case` (returning-client scenario links, never duplicates; out-of-scope creates nothing),
write MissingItems/Promises, and set `next_best_action` + due time — feeding the same
Completion Loop tested in the core scaffold.

**12. Does it create audit events?** **Yes — implemented and tested**, on the shared
hash-chained `AuditLog`; chain verified in every test run.

**13. Does human handoff work?** **Yes at the logic level — implemented and tested** for
explicit request, anger, and legal/medical asks; low-ASR-confidence-on-critical-data is
partially covered via uncertain-status (a full confidence-triggered handoff rule is in the
backlog). Real warm-transfer audio handoff = Designed.

**14. Is it enterprise-ready?** **No — not production-ready.** Implemented+tested: tenant_id
on every session, consent gating, audit chain, fallback routing, HITL. Designed-only: PII
redaction, retention execution, RLS, quotas, health checks, observability, kill switch.
(enterprise-controls.md, production-readiness-matrix.md)

**15. What blocks production?**
No real audio path; no measured latency (all latency metrics honestly `None`/`measured=False`);
no persistence/API; ZONOS2 Polish quality + weights license unconfirmed; enterprise gaps
above; telecom provisioning (SIP trunk/number — acceptable external infra cost).

**16. What is the next sprint?**
**VS1 (implementation-backlog.md): the real-time loop** — Pipecat 1.5 pipeline +
SmallWebRTCTransport + Silero VAD + **Smart Turn v3** (BSD-2, 23 langs incl. Polish, 12–60 ms
CPU — the deciding reason Pipecat beat LiveKit Agents as framework), with mock ASR/TTS still
in place, plus first TTFA latency measurements. Then VS2 ASR lane, VS3 TTS lane, VS4 LLM
dialogue.

---

## Verified / not verified

**Verified by tests (26):** session lifecycle + consent; barge-in stop + audit; one-question-
at-a-time; intent/field extraction with correction-overwrite; uncertain-term ceiling (an
ASR-flagged brand can never become "confirmed"); promise→task pipeline; missing-info
derivation; refusal risk flag; no-price-without-data; handoff (request + anger); out-of-scope
no-case; returning-client linking; ASR failover (crash + low-confidence); TTS language
selection + fallback + interruption counting; no-hallucination invariant across 6 scenarios;
metrics honesty (`measured=False`); audit chain integrity everywhere.

**Not verified:** anything involving actual sound, actual models, actual networks, actual
latency, or actual Polish speech quality. Stack choices are research-verified
(open-source-stack.md, with [VP]/[S] tags) but not yet load-tested by us.

## Top 10 next tasks
1. VS1: Pipecat pipeline + SmallWebRTCTransport + Smart Turn v3 + Silero VAD; measure TTFA.
2. VS2: self-host Parakeet TDT 0.6B v3 (NeMo) + faster-whisper fallback; validate Polish WER
   on the BIGOS/amu-cai leaderboard protocol.
3. VS3: ZONOS2 streaming server + Piper fallback; confirm ZONOS2 HF weights license; Polish
   MOS bake-off.
4. VS4: vLLM + Qwen3-30B-A3B dialogue + tool calling behind the extractor interface (rule
   layer kept as validator); evaluate Bielik-11B for Polish.
5. VS5: LiveKit server + livekit/sip; provision a test number/trunk.
6. `/voice/sessions` REST endpoints + persistence for VoiceSession/Utterance/Extraction.
7. Evaluation harness Stage 2: synthetic-audio tests (TTS-generated speech → real ASR).
8. Enterprise: PII redaction filter, per-tenant session quota, health checks.
9. Low-ASR-confidence-on-critical-data handoff rule (upgrade from uncertain-status partial).
10. Audio fixture library: the 12 scenarios recorded in PL/DE/ES/EN with accent/noise
    variants (36).

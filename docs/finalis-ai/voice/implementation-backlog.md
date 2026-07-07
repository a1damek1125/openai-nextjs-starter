# Finalis Voice Engine — Implementation Backlog (scaffold → production)

> Starting point: the transcript-level scaffold on `claude/finalis-voice-engine-open-core`
> (`finalis/voice/` — engine, extractor, routers, models; 26 passing voice tests). The
> scaffold's contract is the load-bearing asset: **everything downstream of the ASR router
> stays identical** (engine.py module docstring) — these sprints replace the input iterator
> and the mocks, not the logic. Sprint order is dependency order; VS2/VS3 can run in
> parallel after VS1.

---

## VS1 — Real-time loop

**Objective**: replace the fixture-chunk iterator with a live streaming audio pipeline:
**Pipecat** pipeline + **SmallWebRTCTransport** (browser calls first — no telephony infra
needed), **Silero VAD** for speech detection, **Smart Turn v3** for semantic end-of-utterance,
mock ASR/TTS swapped for real engines behind the existing routers, and latency
instrumentation filling `VoiceMetric` with real numbers.

- **Files/modules**: new `finalis/voice/realtime.py` (Pipecat pipeline assembly, transport,
  VAD/turn config); `finalis/voice/engine.py` gains an async per-utterance entry point
  (refactor `run_call`'s per-chunk body into `on_utterance()`); `finalis/voice/models.py`
  `VoiceMetric` populated from pipeline timestamps (`measured=True` only then).
- **Dependencies**: none (first sprint); real ASR/TTS can initially be any hosted engine —
  VS2/VS3 harden the choice.
- **Acceptance criteria**: a browser call completes S1 end-to-end with spoken audio; barge-in
  physically stops audio output; `VoiceMetric.measured == True` with real
  p50/p95/asr/llm/tts latencies; existing transcript tests still pass unchanged (the mock
  path remains the CI path).
- **Tests**: harness Stage 2 smoke (synthetic audio for S1/S2/S6); unit tests for
  utterance-boundary assembly (partials → final); latency-injection test verifying the
  fallback-when-slow filler phrase (doc 06 §3).
- **Risks**: turn-detection quality dominates perceived latency (Smart Turn v3 mitigates but
  needs PL validation); async refactor of `run_call` is the one place scaffold logic is
  touched — regression risk covered by keeping all 26 tests green on the sync path.

## VS2 — ASR lane

**Objective**: production ASR: **Parakeet-v3 self-hosted via NeMo** as primary,
**faster-whisper large-v3** as fallback, language routing (PL/DE/ES/EN), and Polish WER
validation on **BIGOS** (cross-checked against amu-cai/pl-asr-leaderboard).

- **Files/modules**: `finalis/voice/asr_engines.py` (two `ASRService` implementations —
  streaming NeMo client, faster-whisper worker); `finalis/voice/routers.py` unchanged (the
  failover contract is already tested); deployment manifests for the GPU ASR service.
- **Dependencies**: VS1 (audio frames to transcribe); GPU capacity.
- **Acceptance criteria**: PL WER within 10% relative of the pl-asr-leaderboard reference for
  the chosen model on BIGOS; critical-slot entity accuracy reported on own fixtures;
  streaming final ≤ 500 ms after end-of-utterance; failover to faster-whisper on primary
  crash/low-confidence observed in an injected-fault test; per-utterance `confidence` and
  `uncertain_terms` populated (S11's uncertain-value contract must hold on real ASR output).
- **Tests**: router failover tests re-run against real engines (fault injection); WER
  regression job on the BIGOS subset in CI-nightly; language-routing tests for the S8
  mixed-language case.
- **Risks**: Parakeet-v3 PL entity accuracy on brands/addresses unproven → bake-off protocol
  (harness §3.1) decides, router makes the swap cheap; `uncertain_terms` requires
  word-level confidence — verify the engine exposes it, else derive from lattice/logprobs.

## VS3 — TTS lane

**Objective**: production TTS: **ZONOS2 streaming server** as primary, **Piper** as fallback,
**license confirmation for commercial self-hosting (hard gate before any deploy)**, Polish
MOS bake-off (ZONOS2 vs Piper), Qwen3-TTS evaluated for DE/ES/EN.

- **Files/modules**: `finalis/voice/tts_engines.py` (`TTSService` implementations with
  streaming synthesis + hard stop for barge-in); `TTSRouter` unchanged; voice-profile config
  per tenant.
- **Dependencies**: VS1 (audio out path).
- **Acceptance criteria**: ZONOS2 license verified compatible with commercial self-hosting
  (blocker if not — Piper promotes to primary); first audio frame ≤ 200 ms P50; hard stop
  ≤ 200 ms on barge-in signal (the physical half of the tested `TTSRouter.stop()` logic);
  PL MOS study completed with documented result; language-aware routing serves all four
  languages.
- **Tests**: barge-in protocol (harness §7) at Stage 2; number/address/date readback
  intelligibility set; router fallback under synthesized engine failure.
- **Risks**: license outcome (explicit gate above); streaming-stop granularity — if the
  engine can't abort mid-chunk, buffer in ≤100 ms frames at the transport.

## VS4 — LLM dialogue

**Objective**: replace the scripted dialogue policy and rule-based extractor with an LLM:
**vLLM serving Qwen3-30B-A3B**, playbook-driven prompting (the `QUESTION_ORDER`/`QUESTIONS`
policy becomes playbook data), tool calling for case-graph reads and next-action proposals —
**keeping the rule-based extractor as a validation layer** (disagreement ⇒ field downgraded
to `uncertain`, never silently trusting the LLM).

- **Files/modules**: `finalis/voice/llm_dialogue.py` (prompt assembly, streaming decode,
  tool schema); `finalis/voice/extractor.py` retained and wrapped as `RuleValidator`;
  `engine.py` swaps the question-selection block for LLM turns behind a feature flag.
- **Dependencies**: VS1; VS2 (real transcripts to prompt on); GPU pool sizing with VS2/VS3.
- **Acceptance criteria**: all 12 Stage-1 scenarios pass with the LLM policy (same
  assertions — one question at a time, no price without data, handoff honored first
  request); intent ≥ 0.9 / slot F1 ≥ 0.85 on the expanded held-out set (harness §5);
  first-token latency inside the 800 ms turn budget; every LLM-asserted field carries
  `source_utterance_ids`; validator-disagreement rate tracked and alertable.
- **Tests**: Stage-1 suite re-run with LLM policy (flag on) in CI-nightly; adversarial set
  (prompt-injection via caller speech, off-playbook promises, price-baiting — S12's
  invariant re-proven statistically); hallucination gate ~0 on evidence-required outputs.
- **Risks**: the single biggest behavioral risk in the program — an LLM can invent values
  the rules never could; mitigations: rule-validator layer, `uncertain`-status downgrade,
  ActionGate on every proposal, Phase-2 LGGT class 5 (critical-answer permission) lands
  here. Latency risk: 30B-A3B MoE chosen for decode speed; measure before committing.

## VS5 — Telephony

**Objective**: real phone calls: **LiveKit server** + **livekit/sip** bridge, number/trunk
provisioning per tenant, PSTN ↔ pipeline audio interop.

- **Files/modules**: `finalis/voice/telephony.py` (LiveKit room/session mapping →
  `VoiceSession(channel="sip")`); infra: LiveKit deployment, SIP trunk config, per-tenant
  number inventory.
- **Dependencies**: VS1 (pipeline); provider contracts (trunk + numbers).
- **Acceptance criteria**: inbound PSTN call reaches the pipeline and completes S1; caller
  number lands in session metadata (the output's `client.phone` slot — currently `None` by
  design); 8 kHz telephone-band cohort of the harness passes its WER/slot gates; per-tenant
  number → tenant routing proven (no cross-tenant call delivery); concurrent-call cap
  enforced at the trunk edge.
- **Tests**: SIP loopback e2e in staging; codec/band degradation cohort (harness §6);
  failover behavior when LiveKit or trunk drops mid-call (case gets a callback task — never
  a silently lost case).
- **Risks**: two transports now exist (SmallWebRTC from VS1, LiveKit for SIP) — either
  consolidate on LiveKit transport for both or explicitly maintain two Pipecat transports;
  telco provisioning lead times are calendar risk, start contracts early.

## VS6 — Evaluation stages 2–3 + enterprise hardening

**Objective**: turn the harness doc into running infrastructure (Stage-2 synthetic-audio
suite, Stage-3 consented-recording suite) and close the enterprise-controls gaps: full
consent flows (spoken prompt, revocation, jurisdiction scripts), PII redaction filter before
every log sink, per-tenant quotas (minutes + concurrency), health checks, kill switch.

- **Files/modules**: `evals/voice/` (audio fixture generation, caller bot, metric
  aggregation); `finalis/voice/consent.py`; logging filter in the service skeleton;
  quota/kill-switch config plumbing.
- **Dependencies**: VS1–VS3 (something real to evaluate); VS5 for the telephone-band cohort.
- **Acceptance criteria**: the acceptance criteria enumerated per control in
  `enterprise-controls.md` §§1–6 (consent fail-closed, canary-PII log test, RLS suite,
  quota enforcement, kill-switch drill ≤ 60 s); Stage-2 suite runs nightly with trend
  dashboards; Stage-3 cohort collected under consent with human reference transcripts.
- **Tests**: this sprint IS tests + controls; additionally chaos drills (engine outage →
  router fallback → degradation ladder) and the retention-deletion job test.
- **Risks**: consented-recording collection is slow (people + legal) — start recruitment at
  VS2; redaction filters have long false-negative tails — canary approach plus periodic
  human log audits.

## VS7 — API surface

**Objective**: expose voice over the doc-22 API: `/voice/sessions` endpoints — create
(returns WebRTC/SIP join credentials), get (status, summary, extractions, `certainty_audit_id`),
list (tenant-scoped), transcript retrieval (consent- and role-gated), plus webhook events
(`voice.session.ended`, `voice.handoff.requested`) with signed delivery.

- **Files/modules**: API layer (service repo) mapping to `VoiceEngine`/`VoiceSession`;
  OpenAPI additions to `docs/finalis-ai/openapi.finalis.yaml`; persistence for
  sessions/utterances/extractions/metrics with RLS (this is where the scaffold's dataclasses
  get tables).
- **Dependencies**: VS1 (sessions to expose); VS6 controls (must not ship endpoints before
  redaction/RLS/consent gating exist — fail-closed ordering).
- **Acceptance criteria**: session lifecycle drivable end-to-end via API; the session-output
  JSON contract equals `_build_output`'s shape (the 12 scenarios' assertions become API
  contract tests); RLS suite green across all endpoints; webhooks signed + replay-protected;
  transcript endpoint access audit-logged.
- **Tests**: contract tests generated from the Stage-1 scenario outputs; authz matrix tests;
  webhook signature/replay tests.
- **Risks**: freezing the output JSON as public API — version it (`/v1`) from day one; the
  scaffold contract is good but `client.phone`/recording URIs arrive only with VS5/consent
  work, so document nullable fields explicitly.

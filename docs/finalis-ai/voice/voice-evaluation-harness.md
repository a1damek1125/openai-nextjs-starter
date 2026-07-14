# Finalis Voice Engine — Evaluation Harness

> Refines `28-voice-verification-and-test-plan.md` now that an executable scaffold exists on
> branch `claude/finalis-voice-engine-open-core`. Ground truth: `finalis/voice/` with 26
> passing voice tests (`tests/test_voice_engine.py`, fixtures in `tests/voice_fixtures.py`);
> real audio, ASR, and TTS are **mocked**. Every latency number below is a **target from
> `06-voice-architecture.md` §3 — nothing has been measured**, because the scaffold is
> transcript-only and `VoiceMetric.measured` is honestly hard-coded `False`
> (`finalis/voice/models.py`, asserted in `TestSessionAndConsent::test_metrics_marked_not_measured`).

---

## 1. Harness stages

### Stage 1 — Transcript-based (IMPLEMENTED — the 12 scenarios ARE the harness v0)

Status: **done and running in CI.** The 12 fixture scenarios in `tests/voice_fixtures.py`
(S1 normal quote … S12 price-without-data), executed by `tests/test_voice_engine.py` against
`VoiceEngine.run_call()` with `MockASR`/`MockTTS` (`finalis/voice/routers.py`), are Stage 1
of this harness — not a precursor to it. Doc 28's "Stage A" is exactly what this delivers:

- Fixture format: a "call" is a list of audio-chunk dicts carrying `text`, `confidence`,
  `language`, `uncertain_terms`, `barge_in`, `start_ms`/`end_ms` — the mock ASR returns
  these as `TranscriptChunk`s, so the entire downstream pipeline (dialogue policy,
  extraction, missing-info, promises, handoff, case update, audit, certainty stamp) runs
  for real.
- Assertions per scenario: intent, extracted fields (with `unknown | uncertain | confirmed`
  status), missing items, promises + tasks, next action + autonomy gating, handoff, audit
  events, hash-chain integrity (`audit.verify_chain()`), and the cross-scenario
  no-hallucination invariant (`TestNoHallucination`).
- What Stage 1 measures: **behavioral correctness only.** Intent/slot/promise/missing-info/
  handoff accuracy on the scripted set is currently 100% by construction (rule-based
  extractor authored against the fixtures). Stage 1 numbers become meaningful accuracy
  metrics only once the fixture set is expanded beyond the authored 12 (see §5) and the LLM
  extractor (backlog VS4) replaces the rules.
- What Stage 1 cannot measure: any latency, ASR quality, TTS quality, barge-in stop timing,
  VAD/turn-taking. Those columns stay `None` until Stage 2+.

### Stage 2 — Synthetic-audio (TTS-generated speech fed to real ASR)

Render each fixture utterance to audio with a TTS engine (a *different* engine than the one
under test, to avoid self-agreement bias), feed it through the **real ASR router** with real
engines, and run the identical Stage-1 assertions on the result. Additions:

- Audio fixture generation: per language (PL/DE/ES/EN), per voice (≥2 voices/language),
  stored with the source transcript as reference for WER.
- Degradation matrix applied to the same audio: SNR sweep, telephone-band filtering, codec
  artifacts (§6).
- First real measurements unlocked: ASR WER/latency, end-to-end extraction accuracy under
  ASR noise, `uncertain_terms` calibration (does low ASR confidence actually correlate with
  wrong values — the S11 "uncertain brand" contract must survive real ASR).
- Entry criteria: VS1 (real-time loop) + VS2 (ASR lane) from `implementation-backlog.md`.

### Stage 3 — Recorded real calls (consented)

Replay recorded human calls (recording consent captured per `enterprise-controls.md` §1;
`VoiceSession.recording_allowed` gate already implemented) through the full pipeline offline.

- Sources: pilot-tenant calls with explicit consent; hired-speaker recordings for accent and
  emotion cohorts (synthetic voices cannot faithfully produce accents/anger — doc 28 Stage B).
- Human reference transcripts produced for the WER denominator; human gold labels for
  intent/slots/promises/handoff.
- This is the first stage where accuracy numbers generalize beyond scripted inputs.
- Entry criteria: Stage 2 green; consent + retention controls live (VS6).

### Stage 4 — Live A/B

Shadow/canary evaluation on production traffic: new model or pipeline version handles a
capped fraction of live calls (or runs in shadow, transcribing without speaking), with
handoff-to-human always available, per-tenant opt-in, and the kill switch from
`enterprise-controls.md` §6 armed. Compares completion rate, handoff rate, latency
percentiles, and post-call correction rate (human edits to extracted fields as implicit
labels). Entry criteria: Stage 3 green, enterprise controls (consent, redaction, quotas,
observability) live, rollback rehearsed.

---

## 2. Metrics table

Measurement stage tells you when a number first becomes real. **Today only Stage-1 rows have
any standing, and those are behavioral pass/fail, not statistics.**

| Metric | Measurement method | Pass/fail threshold | First measurable at |
|---|---|---|---|
| P50 first-response latency | `end_of_utterance → first TTS frame` per turn, percentile over turns | **≤ 800 ms** (doc 06 §3) — **NOT MEASURED yet; transcript-only** | Stage 2 (real loop, VS1) |
| P95 first-response latency | same distribution, P95 | **≤ 1500 ms** (doc 06 §3); repeated breach → shorten/scripted turns | Stage 2 |
| ASR latency | audio-chunk-in → final transcript, per utterance; P50/P95; slot on `VoiceMetric.asr_latency_ms` | streaming partials ≤ 300 ms behind audio; final ≤ 500 ms after end-of-utterance (engineering budget within the 800 ms turn) | Stage 2 |
| LLM latency | prompt-dispatch → first token / full response; `VoiceMetric.llm_latency_ms` | first token ≤ 350 ms P50 (budget); tool-augmented turn ≤ 1200 ms P50 (doc 06 §3) | Stage 2 (VS4 for real LLM) |
| TTS latency | text-in → first audio frame; `VoiceMetric.tts_latency_ms` | ≤ 200 ms P50 first frame (budget) | Stage 2 (VS3) |
| Barge-in success | scripted interruptions (§7): fraction where TTS actually stops; stop latency = speech onset → TTS silent | success **≥ 95%**, stop **≤ 200 ms** (doc 06 §3). Stage 1 verifies the *logic* only (stop + flush + audit, `TestS2Interruption`, `test_tts_interruption_stop`) — zero timing measured | Stage 2 |
| Interruption recovery | after barge-in/correction: dialogue resumes coherently, no re-utterance of flushed content; scripted assertions + calibrated LLM judge | ≥ 0.9 coherent recoveries | Stage 1 (logic: S2/S3 pass) / Stage 2 (real) |
| Intent accuracy | confusion matrix vs gold labels over the fixture set + Stage-3 sample | **≥ 0.9** | Stage 1 (trivial on authored set) → honest at Stage 3 |
| Slot extraction F1 | per-slot normalized match vs gold (name, address, date, brand); critical slots reported separately | **F1 ≥ 0.85**; zero critical slots committed as `confirmed` from ASR-uncertain input (hard gate — the S11 invariant) | Stage 1 → honest at Stage 3 |
| Promise extraction F1 | extracted `Promise` rows vs gold (who/what/due) | **F1 ≥ 0.85** | Stage 1 → honest at Stage 3 |
| Missing-info recall | `MissingItem` rows vs gold; recall prioritized (a missed gap silently blocks the quote) | **recall ≥ 0.9**, precision ≥ 0.85 | Stage 1 → honest at Stage 3 |
| Human handoff correctness | per trigger class (§8): precision (no spurious handoffs) / recall (no missed ones) | **precision ≥ 0.9, recall ≥ 0.95**; explicit-request recall = 100% hard gate (S6 behavior) | Stage 1 (4 classes) → all 7 at Stage 3 |
| Hallucination rate | evidence-required outputs (field values, summary claims, prior-conversation references) lacking a `source_utterance_id` / asserting above evidence | **~0** — hard gate. Stage 1 enforces the structural version: unknown stays `None` (`TestNoHallucination`), uncertain never `confirmed` (S11), no price without data (S12) | Stage 1 (structural) → Stage 3 (statistical) |
| Task creation accuracy | proposed tasks/next-actions vs gold; autonomy-gate compliance on every proposal | F1 ≥ 0.85; 100% of client-facing actions gated (hard, doc 13) | Stage 1 → Stage 3 |
| Summary quality | rubric: covers intent, decisions, promises, missing items, emotion/handoff; **zero invented content**; LLM judge calibrated weekly vs human labels | judge ≥ calibrated threshold; any invented claim = fail | Stage 1 (template summary asserted) → Stage 3 (LLM summary) |

---

## 3. Model comparison plan

### 3.1 ASR bake-off protocol

Candidates: **NVIDIA Parakeet-v3** (primary candidate, self-hosted via NeMo) vs
**faster-whisper large-v3** (fallback candidate) vs **Voxtral-Realtime** (streaming
candidate). Per language:

1. **Public benchmark leg**: run all candidates on **BIGOS** (multi-domain Polish + European
   ASR corpus) plus per-language standard sets; for Polish specifically, cross-check against
   the **amu-cai/pl-asr-leaderboard** results rather than re-deriving baselines.
2. **Own-fixture leg**: the Stage-2 synthetic-audio renderings of the 12 scenarios plus the
   Stage-3 recorded set — domain vocabulary (brand names like "Viessmann", street addresses,
   dates) is where generic WER rankings mislead. Report WER overall **and** entity-level
   error rate on critical slots.
3. **Streaming leg**: partial-transcript latency and stability (how often partials are
   revised) — matters for barge-in and the 800 ms budget; batch-mode WER alone does not decide.
4. Decision rule: primary = best critical-slot entity accuracy on PL within latency budget;
   fallback = best robustness under the §6 degradation matrix. The `ASRRouter`
   (`finalis/voice/routers.py` — confidence-based failover, already tested) makes the pair
   swappable without pipeline changes.

### 3.2 TTS bake-off

- **Polish**: **ZONOS2 vs Piper** — MOS study (≥15 raters, ≥30 utterances incl. addresses,
  numbers, dates), intelligibility on digit/street-name readback, first-frame latency, and
  license confirmation for commercial self-hosting (VS3 gate). Piper is the designated
  fallback in the `TTSRouter` regardless of the primary outcome.
- **DE/ES/EN**: **Qwen3-TTS** as the candidate primary; same MOS + latency protocol, Piper
  fallback. Language-aware routing is already implemented and tested
  (`test_tts_language_aware_selection_and_fallback`).

---

## 4. Language testing plan (PL / DE / ES / EN)

`SUPPORTED_LANGUAGES = {"pl", "de", "es", "en"}` is already enforced in the router. Plan:

- Full fixture set authored in PL and EN (today's fixtures mix both); DE and ES translations
  of all 12 scenarios for Stage 2.
- Mixed-language calls: S8 (PL/DE switch) is the template — every language pair gets one
  switch scenario; assert per-utterance language detection and that slot values survive the
  switch.
- Per-language reporting: every §2 accuracy metric reported per language cohort; Polish is
  the gating cohort (primary market), others must be within 10% relative of PL.
- Polish-specific hazards to fixture: declension of names/streets ("na Kwiatowej" →
  canonical "Kwiatowa"), voiced/devoiced brand confusions ("Vissmann"/"Viessmann" — the S11
  case), number-heavy addresses.

## 5. Fixture growth

Stage 1's 12 authored scenarios are a smoke set, not a statistic. Before quoting any
accuracy percentage: grow to ≥100 transcripts per language via paraphrase generation +
human review, with held-out authorship (people who did not write the extractor rules), and
freeze as a versioned golden set with regression gating (doc 15 §3).

## 6. Accent & noise plan

Applied to Stage-2 audio (synthetic degradation) and Stage-3 recordings (natural):

- **SNR sweep**: clean / 20 dB / 10 dB / 5 dB with babble and appliance noise; plot WER and
  slot-F1 vs SNR; define the SNR floor below which the pipeline must switch to targeted
  repair + confirmation rather than proceeding.
- **Telephone band**: 8 kHz downsampling + band-pass 300–3400 Hz + AMR/Opus-narrowband codec
  pass — mandatory cohort, since SIP/PSTN (VS5) is a launch channel.
- **Street noise**: outdoor recordings/impulse mixes (traffic, wind on mic) for the
  tradesperson-calls-from-site persona.
- **Accents**: recorded human cohorts — non-native Polish, regional Polish, non-native
  English (Polish-accented), Ukrainian-accented Polish. Target: WER ≤ 20% accented (doc 28),
  and the hard gate that low-confidence critical slots are confirmed, never guessed.

## 7. Barge-in test protocol

Scripted interruptions at controlled offsets — a caller bot plays fixture audio and
interrupts on cue:

- Offsets: 100 ms / 500 ms / 1500 ms after TTS onset, and mid-final-word; 20 repetitions per
  offset per configuration.
- Measure per event: detection (did the pipeline register speech during TTS), stop latency
  (speech onset → TTS output silent; target ≤ 200 ms), flush correctness (queued content
  never spoken later), recovery (interrupting utterance fully processed — Stage-1 S2 already
  asserts this at the logic level, including the `BARGE_IN` audit event).
- False-trigger control: the same protocol with non-speech noise bursts and backchannels
  ("mhm") — these must **not** stop TTS; feeds barge-in precision.
- Counters already exist in the scaffold: `TTSRouter.interrupted_count`,
  `Utterance.is_interruption`, `BARGE_IN` audit events.

## 8. Human handoff test protocol — the 7 trigger classes

Per doc 06 §4 + doc 13. Each class gets dedicated scripted scenarios (positive + hard
negative) and is scored precision/recall separately:

| # | Trigger class | Scaffold status |
|---|---|---|
| 1 | Explicit request for a human | implemented + tested (S6; first-request, no deflection loop) |
| 2 | Anger / distress | implemented + tested (S7; keyword-level — sentiment model later) |
| 3 | Legal-advice request | implemented (`HANDOFF_PATTERNS.legal_advice`) |
| 4 | Medical-advice request | implemented (`HANDOFF_PATTERNS.medical_advice`) |
| 5 | `EscalationScore ≥ θ_escalate` | designed (doc 05/06) — not in scaffold |
| 6 | Safety emergency (e.g. gas leak — safety script first) | designed — not in scaffold |
| 7 | Low ASR confidence on critical data after repair attempts | partial — uncertain-status handling exists (S11 keeps the field missing); the *handoff* on persistent low confidence is designed |
| — | Negatives | mentions of "my lawyer said…", quoted anger, jokes — must NOT trigger (precision leg) |

Hard gates: class 1 recall = 100%; every handoff passes a live summary (Stage-1 asserts
`HANDOFF_LINE` + `HUMAN_HANDOFF` audit + `human_callback` next action with
`requires_human_approval: true`).

## 9. External benchmark reference

**Full-Duplex-Bench-v3 (arXiv 2604.04847)** is the external reference for interruption
handling, disfluency robustness, and tool-use-during-speech behaviors. Use it to (a) sanity-
check our barge-in/turn-taking protocol against a community-standard task taxonomy, (b)
position the cascaded pipeline against published full-duplex baselines, and (c) import its
disfluency categories (restarts, fillers, self-corrections) into fixture generation — our S3
"correction" scenario covers only one of them today. It does not replace the domain harness:
none of its tasks score promise/missing-info extraction or case-graph effects, which are the
metrics Finalis actually sells.

# Finalis Voice Engine — Architecture

Status labels follow the [acceptance rule](README.md#acceptance-rule):
**Implemented** = executable in `finalis/voice/` and covered by
`tests/test_voice_engine.py` (26 passing tests). **Designed** = specified here,
with the plug-in point already present in code.

## Pipeline diagram

```
                    PSTN caller                      Browser / mobile client
                        │                                      │
                   SIP trunk (carrier)                    WebRTC (DTLS-SRTP)
                        │                                      │
                 ┌──────▼──────┐                               │
                 │ livekit/sip │  Apache-2.0 SIP↔room bridge   │
                 └──────┬──────┘                               │
                        │                                      │
                 ┌──────▼──────────────────────────────────────▼──────┐
                 │        LiveKit server (Apache-2.0, self-hosted)    │
                 │        SFU · rooms · tracks · TURN/coturn          │
                 └──────────────────────────┬────────────────────────┘
                                            │  audio frames
                 ┌──────────────────────────▼────────────────────────┐
                 │        Pipecat v1.5.0 pipeline (BSD-2)             │
                 │                                                    │
                 │  VAD (Silero) ─► Smart Turn v3 (BSD-2, ~8M params, │
                 │                  12–60ms CPU, 23 langs incl. PL)   │
                 │        │  end-of-turn / barge-in events            │
                 │        ▼                                           │
                 │  ╔══════════════ finalis/voice ═════════════════╗  │
   test          │  ║  ASR Router (routers.ASRRouter)              ║  │
   transcripts ══╪══╣► primary Parakeet ─ fallback faster-whisper  ║  │
   (fixture      │  ║        │ TranscriptChunk                     ║  │
   audio-chunk   │  ║        ▼                                     ║  │
   dicts enter   │  ║  Dialogue Manager (engine.VoiceEngine)       ║  │
   HERE — the    │  ║  + Understanding Extractor (extractor.py)    ║  │
   only part the │  ║        │ reply text                          ║  │
   audio path    │  ║        ▼                                     ║  │
   replaces)     │  ║  TTS Router (routers.TTSRouter)              ║  │
                 │  ║  primary ZONOS2 ─ fallback Piper/Qwen3-TTS   ║  │
                 │  ╚═══════╤══════════════════════╤═══════════════╝  │
                 └──────────┼──────────────────────┼──────────────────┘
                            │ synthesized audio    │ structured output
                            ▼                      ▼
                     back to LiveKit room   Case Graph (finalis.models.Case)
                                            + AuditLog (hash-chained)
                                            + ActionGate (finalis.autonomy)
                                            + Certainty seam (certainty_core)
```

The double-lined box is what exists and is tested today. The transcript
simulation entry point (`channel="test_transcript"`) feeds ASR-annotated chunk
dicts directly into `ASRRouter.transcribe()`; the production audio path replaces
**only the input iterator** — everything downstream is identical
(`finalis/voice/engine.py`, module docstring).

## The 10 components

### 1. Voice Gateway
- **Purpose.** Session lifecycle, tenant binding, channel identity, consent.
- **Design.** One `VoiceSession` per call carrying `tenant_id`,
  `channel` (`webrtc | sip | test_transcript`), `language`, `consent_asked`,
  `recording_allowed`, status transitions `created → active → ended | handed_off`.
- **Implemented.** `VoiceEngine.start_session()` (`finalis/voice/engine.py`)
  creates the session, emits `CALL_STARTED` to the audit chain with the consent
  flag, and speaks the greeting. Consent honesty is tested: without consent,
  `recording_allowed` stays `False` and `audio_uri` stays `None`
  (`TestSessionAndConsent`).
- **Production plug-in.** LiveKit room join events (WebRTC) and `livekit/sip`
  inbound-call events construct the same `VoiceSession`; caller phone number
  arrives as channel metadata (the output schema already reserves
  `client.phone`).

### 2. Audio Preprocessor
- **Purpose.** Resampling, denoising, echo handling, voice activity detection.
- **Design.** Pipecat frame processors: Silero VAD `[U]` for speech/silence
  segmentation, 16 kHz mono resample for ASR, browser-side echo cancellation via
  WebRTC.
- **Implemented.** Nothing — the transcript scaffold has no audio. This is the
  one component that is Designed-only by construction.
- **Production plug-in.** Standard Pipecat pipeline stages ahead of the ASR
  router; no Finalis code changes needed.

### 3. ASR Router
- **Purpose.** Speech→text with confidence, language ID, and uncertain-term
  flags; never a single point of failure.
- **Design.** Primary + fallback engines behind an `ASRService` protocol;
  failover on exception **or** confidence below 0.4, keeping whichever result is
  more confident ("never silently drop signal"); language normalization to the
  supported set `{pl, de, es, en}`.
- **Implemented.** `ASRRouter` (`finalis/voice/routers.py`) — the routing logic
  is real and tested (`TestRouters`: failover on low confidence, failover on
  engine crash). Engines are deterministic mocks (`MockASR`) whose fixture chunks
  carry the annotations a real ASR would emit (text, confidence, language,
  `uncertain_terms`).
- **Production plug-in.** Implement `ASRService.transcribe()` for Parakeet TDT
  0.6B v3 (primary) and faster-whisper large-v3 (fallback); see
  [open-source-stack.md](open-source-stack.md).

### 4. Dialogue Manager
- **Purpose.** Drive the call: one question at a time, in priority order, with
  hard stops.
- **Design.** Policy data, not code: `QUESTION_ORDER = [address,
  installation_photo, preferred_date, device_brand]` with Polish question
  templates; hard stops for handoff triggers and out-of-scope; a price guard
  (`NO_PRICE_LINE`) that refuses to quote a price while required data is missing.
- **Implemented.** The `run_call()` loop in `engine.py`: barge-in check → ASR →
  extraction → hard stops → price guard → next still-missing, not-yet-asked
  question. Tested invariants include "no AI turn contains two questions"
  (`TestS1NormalQuote.test_one_question_at_a_time`), immediate handoff (S6, S7),
  out-of-scope decline with no case invented (S9), and no numeric price ever in
  AI speech (S12).
- **Production plug-in.** The rule policy is the Phase-1 baseline; an LLM
  dialogue policy (Qwen3-30B-A3B via vLLM) slots in at the same decision point,
  constrained by the same hard stops, which remain rule-enforced.

### 5. Understanding Extractor
- **Purpose.** Turn utterances into structured facts without inventing anything.
- **Design.** Incremental per-utterance processing; four enforced rules
  (docstring of `finalis/voice/extractor.py`): unknown stays
  `{value: None, status: "unknown"}`; an ASR-uncertain term can **never** become
  a certain fact (confidence capped at 0.5 → status `uncertain`); a later
  correction overwrites an earlier value (last confirmed wins); promises,
  objections, and handoff triggers are detected with confidence scores. Pattern
  tables cover English + Polish and are playbook data in production, not code.
- **Implemented.** `UnderstandingExtractor` — intent, service type, urgency,
  name/address/date/brand fields, address refusal, price-ask flag, corrections,
  promises with due dates, objections, handoff triggers, out-of-scope, returning
  -client references, and `missing_items()` derivation against
  `REQUIRED_FIELDS_HVAC`. Tested by S1, S3 (correction wins), S5 (refusal →
  risk flag), S8 (uncertain city never confirmed), S11 (uncertain brand stays
  `uncertain` and remains a missing item), and the cross-scenario
  `TestNoHallucination` invariant.
- **Production plug-in.** A local-LLM extractor behind the same interface;
  the rule extractor stays as a deterministic cross-check.

### 6. TTS Router
- **Purpose.** Text→speech with language-aware engine choice, fallback, and
  instant stop on barge-in.
- **Design.** `TTSService` protocol with a declared language set; `pick()`
  selects primary if it supports the language, else fallback; `speak()` falls
  back on synthesis exceptions; `stop()` flushes on interruption and counts it.
- **Implemented.** `TTSRouter` (`routers.py`), tested for language-aware
  selection (`de` → piper when primary lacks German), crash fallback, and
  interruption stop (`TestRouters`).
- **Production plug-in.** ZONOS2 streaming client (primary), Piper subprocess
  and Qwen3-TTS (fallbacks); see the language routing matrix in
  [open-source-stack.md](open-source-stack.md).

### 7. Case Graph Connector
- **Purpose.** A call must end as case state, never as a dangling transcript.
- **Design.** Create a `Case` only when there is an in-scope intent; link to an
  existing case for returning clients instead of duplicating; write
  `MissingItem`s (weighted, quote-blocking), `Promise`s (with due dates derived
  from `DUE_TO_HOURS`), follow-up tasks, and `next_best_action` +
  `next_action_due_at` for the completion loop.
- **Implemented.** `VoiceEngine._end_session()` and `_next_action()` — reuses
  `finalis.models.Case/MissingItem/Promise` and `finalis.state_machine`, runs
  the photo-request action through the rule-based ActionGate
  (`finalis.autonomy.gate`), and stamps facts through the certainty seam
  (`finalis.certainty_core.NullAdapter`). Tested: case created in
  `NEW_CONTACT` and wired to the completion loop (S1), photo promise →
  `Promise` + `followup_if_no_photos` task (S4), returning client linked not
  duplicated (S10), no case for out-of-scope (S9).
- **Production plug-in.** Same objects persisted through the core API instead of
  in-memory.

### 8. Human Handoff
- **Purpose.** The AI must know when to stop being the AI.
- **Design.** Trigger classes: explicit human request, anger, legal-advice and
  medical-advice asks (EN + PL patterns). Handoff is a hard stop: speak the
  handoff line, mark the session `handed_off`, emit `HUMAN_HANDOFF`, and produce
  a `human_callback` next action with `requires_human_approval: True`.
- **Implemented.** `HANDOFF_PATTERNS` + `VoiceEngine._handoff()`. Tested by S6
  (explicit request honored immediately) and S7 (anger detection).
- **Production plug-in.** Warm transfer via LiveKit room forwarding / SIP
  REFER; the structured session output becomes the human agent's briefing.

### 9. Evaluation Harness
- **Purpose.** Prove behavior scenario-by-scenario, not vibes.
- **Design.** Transcript fixtures that encode what a real ASR would emit —
  including confidence dips, `uncertain_terms`, mixed languages, and `barge_in`
  flags — replayed through the full engine with the audit chain verified after
  every run.
- **Implemented.** The 12 mandated scenarios in `tests/voice_fixtures.py` +
  `tests/test_voice_engine.py` (26 tests): S1 normal quote, S2 interruption,
  S3 correction, S4 promise, S5 address refusal, S6 human request, S7 anger,
  S8 mixed languages, S9 out-of-scope, S10 returning client, S11 uncertain
  brand, S12 price-without-data — plus router failover and session/consent
  tests.
- **Production plug-in.** The same scenarios re-recorded as audio for
  end-to-end runs; Full-Duplex-Bench-v3 (arXiv 2604.04847) as the duplex
  -behavior evaluation reference.

### 10. Enterprise Controls
- **Purpose.** Multi-tenancy, consent, auditability, bounded autonomy.
- **Design.** Every session tenant-scoped; consent asked and recorded before
  anything else; every significant event (`CALL_STARTED`, `BARGE_IN`,
  `INTENT_DETECTED`, `MISSING_INFO_DETECTED`, `PROMISE_DETECTED`,
  `HUMAN_HANDOFF`, `NEXT_ACTION_CREATED`, `CALL_ENDED`) appended to the
  hash-chained audit log; autonomous actions pass the ActionGate; metrics are
  honest (`measured: False` until an audio path exists).
- **Implemented.** All of the above at transcript level — `audit.verify_chain()`
  is asserted in every test run; consent behavior and unmeasured-metrics honesty
  are explicitly tested.
- **Production plug-in.** Recording storage + retention policy keyed on
  `recording_allowed`, RBAC on session/transcript access, per-tenant model
  routing. Designed, not yet implemented.

## Voice session flow — 16 steps, mapped to the scaffold

| # | Step | Scaffold mapping (Implemented unless noted) |
|---|---|---|
| 1 | Call arrives (WebRTC join or SIP invite) | Designed — LiveKit / livekit/sip; simulated by test invocation |
| 2 | Session created, tenant + channel bound | `start_session(channel=…)` → `VoiceSession` |
| 3 | Consent asked and recorded | `consent_asked=True`, `recording_allowed` flag; `CALL_STARTED` audit payload |
| 4 | Greeting spoken | `_say()` → `TTSRouter.speak()` |
| 5 | Client speech segmented | Designed — VAD (Silero) in Pipecat |
| 6 | End-of-turn / barge-in decided | Designed — Smart Turn v3; simulated by `barge_in` fixture flag |
| 7 | Barge-in stops TTS instantly | `TTSRouter.stop()` + `BARGE_IN` audit event (tested, S2) |
| 8 | Speech transcribed with confidence + language + uncertain terms | `ASRRouter.transcribe()` with primary→fallback failover |
| 9 | Utterance recorded on the session | `Utterance` appended with all ASR annotations |
| 10 | Understanding updated incrementally | `UnderstandingExtractor.process()` |
| 11 | Hard stops checked (handoff, out-of-scope) | `run_call()` — `_handoff()` / `OUT_OF_SCOPE_LINE`, break |
| 12 | Price guard applied | `NO_PRICE_LINE` when price asked with missing data |
| 13 | Next single question chosen and spoken | `QUESTION_ORDER` filtered by `missing_items()` and `asked` |
| 14 | Loop until turns end or hard stop | `run_call()` chunk loop |
| 15 | Session end: case create/update, missing items, promises→tasks, next action via ActionGate, certainty stamp | `_end_session()` + `_next_action()` |
| 16 | Structured JSON output + summary + `CALL_ENDED` + honest metrics | `_build_output()`, `_summary()`, `VoiceMetric(measured=False)` |

## Barge-in and turn handling

Turn handling is split between a **turn decision** (audio-level, Designed) and a
**turn reaction** (logic-level, Implemented):

- **Decision — Smart Turn v3** (Pipecat, BSD-2 open weights + data + training
  code): a ~8M-parameter model deciding end-of-turn semantically rather than by
  silence timeout, at **12–60 ms inference on CPU**, covering **23 languages
  including Polish** `[S]`. This is the decisive reason Pipecat won over LiveKit
  Agents, whose turn detector has proprietary weights (usable only inside
  LiveKit Agents sessions, GitHub issue #3262) and no Polish support (issue
  #3795) `[VP]`. CPU inference means turn detection adds no GPU load next to
  ASR/TTS/LLM.
- **Reaction — the scaffold**: when the client speaks while TTS is active,
  `TTSRouter.stop()` fires immediately (flush queued audio, count the
  interruption), a `BARGE_IN` audit event is appended, the utterance is marked
  `is_interruption=True`, and the dialogue recovers rather than restarting —
  all asserted in `TestS2Interruption` and `TestRouters.test_tts_interruption_stop`.

In the transcript scaffold the decision is simulated by the fixture-level
`barge_in` flag; wiring Smart Turn v3's event to that flag is the entire
integration surface. Latency figures for the full loop (`VoiceMetric`
p50/p95 first-response, per-stage ASR/LLM/TTS latency, `barge_in_success`)
are deliberately `None`/unmeasured until the audio path exists.

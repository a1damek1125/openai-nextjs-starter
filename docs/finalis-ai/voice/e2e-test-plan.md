# Finalis Voice Engine — E2E Test Plan

> Ground truth: `tests/test_voice_engine.py` + `tests/voice_fixtures.py` on
> branch `claude/finalis-voice-engine-open-core`. Every scenario below marked
> **PASSING** is executable right now:
>
> ```
> python3 -m pytest tests/test_voice_engine.py -q   # 26 passed
> python3 -m pytest tests/ -q                       # 128 passed (repo-wide)
> ```
>
> Fixtures are ASR-annotated audio-chunk dicts — what a real ASR would emit
> (text, confidence, language, `uncertain_terms`, `barge_in` flags) — replayed
> through the **full engine** (session lifecycle → ASR router → dialogue loop →
> extractor → case-graph write → audit). The shared `run()` helper additionally
> asserts `audit.verify_chain()` after **every single call**, so the
> hash-chained audit integrity is an implicit invariant of all 26 tests.

---

## 1. The 12 mandated scenarios — all PASSING

### S1 — Normal HVAC quote call
- **Fixture**: `S1_NORMAL_HVAC_QUOTE` — "Hi, I'd like a quote for a heat pump
  installation." / "My name is Jan Kowalski, the house is at ul. Kwiatowa 12 in
  Poznań." / "Thursday would work best for me." (confidences 0.93–0.95, en).
- **Expected behavior**: full happy-path intake — intent, name, address, date
  extracted; photo + brand remain missing; photo-request next action; case
  created and wired to the completion loop.
- **Exact assertions** (`TestS1NormalQuote.test_full_happy_intake`):
  `intent == "request_quote"`; `case_type == "hvac_installation"`;
  `service.type == "heat_pump_quote"`; `client.name == "Jan Kowalski"`;
  `service.address == "Kwiatowa 12"`; `service.preferred_date == "thursday"`;
  missing set == `{installation_photo, device_brand}` (photos can never arrive
  mid-call); `next_action.type == "send_photo_request"`;
  `human_review_required is False`; audit events include `CALL_STARTED`,
  `INTENT_DETECTED`, `MISSING_INFO_DETECTED`, `NEXT_ACTION_CREATED`,
  `CALL_ENDED`; `r.case is not None` and in `CaseState.NEW_CONTACT`;
  `case.next_best_action == output.next_action`;
  `case.next_action_due_at is not None`.
- **Status**: PASSING (`TestS1NormalQuote`, 2 tests — see also §2
  one-question invariant).

### S2 — Client interrupts the AI (barge-in)
- **Fixture**: `S2_CLIENT_INTERRUPTS` — AC quote request, then "Sorry, before
  you continue - it's actually for two rooms." with `barge_in: True`.
- **Expected behavior**: TTS stops immediately, the interruption is recorded
  and audited, and the dialogue recovers instead of restarting.
- **Exact assertions** (`TestS2Interruption.test_barge_in_stops_tts_and_is_audited`):
  exactly one `BARGE_IN` audit event; exactly one utterance with
  `is_interruption == True`; `intent == "request_quote"` (flow recovered).
- **Status**: PASSING (`TestS2Interruption`).

### S3 — Wrong data corrected mid-call
- **Fixture**: `S3_WRONG_DATA_CORRECTED` — name Adam Nowak; address "ul. Polna
  5"; then "No, wait, sorry - the address is ul. Lipowa 8, the other one is my
  office."
- **Expected behavior**: last confirmed value wins; the correction overwrites
  the earlier confirmed address; no stale value survives.
- **Exact assertions** (`TestS3Correction.test_later_correction_wins`):
  `service.address == "Lipowa 8"`; `client.name == "Adam Nowak"`.
- **Status**: PASSING (`TestS3Correction`).

### S4 — Client promises to send photos
- **Fixture**: `S4_PROMISES_PHOTOS` — boiler replacement quote; "I'll send you
  the photos tomorrow, of the boiler and the nameplate."
- **Expected behavior**: promise extracted with due date, written as a
  `Promise` row on the case, audited, and a follow-up task proposed; the
  summary asserts the promise.
- **Exact assertions** (`TestS4Promise.test_photo_promise_creates_promise_and_task`):
  `promises == [{who: "client", what: "send photos", due: "tomorrow",
  confidence ≈ 0.87 (±0.05)}]`; `PROMISE_DETECTED` in audit events;
  `r.tasks == [{type: "followup_if_no_photos", due: "tomorrow",
  channel: "sms_or_whatsapp"}]`; `len(case.promises) == 1` with
  `what == "send photos"`; `"promised to send photos"` in the summary.
- **Status**: PASSING (`TestS4Promise`).

### S5 — Client refuses to give the address
- **Fixture**: `S5_REFUSES_ADDRESS` — "How much would a heat pump cost? I need
  a quote." / "I don't want to give my address yet, just a rough price please."
- **Expected behavior**: refusal never becomes a value; address stays missing;
  refusal is surfaced as a risk; and the AI must not quote a price without data.
- **Exact assertions** (`TestS5RefusesAddress.test_refusal_keeps_missing_and_flags_risk`):
  `"address"` in missing types; `service.address is None`;
  `risks == ["client_refused_address"]`; the AI speech contains the price-guard
  line `"Nie chcę podawać ceny"`.
- **Status**: PASSING (`TestS5RefusesAddress`).

### S6 — Client asks for a human
- **Fixture**: `S6_ASKS_FOR_HUMAN` — AC quote, then "Actually, I'd prefer to
  talk to a human about this."
- **Expected behavior**: unconditional, immediate handoff — no deflection loop;
  session ends `handed_off`; next action is a human callback requiring
  approval.
- **Exact assertions** (`TestS6HumanRequest.test_handoff_honored_immediately`):
  `human_review_required is True`; `handoff_reason == "human_requested"`;
  `session.status == "handed_off"`; `next_action == {type: "human_callback",
  channel: "phone", requires_human_approval: True}`; exactly one
  `HUMAN_HANDOFF` audit event.
- **Status**: PASSING (`TestS6HumanRequest`).

### S7 — Angry client
- **Fixture**: `S7_ANGRY_CLIENT` — "Your technician was supposed to come
  yesterday and nobody showed up. This is outrageous!"
- **Expected behavior**: anger trigger → handoff, same hard-stop path as S6.
- **Exact assertions** (`TestS7AngryClient.test_anger_triggers_handoff`):
  `human_review_required is True`; `handoff_reason == "anger"`.
- **Status**: PASSING (`TestS7AngryClient`).

### S8 — Mixed languages mid-call
- **Fixture**: `S8_MIXED_LANGUAGES` — Polish heat-pump request, then a mixed
  German/Polish turn ("Das Haus ist, przepraszam, dom jest w Słubicach…") at
  confidence 0.75 with `uncertain_terms: ["Słubicach"]`.
- **Expected behavior**: both languages recorded; intent survives the switch;
  the ASR-uncertain city fragment must never surface as a confirmed address.
- **Exact assertions** (`TestS8MixedLanguages.test_language_detection_and_uncertain_place_name`):
  `set(languages_detected) == {"pl", "de"}`; `intent == "request_quote"`;
  `service.type == "heat_pump_quote"`; `service.address is None`.
- **Status**: PASSING (`TestS8MixedLanguages`).

### S9 — Out-of-scope request
- **Fixture**: `S9_OUT_OF_SCOPE` — "Hi, do you also do car repair? My engine is
  making noises."
- **Expected behavior**: polite decline, no case invented, close-out action.
- **Exact assertions** (`TestS9OutOfScope.test_out_of_scope_declined_no_case`):
  `next_action.type == "close_out_of_scope"`; `r.case is None`; AI speech
  contains the decline line `"nie zajmujemy się"`.
- **Status**: PASSING (`TestS9OutOfScope`).

### S10 — Returning client
- **Fixture**: `S10_RETURNING_CLIENT` — "you installed my AC last year - I'm
  calling about the previous order." / "I'd like a quote for a second unit,
  same address as last time." Run with an `existing_case` in
  `CaseState.COMPLETED`.
- **Expected behavior**: the previous-case reference is detected and the call
  links to the existing case instead of duplicating it.
- **Exact assertions** (`TestS10ReturningClient.test_previous_case_reference_detected`):
  `returning_client_reference is True`; `case_id == existing.id`;
  `intent == "request_quote"`.
- **Status**: PASSING (`TestS10ReturningClient`).

### S11 — Uncertain brand name from ASR
- **Fixture**: `S11_UNCERTAIN_BRAND` — boiler service quote; "I think it's a
  Vissmann or something like that, hard to read." at confidence 0.6 with
  `uncertain_terms: ["Vissmann"]`.
- **Expected behavior**: the uncertain value is kept **as uncertain** — visible
  but never a fact, and the field still counts as missing.
- **Exact assertions** (`TestS11UncertainBrand.test_uncertain_brand_never_saved_as_certain`):
  `device_brand.value == "Vissmann"`; `device_brand.status == "uncertain"`
  (NOT confirmed); `device_brand.confidence <= 0.5`; `"device_brand"` in
  missing types with `note == "value_present_but_uncertain"`.
- **Status**: PASSING (`TestS11UncertainBrand`).

### S12 — Price demanded without data
- **Fixture**: `S12_PRICE_WITHOUT_DATA` — "What's the price for a heat pump?
  Just tell me how much it will cost."
- **Expected behavior**: the AI never quotes a number while required data is
  missing; it explains what it still needs.
- **Exact assertions** (`TestS12PriceWithoutData.test_no_price_promised_without_data`):
  AI speech contains `"Nie chcę podawać ceny"`; regex assertion that **no
  numeric price** (`\d+\s*(zł|PLN|EUR|€)`) appears anywhere in AI speech;
  missing types ⊇ `{address, installation_photo}`.
- **Status**: PASSING (`TestS12PriceWithoutData`).

---

## 2. Cross-cutting invariant tests — all PASSING

| Invariant | Test | What it asserts |
|---|---|---|
| **No hallucination** | `TestNoHallucination.test_unknown_fields_stay_null` — parametrized over 6 fixtures (S1, S4, S5, S8, S11, S12) | Confirmed-only surfaces: a non-null `service.address` implies `address_status == "confirmed"`; a `device_brand` with `status == "unknown"` has `value is None`. Fields never invent values, across happy-path, refusal, mixed-language, uncertain-ASR, and no-data scenarios. |
| **One question at a time** | `TestS1NormalQuote.test_one_question_at_a_time` | No AI turn contains more than one `?` — the `QUESTION_ORDER` dialogue policy never stacks questions. |
| **Session lifecycle** | `TestSessionAndConsent.test_session_object_lifecycle` | `tenant_id` bound; final status in `{ended, handed_off}`; `started_at`/`ended_at`/`summary` set; `consent_asked` true. |
| **Consent honesty** | `TestSessionAndConsent.test_no_recording_without_consent` | With `consent=False`: `recording_allowed is False`, the `CALL_STARTED` audit payload records it, and `audio_uri is None` — nothing recorded. |
| **Metrics honesty** | `TestSessionAndConsent.test_metrics_marked_not_measured` | `metrics.measured is False` and `p50_first_response_latency_ms is None` — the transcript scaffold makes **no latency claims**; `intent_confidence > 0` (the confidences that ARE real are populated). |
| **ASR failover — low confidence** | `TestRouters.test_asr_failover_on_low_confidence` | Primary returning confidence 0.1 → fallback used (`last_engine == "fallback"`), fallback's text kept. |
| **ASR failover — crash** | `TestRouters.test_asr_failover_on_crash` | Primary raising → fallback result returned; no exception escapes the router. |
| **TTS language routing + fallback** | `TestRouters.test_tts_language_aware_selection_and_fallback` | `de` (unsupported by primary) → fallback engine; `en` → primary. |
| **TTS barge-in stop** | `TestRouters.test_tts_interruption_stop` | `stop()` clears `speaking` and increments `interrupted_count`. |
| **Audit chain integrity** | `run()` helper (every test) | `audit.verify_chain()` — the SHA-256 hash chain validates after every simulated call. |

Test count: 13 scenario tests (S1×2 + S2–S12) + 6 no-hallucination
parametrizations + 3 session/consent + 4 router = **26**.

---

## 3. Next test stages — NOT IMPLEMENTED

These are Stage-B items per `../28-voice-verification-and-test-plan.md`; none
are executable in this repository, and per the readiness rule
(`../41-voice-e2e-readiness-report.md`) every latency number remains a
**target, not a measurement**, until they exist.

### 3.1 Audio-based scenario runs — NOT IMPLEMENTED
The same 12 scenarios **spoken**, not typed: TTS-rendered caller audio plus
mandatory recorded human variants, in PL / DE / ES / EN including accented
speakers, replayed through the real pipeline. Needed: LiveKit + Pipecat staging
pipeline (real ASR/TTS engines behind the existing `ASRService`/`TTSService`
protocols — the scaffold's input iterator is the only part that changes), a
deterministic caller bot (plays fixture audio, interrupts on cue, goes silent
on cue), and audio fixture storage. Human recordings are mandatory for the
accent/anger scenarios — synthetic voices cannot represent them faithfully.

### 3.2 Noise / accent robustness — NOT IMPLEMENTED
Accented and noisy cohorts of the same audio fixtures; measures ASR WER per
cohort (targets: ≤ 12% overall, ≤ 20% accented/noisy — aspirational per doc 28
§3) and asserts the behavioral rule already proven at transcript level: low
ASR confidence must produce `uncertain` fields and repair/confirmation
behavior, never confirmed facts. Needed: recorded accent corpus (PL/DE/ES/EN),
noise-injection tooling, human reference transcripts for WER.

### 3.3 Real barge-in timing — NOT IMPLEMENTED
S2 as audio with measured `barge_in_onset → tts_stop` latency against the
**≤ 200 ms** target (doc 06 §3), plus barge-in precision/recall labeling
(false-trigger rate on thinking pauses). Needed: Silero VAD + Smart Turn v3
wired to the scaffold's `barge_in` flag, audio-frame timestamping, and the
`VoiceMetric.barge_in_success` field flipping from `None` to real values.

### 3.4 Latency regression gate — NOT IMPLEMENTED
TTFA P50 ≤ 800 ms / P95 ≤ 1500 ms and per-stage ASR/LLM/TTS latencies measured
per turn on staging (Pipecat's built-in TTFA metrics / LiveKit turn-timing
hooks), written into `VoiceMetric` with `measured: true`, and asserted in CI on
every release — a breach fails the build exactly like a logic test. Needed:
staging pipeline (3.1), metrics ingestion, CI gate definition. Until then,
`VoiceMetric.measured` stays `False` by design and the suite *asserts* that
honesty (§2, metrics-honesty test).

---

## 4. Test command and current result

```
$ python3 -m pytest tests/test_voice_engine.py -q
26 passed

$ python3 -m pytest tests/ -q
128 passed
```

All 12 mandated scenarios, all cross-cutting invariants, and all router
failover tests pass; the repo-wide suite (state machine, scoring, autonomy,
completion loop, OCR, WebScout, voice) passes at 128 with no skips or xfails.

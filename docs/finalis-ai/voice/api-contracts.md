# Finalis Voice Engine — API Contracts

> Two layers are specified here.
>
> **Part 1 — REST contracts** are **design artifacts: no HTTP server implements
> them yet** anywhere in this repository. They follow the conventions of
> `../22-api-and-event-model.md`: `/v1` base path, tenant derived from the auth
> principal (never the body), `Idempotency-Key` on all mutations, RFC 9457
> `application/problem+json` errors, cursor pagination, and an `AuditEvent` per
> mutation.
>
> **Part 2 — internal service interfaces** are **implemented in the scaffold**
> (`finalis/voice/`) and covered by the 26 passing tests in
> `tests/test_voice_engine.py`. Each is labeled
> **Implemented (scaffold)** or **Designed**.

Entities referenced (`VoiceSession`, `Utterance`, `VoiceExtraction`,
`VoiceMetric`, and the reused `Promise`/`MissingItem`/`AuditEvent`) are defined
in [data-model.md](data-model.md).

---

# PART 1 — REST contracts (Designed — no server yet)

Base URL: `https://api.finalis.ai/v1`. All routes tenant-scoped via auth;
cross-tenant ids return `404 not_found` (RLS convention, doc 22 §1.4).
Mutations accept `Idempotency-Key` and write hash-chained `AuditEvent`s.

## POST `/v1/voice/sessions/start` — Designed

Open a voice session. Backed by `VoiceEngine.start_session()` semantics:
session becomes `active`, `CALL_STARTED` is audited with the consent flag, and
the greeting is queued for TTS.

Request:

```json
{
  "channel": "webrtc",
  "language": "pl",
  "recording_consent": true,
  "case_id": null
}
```

- `channel`: `webrtc | sip | test_transcript` (400 `validation_error` otherwise).
- `recording_consent`: defaults `false` — recording stays off unless explicitly
  granted (`recording_allowed` is never inferred).
- `case_id` (optional): link a returning client's existing case instead of
  creating a new one at end (S10 semantics).
- `tenant_id` comes from the auth principal, never the body (doc 22 §1.1).

Response `201`:

```json
{
  "id": "b7f1c2ce-4b6c-4e1a-9a3d-5e1f0c9d2a11",
  "tenant_id": "hvac-1",
  "channel": "webrtc",
  "case_id": null,
  "language": "pl",
  "status": "active",
  "recording_allowed": true,
  "consent_asked": true,
  "started_at": "2026-07-07T10:02:11Z",
  "greeting": "Dzień dobry, tu asystent firmy. W czym mogę pomóc?"
}
```

## POST `/v1/voice/sessions/{id}/utterance` — Designed

Push one client turn: an **audio chunk** (production) or an **annotated
transcript chunk** (test/simulation lane — exactly the fixture dict shape the
scaffold consumes today). Runs one iteration of the dialogue loop:
barge-in check → ASR routing → extraction → hard stops → price guard → at most
one question back.

Request (either form):

```json
{ "audio": "<base64 or stream ref>", "barge_in": false }
```

```json
{
  "text": "My name is Jan Kowalski, the house is at ul. Kwiatowa 12 in Poznań.",
  "confidence": 0.93,
  "language": "en",
  "uncertain_terms": [],
  "barge_in": false
}
```

Response `200`:

```json
{
  "utterance": {
    "id": "3a9e7c10-88d2-4f0b-9c55-2d6e4f7a8b01",
    "speaker": "client",
    "text": "My name is Jan Kowalski, the house is at ul. Kwiatowa 12 in Poznań.",
    "confidence": 0.93,
    "language": "en",
    "is_interruption": false,
    "uncertain_terms": []
  },
  "ai_reply": {
    "text": "Najlepiej, jeśli po rozmowie wyśle Pan zdjęcie obecnej instalacji i tabliczki znamionowej.",
    "language": "pl"
  },
  "hard_stop": null,
  "session_status": "active"
}
```

- `hard_stop`: `null | "handoff" | "out_of_scope"` — when non-null the AI's
  script has ended and the caller should proceed to `/end`.
- `409 session_already_ended` if `status` is `ended | handed_off`.

## POST `/v1/voice/sessions/{id}/transcript` — Designed

Bulk variant: submit the whole call as an ordered chunk array (same shapes as
above) — the API equivalent of `VoiceEngine.run_call()`. Intended for the
`test_transcript` channel, replays, and batch import of externally recorded
calls.

Request: `{ "chunks": [ { "text": "...", "confidence": 0.95, "language": "en" }, ... ] }`

Response `200`: the full end-of-call output object (see `/end`), since
`run_call` ends the session.

## POST `/v1/voice/sessions/{id}/extract` — Designed

Force an extraction pass and return the current `Understanding` snapshot
without ending the session (mid-call state for a supervising human or the
warm-handoff briefing).

Response `200`:

```json
{
  "intent": "request_quote",
  "intent_confidence": 0.93,
  "case_type": "hvac_installation",
  "service_type": "heat_pump_quote",
  "fields": {
    "client_name": { "value": "Jan Kowalski", "confidence": 0.9, "status": "confirmed" },
    "address": { "value": "Kwiatowa 12", "confidence": 0.85, "status": "confirmed" },
    "preferred_date": { "value": null, "confidence": 0.0, "status": "unknown" },
    "device_brand": { "value": null, "confidence": 0.0, "status": "unknown" }
  },
  "missing_items": [
    { "type": "installation_photo", "severity": "high", "blocks": "quote_preparation" },
    { "type": "preferred_date", "severity": "medium", "blocks": null },
    { "type": "device_brand", "severity": "medium", "blocks": null }
  ],
  "promises": [],
  "objections": [],
  "handoff_triggers": []
}
```

## POST `/v1/voice/sessions/{id}/end` — Designed

End the session. Backed by `VoiceEngine._end_session()` semantics: case
create/update, `MissingItem`/`Promise` writes, next action via ActionGate,
certainty stamp, summary, `CALL_ENDED` audit event.

Response `200`: **the required JSON output** documented in
[data-model.md §6](data-model.md) (`voice_session_id`, `case_id`, `intent`,
`client`/`service` with `*_status` fields, `missing_items`, `promises`,
`objections`, `risks`, `next_action`, `human_review_required`,
`handoff_reason`, `summary`, `certainty_audit_id`, `audit_events`).

Idempotent: a second `end` returns the original output with
`Idempotent-Replay: true` (doc 22 §1.1).

## GET `/v1/voice/sessions/{id}` — Designed

Full session detail: the `VoiceSession` projection plus `utterances[]`
(diarized transcript — **PII; access audit-logged**, doc 22 calls convention)
and `extractions[]`. `?include=case` embeds the linked `Case` projection.

## GET `/v1/voice/sessions/{id}/summary` — Designed

```json
{
  "voice_session_id": "b7f1c2ce-...",
  "summary": "Client requested heat pump quote. Missing: installation_photo, device_brand.",
  "status": "ended",
  "human_handoff_requested": false,
  "handoff_reason": null
}
```

The summary is template-built from confirmed facts only (never asserts
unconfirmed values); `404 not_found` until the session has ended or handed off.

## GET `/v1/voice/sessions/{id}/metrics` — Designed

Returns the `VoiceMetric` object verbatim — including honest `null`s:

```json
{
  "voice_session_id": "b7f1c2ce-...",
  "p50_first_response_latency_ms": null,
  "p95_first_response_latency_ms": null,
  "asr_latency_ms": null,
  "llm_latency_ms": null,
  "tts_latency_ms": null,
  "barge_in_success": null,
  "intent_confidence": 0.9325,
  "extraction_confidence": 0.8,
  "measured": false
}
```

Non-PII; safe for dashboards. Clients MUST treat `measured: false` as "no
latency claims can be made about this call".

## Error model (all routes)

RFC 9457 problem+json per doc 22 §1.4. Voice-specific `type` slugs:

| Status | Slug | When |
|---|---|---|
| 400 | `validation_error` | Bad channel/language/chunk shape |
| 404 | `not_found` | Unknown or cross-tenant session id |
| 409 | `session_already_ended` | Utterance/extract/end on a closed session |
| 403 | `consent_required` | Requesting `audio_uri`/recording for a session with `recording_allowed: false` |
| 422 | `confidence_below_threshold` | Asking the engine to assert an uncertain fact as confirmed — it abstains |

---

# PART 2 — Internal service interfaces (as implemented)

These are the seams real engines plug into. Protocols and routing logic live in
`finalis/voice/routers.py`; orchestration in `finalis/voice/engine.py`;
extraction in `finalis/voice/extractor.py`.

## `ASRService.transcribe(audio_chunk) -> TranscriptChunk` — Implemented (scaffold: protocol + deterministic mocks)

```python
class ASRService(Protocol):
    name: str
    def transcribe(self, audio_chunk: dict) -> TranscriptChunk: ...
```

`TranscriptChunk` = `{text: str, confidence: float, language: str,
start_ms: int, end_ms: int, uncertain_terms: list[str]}`. The scaffold ships
`MockASR`, which reads fixture chunks already carrying the annotations a real
ASR would emit. Production implementations: Parakeet TDT (primary),
faster-whisper (fallback) — **Designed**.

## `TTSService.synthesize(text, language, voice_profile) -> audio stream` — Implemented (scaffold: protocol + mocks)

```python
class TTSService(Protocol):
    name: str
    languages: set[str]
    def synthesize(self, text: str, language: str, voice_profile: str) -> dict: ...
```

`MockTTS` records spoken text and returns
`{"engine", "language", "chars"}`; production engines (ZONOS2 primary,
Piper/Qwen3-TTS fallback) return real audio streams — **Designed**.

## `ASRRouter` — Implemented (scaffold), tested

`ASRRouter(primary, fallback, failover_confidence=0.4)`. Failover semantics
(`routers.py`, verified by `TestRouters`):

1. Try `primary.transcribe()`; an **exception** counts as no result.
2. If there is no result **or** `confidence < 0.4` → call the fallback.
3. **Keep whichever result is more confident** — the fallback's output only
   replaces a low-confidence primary result if it is actually better ("never
   silently drop signal").
4. Normalize unsupported languages to `"en"` (supported set: `{pl, de, es, en}`).
5. `last_engine` records which engine won (observability).

Tested: failover on low confidence (`test_asr_failover_on_low_confidence`),
failover on engine crash (`test_asr_failover_on_crash`).

## `TTSRouter` — Implemented (scaffold), tested

- `pick(language)`: language-aware selection — primary if it declares the
  language, else fallback (tested: `de` routes to piper when the primary lacks
  German).
- `speak(text, language, voice_profile="default")`: synthesize via the picked
  engine; **on exception, fall back**; sets `speaking = True`.
- `stop()`: **barge-in** — immediately stop speaking, flush queued audio,
  increment `interrupted_count` (tested: `test_tts_interruption_stop`, and
  end-to-end in S2 where a `barge_in` chunk while `speaking` triggers `stop()`
  plus a `BARGE_IN` audit event).

## DialogueService / next-turn — Implemented (scaffold) inside `VoiceEngine.run_call()`

The one-question-at-a-time policy (`engine.py`):

- Priority order is data: `QUESTION_ORDER = ["address", "installation_photo",
  "preferred_date", "device_brand"]` with Polish question templates in
  `QUESTIONS`.
- Per turn, after extraction: **hard stops first** — any handoff trigger →
  `_handoff()` and break; out-of-scope without a detected service →
  `OUT_OF_SCOPE_LINE` and break.
- **Price guard**: price asked while required data is missing →
  `NO_PRICE_LINE` (never a number), answered at most once.
- Then ask **the single highest-priority question** whose item is still
  missing and hasn't been asked yet (`asked` list prevents repeats).
- Invariant tested: no AI turn contains more than one question mark
  (`TestS1NormalQuote.test_one_question_at_a_time`).

Production: an LLM dialogue policy slots in at the same decision point;
hard stops stay rule-enforced — **Designed**.

## `UnderstandingService.extract` — Implemented (scaffold) as `UnderstandingExtractor`

- `process(utterance)`: incremental per-utterance extraction — intent, service
  type, urgency, name/address/date/brand fields, refusals, price-ask flag,
  corrections, promises (+ due), objections, handoff triggers, out-of-scope,
  returning-client references, language set.
- Enforced rules (all tested): unknown stays `{value: None,
  status: "unknown"}`; an ASR-uncertain term is confidence-capped at 0.5 and
  can never reach `confirmed`; a later correction overwrites (last confirmed
  wins); every recorded extraction carries confidence + source utterance ids.
- `missing_items()`: derives open items from `REQUIRED_FIELDS_HVAC`;
  `installation_photo` is always missing mid-call; uncertain values stay
  missing with `note: "value_present_but_uncertain"`.

Production: local-LLM extractor behind the same interface, pattern tables as
playbook data — **Designed**.

## `CaseGraphService.apply_voice_update` — Implemented (scaffold) as `VoiceEngine._end_session()` / `_next_action()`

What a session end writes to the Case Graph:

1. **Case create/link**: create `Case(autonomy_level=3,
   state=CaseState.NEW_CONTACT)` only when there is an in-scope intent and no
   existing case (audited as `case.created{source: "voice"}`); returning
   clients keep their existing `case_id` — never duplicated (S10). Out-of-scope
   calls create **no** case (S9).
2. **MissingItems**: one `MissingItem` per open item — `weight` 0.9 (high) /
   0.5 (medium), `blocks_quote` when it blocks quote preparation; audited as
   `MISSING_INFO_DETECTED`.
3. **Promises**: one `Promise` per detected promise, `due_at = now +
   DUE_TO_HOURS[due]`, `importance=0.7`, `dependency_impact=0.8`; audited as
   `PROMISE_DETECTED`; a photo promise also emits a
   `followup_if_no_photos` task proposal.
4. **Next best action** (via `_next_action`, audited as
   `NEXT_ACTION_CREATED`): priority — `human_callback` (handoff, always
   `requires_human_approval: true`) → `close_out_of_scope` →
   `send_photo_request` (**gated through `finalis.autonomy.gate(case,
   "send_missing_info_request")`** — approval required when the case's
   effective autonomy is below L3) → `send_missing_info_request` →
   `prepare_quote`. Written to `case.next_best_action` with
   `next_action_due_at = now + 4h`, wiring the case into the completion loop.
5. **Certainty stamp**: the four fact fields go through
   `certainty_core.NullAdapter.certify()` (verdict `heuristic`,
   policy `hvac-playbook-v1`) — the LGGT seam; its `audit_id` lands in the
   output as `certainty_audit_id`.

Production: the same objects persisted through the core API/Postgres instead
of in-memory — **Designed**.

## `AuditService.write` — Implemented (scaffold) as `finalis.audit.AuditLog`

`append(event_type, actor, case_id, payload)` — append-only, SHA-256
hash-chained (`hash_prev`/`hash_self`, genesis = 64 zeros); no update/delete
API exists. `verify_chain()` is asserted after **every** test call. Voice event
types are listed in [data-model.md §5.3](data-model.md). Production adds
Postgres persistence and the transactional-outbox relay of doc 22 §2 —
**Designed**.

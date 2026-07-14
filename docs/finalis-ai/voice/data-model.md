# Finalis Voice Engine — Data Model

> Ground truth: `finalis/voice/models.py` on branch
> `claude/finalis-voice-engine-open-core`, exercised by 26 passing tests in
> `tests/test_voice_engine.py`. Status labels follow the
> [acceptance rule](README.md#acceptance-rule): **Implemented** = executable and
> tested in this repo; **Designed / Reserved** = field or behavior present in the
> schema but not yet populated by any code path.
>
> Companion docs: `../04-data-model.md` (core entities the voice engine reuses),
> `architecture.md` (component map), `api-contracts.md` (REST + internal
> interfaces), `e2e-test-plan.md` (scenario coverage).

The voice engine adds **four entities** (`VoiceSession`, `Utterance`,
`VoiceExtraction`, `VoiceMetric`) and **reuses three core entities**
(`Promise`, `MissingItem`, `AuditEvent` from `finalis/models.py` /
`finalis/audit.py`). Voice deliberately introduces no parallel promise/missing/
audit types — a call feeds the **same Case Graph** as every other channel.

All ids are UUID strings generated at construction. The scaffold uses
dataclasses, not an ORM: it proves logic, not persistence; field names are
chosen so the production schema (doc 04 conventions: `tenant_id` scoping, RLS,
`created_at/updated_at`) can be generated from the same shapes.

---

## 1. `VoiceSession`

**Purpose.** One call = one session. The unit of consent, tenancy, lifecycle,
handoff state, and the anchor for utterances, extractions, and metrics.
Corresponds to doc 04's `Call` at production time.

**Fields** (from `finalis/voice/models.py`):

| Field | Type | Default | Notes |
|---|---|---|---|
| `id` | `str` (uuid) | auto | PK |
| `tenant_id` | `str` | required | Every session is tenant-scoped |
| `channel` | `str` | required | `webrtc \| sip \| test_transcript` |
| `case_id` | `Optional[str]` | `None` | Set at start (returning client) or when `_end_session` creates a `Case` |
| `language` | `str` | `"en"` | Session default; the engine starts sessions with `"pl"` |
| `status` | `str` | `"created"` | `created → active → ended \| handed_off` |
| `recording_allowed` | `bool` | `False` | Consent gate — only true if consent explicitly given |
| `consent_asked` | `bool` | `False` | Engine sets `True` in `start_session` |
| `audio_uri` | `Optional[str]` | `None` | **Reserved** — always `None` in the scaffold (no audio path); tested: stays `None` without consent |
| `transcript_uri` | `Optional[str]` | `None` | **Reserved** — always `None` in the scaffold (transcript lives in `utterances`) |
| `summary` | `Optional[str]` | `None` | Template-built, facts-only (`VoiceEngine._summary`) |
| `human_handoff_requested` | `bool` | `False` | Set by `_handoff()` |
| `handoff_reason` | `Optional[str]` | `None` | `human_requested \| anger \| legal_advice \| medical_advice` |
| `started_at` / `ended_at` | `Optional[str]` | `None` | ISO-8601 UTC timestamps |
| `utterances` | `list[Utterance]` | `[]` | Full diarized transcript |
| `extractions` | `list[VoiceExtraction]` | `[]` | Reserved at session level; the scaffold accumulates extractions on the in-call `Understanding` object |
| `metrics` | `VoiceMetric` | auto | Auto-created in `__post_init__` with matching `voice_session_id` |

**Relations.** → many `Utterance`, many `VoiceExtraction`, one `VoiceMetric`;
→ optionally one `Case` (`case_id`). `AuditEvent`s reference the session via
`payload.voice_session_id`.

**Retention / privacy.**
- **Recordings are consent-gated** (`recording_allowed`): without consent
  nothing is recorded and `audio_uri` stays `None`
  (tested: `TestSessionAndConsent.test_no_recording_without_consent`).
  Production default per doc 04 `Call`: audio retained 90 days,
  region-configurable; consent notice per `VoiceProfile.consent_prompt`.
- The `summary` and `handoff_reason` may reference PII-adjacent facts;
  retention follows the case.

**Example (JSON projection):**

```json
{
  "id": "b7f1c2ce-4b6c-4e1a-9a3d-5e1f0c9d2a11",
  "tenant_id": "hvac-1",
  "channel": "test_transcript",
  "case_id": "0fdc2771-49a3-4df2-8b84-49556ff9ec43",
  "language": "pl",
  "status": "ended",
  "recording_allowed": true,
  "consent_asked": true,
  "audio_uri": null,
  "transcript_uri": null,
  "summary": "Client requested heat pump quote. Missing: installation_photo, device_brand.",
  "human_handoff_requested": false,
  "handoff_reason": null,
  "started_at": "2026-07-07T10:02:11.482913",
  "ended_at": "2026-07-07T10:05:47.109226"
}
```

---

## 2. `Utterance`

**Purpose.** One diarized turn — client or AI — with the full set of ASR
annotations the extractor needs (confidence, language, uncertain terms,
interruption flag). This is the evidence unit: every extraction points back at
utterance ids.

**Fields:**

| Field | Type | Default | Notes |
|---|---|---|---|
| `id` | `str` (uuid) | auto | PK |
| `voice_session_id` | `str` | required | FK → `VoiceSession` |
| `speaker` | `str` | required | `client \| ai` |
| `text` | `str` | required | Transcript text (**PII**) |
| `start_ms` / `end_ms` | `int` | `0` | Timing within the call; `0/0` in transcript fixtures unless annotated |
| `confidence` | `float` | `1.0` | ASR confidence `[0,1]`; AI turns default to `1.0` |
| `language` | `str` | `"en"` | Per-utterance language ID (`pl \| de \| es \| en`) |
| `is_interruption` | `bool` | `False` | `True` when the chunk carried a `barge_in` flag |
| `uncertain_terms` | `list[str]` | `[]` | Terms the ASR flagged as low-confidence — these can never become confirmed facts |

**Relations.** → `VoiceSession`; referenced by
`VoiceExtraction.source_utterance_ids` and `FieldValue.source_utterance_id`
(the evidence chain — the voice equivalent of doc 04's `EvidenceReference`
locator).

**Retention / privacy.** **Transcript text is PII** — encrypted at rest in
production, retention follows the case (doc 04 `Call`: transcript retained with
case while audio expires earlier).

**Example:**

```json
{
  "id": "3a9e7c10-88d2-4f0b-9c55-2d6e4f7a8b01",
  "voice_session_id": "b7f1c2ce-4b6c-4e1a-9a3d-5e1f0c9d2a11",
  "speaker": "client",
  "text": "My name is Jan Kowalski, the house is at ul. Kwiatowa 12 in Poznań.",
  "start_ms": 14200,
  "end_ms": 19850,
  "confidence": 0.93,
  "language": "en",
  "is_interruption": false,
  "uncertain_terms": []
}
```

---

## 3. `VoiceExtraction`

**Purpose.** One structured fact pulled from the call, with confidence and a
pointer to its source utterance(s) — the voice-channel analogue of doc 04's
`ExtractedField` + `EvidenceReference` pair.

**Fields:**

| Field | Type | Default | Notes |
|---|---|---|---|
| `id` | `str` (uuid) | auto | PK |
| `voice_session_id` | `str` | required | FK → `VoiceSession` |
| `case_id` | `Optional[str]` | required (nullable) | FK → `Case`, if one exists at extraction time |
| `extraction_type` | `str` | required | Declared enum in the model comment: `intent \| field \| promise \| missing \| objection`. The scaffold's extractor actually records `intent`, `promise`, `objection`, and `handoff_trigger` (an addition to the declared enum); `field` and `missing` are reserved — field values live on `FieldValue`/`Understanding` and missing items are derived by `missing_items()` rather than recorded as extractions. |
| `payload` | `dict[str, Any]` | required | e.g. `{"intent": "request_quote"}`, a promise dict, `{"trigger": "anger"}` |
| `confidence` | `float` | required | `[0,1]` |
| `source_utterance_ids` | `list[str]` | `[]` | Evidence chain to `Utterance` rows |

**Relations.** → `VoiceSession`, → `Case` (nullable), → many `Utterance`
(evidence).

**Retention / privacy.** Payloads can quote transcript fragments (promise text,
names) — treat as PII; retention follows the case.

**Example:**

```json
{
  "id": "5e2d1f44-6a3b-4c7d-8e9f-0a1b2c3d4e5f",
  "voice_session_id": "b7f1c2ce-4b6c-4e1a-9a3d-5e1f0c9d2a11",
  "case_id": "0fdc2771-49a3-4df2-8b84-49556ff9ec43",
  "extraction_type": "intent",
  "payload": { "intent": "request_quote" },
  "confidence": 0.93,
  "source_utterance_ids": ["9c4f2e88-1b7a-4d3c-a6e5-7f8091a2b3c4"]
}
```

---

## 4. `VoiceMetric`

**Purpose.** Per-session quality/latency record for the Evaluation Lab
(doc 15). Designed to be **honest**: every latency field is `Optional` and the
`measured` flag says whether any timing was actually measured.

**Fields:**

| Field | Type | Default | Scaffold status |
|---|---|---|---|
| `voice_session_id` | `str` | required | Implemented (set on session creation) |
| `p50_first_response_latency_ms` | `Optional[float]` | `None` | **Reserved — `None` = not measured** (no audio path) |
| `p95_first_response_latency_ms` | `Optional[float]` | `None` | Reserved — `None` |
| `asr_latency_ms` | `Optional[float]` | `None` | Reserved — `None` |
| `llm_latency_ms` | `Optional[float]` | `None` | Reserved — `None` |
| `tts_latency_ms` | `Optional[float]` | `None` | Reserved — `None` |
| `barge_in_success` | `Optional[bool]` | `None` | Reserved — `None` (barge-in *reaction* is tested; stop *timing* is not measurable without audio) |
| `intent_confidence` | `float` | `0.0` | **Implemented** — set from the winning intent detection |
| `extraction_confidence` | `float` | `0.0` | **Implemented** — min confidence across non-null extracted facts |
| `measured` | `bool` | `False` | **Implemented and asserted** — stays `False` in the transcript-only MVP (`TestSessionAndConsent.test_metrics_marked_not_measured`) |

**Relations.** 1:1 with `VoiceSession` (auto-created in `__post_init__`).

**Retention / privacy.** **Non-PII** — aggregate numbers only, no transcript
content. Safe for long retention and cross-tenant benchmarking dashboards
(Evaluation Lab, doc 15).

**Example (S1, exactly as the scaffold produces it):**

```json
{
  "voice_session_id": "b7f1c2ce-4b6c-4e1a-9a3d-5e1f0c9d2a11",
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

---

## 5. Reused core entities — voice feeds the same Case Graph

Voice creates **no parallel types** for promises, missing information, or
audit. `VoiceEngine._end_session()` writes directly into
`finalis.models.Case.promises` / `.missing_items` and appends to the shared
hash-chained `finalis.audit.AuditLog`.

### 5.1 `Promise` (`finalis/models.py`; production schema in doc 04)

**Purpose.** A commitment by any party; the Promise Tracker's unit. Voice
detects promises from client speech ("I'll send you the photos tomorrow").

| Field | Type | How voice populates it |
|---|---|---|
| `id` | `str` (uuid) | auto |
| `promisor` | `str` | `"client"` (from the promise pattern's `who`) |
| `what` | `str` | e.g. `"send photos"`, `"call back"`, `"confirm details"` |
| `due_at` | `datetime` | `now + DUE_TO_HOURS[due]` — `today`→8h, `tomorrow`→24h, `this_week`→96h, `unspecified`→48h |
| `importance` | `float` | `0.7` (scaffold constant) |
| `dependency_impact` | `float` | `0.8` (scaffold constant) |
| `status` | `str` | `"open"` (default) |
| `evidence` | `Optional[EvidenceReference]` | **Not populated by voice in the scaffold** — production links the source utterance/timestamp per doc 04/06 §5 |

A `send photos` promise additionally yields a follow-up task proposal
`{"type": "followup_if_no_photos", "due": "...", "channel": "sms_or_whatsapp"}`
on `VoiceEngineResult.tasks` (tested in S4).

**Example (S4 — boiler-photo promise):**

```json
{
  "id": "7d4a9b2e-0c1f-4e6a-b8d3-5f2e1a0c9b87",
  "promisor": "client",
  "what": "send photos",
  "due_at": "2026-07-08T10:05:47.109226",
  "importance": 0.7,
  "dependency_impact": 0.8,
  "status": "open",
  "evidence": null
}
```

### 5.2 `MissingItem` (`finalis/models.py`; production schema in doc 04)

**Purpose.** A piece of information blocking progress; the Missing-Info
Hunter's unit. Voice derives it from `REQUIRED_FIELDS_HVAC` minus what the call
confirmed (uncertain values still count as missing — see S11).

| Field | Type | How voice populates it |
|---|---|---|
| `id` | `str` (uuid) | auto |
| `field_key` | `str` | `address \| installation_photo \| preferred_date \| device_brand` |
| `label` | `str` | Same as `field_key` in the scaffold (playbook labels in production) |
| `weight` | `float` | `0.9` for `severity: high`, `0.5` for `severity: medium` |
| `blocks_quote` | `bool` | `True` when the item's `blocks == "quote_preparation"` |
| `status` | `str` | `"missing"` (default) |

Note: `installation_photo` is **always** missing at call end — photos cannot
arrive during a call; a photo-send promise covers the request path but the item
stays open (tested in S1 and S4).

**Example (S1 — photo still missing after a good call):**

```json
{
  "id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
  "field_key": "installation_photo",
  "label": "installation_photo",
  "weight": 0.9,
  "blocks_quote": true,
  "status": "missing"
}
```

### 5.3 `AuditEvent` (`finalis/audit.py`; production schema in doc 04)

**Purpose.** Append-only, hash-chained source of truth. Every significant voice
moment writes one; `AuditLog.verify_chain()` is asserted after every test run.

| Field | Type | Notes |
|---|---|---|
| `id` | `str` (uuid) | auto |
| `event_type` | `str` | Voice emits: `CALL_STARTED`, `BARGE_IN`, `INTENT_DETECTED`, `case.created`, `MISSING_INFO_DETECTED`, `PROMISE_DETECTED`, `HUMAN_HANDOFF`, `NEXT_ACTION_CREATED`, `CALL_ENDED`, plus `certainty.stamped` from the certainty seam |
| `actor` | `str` | `system \| ai \| client` |
| `case_id` | `Optional[str]` | Null before a case exists |
| `payload` | `dict` | Voice events carry `voice_session_id` (+ event specifics: channel, consent flag, intent + confidence, missing types, promise dict, handoff reason, next action) |
| `hash_prev` / `hash_self` | `str` | SHA-256 tamper-evidence chain (genesis = 64 zeros) |

**Retention / privacy.** Immutable, long retention (doc 04: e.g. 7y);
payloads reference ids, not raw transcript text, wherever possible.

**Example (S1 `INTENT_DETECTED`):**

```json
{
  "id": "c0ffee00-1234-4abc-9def-000000000001",
  "event_type": "INTENT_DETECTED",
  "actor": "ai",
  "case_id": null,
  "payload": {
    "voice_session_id": "b7f1c2ce-4b6c-4e1a-9a3d-5e1f0c9d2a11",
    "intent": "request_quote",
    "confidence": 0.9325
  },
  "hash_prev": "9f3c…e2a1",
  "hash_self": "17bd…40cc"
}
```

---

## 6. The required JSON output after every call

Every call — regardless of how it ended — produces one structured JSON object,
built by `VoiceEngine._build_output()` (`finalis/voice/engine.py`). This is the
call's contract with the rest of the system: the human agent's briefing on
handoff, the Case Graph update payload, and the Evaluation Lab record.

**Actual scaffold output for the S1 scenario** (`S1_NORMAL_HVAC_QUOTE`:
"Hi, I'd like a quote for a heat pump installation." / "My name is Jan
Kowalski, the house is at ul. Kwiatowa 12 in Poznań." / "Thursday would work
best for me."), reproduced from a real run — only the uuids vary per run:

```json
{
  "voice_session_id": "b7f1c2ce-4b6c-4e1a-9a3d-5e1f0c9d2a11",
  "tenant_id": "hvac-1",
  "case_id": "0fdc2771-49a3-4df2-8b84-49556ff9ec43",
  "language": "en",
  "languages_detected": ["en"],
  "intent": "request_quote",
  "case_type": "hvac_installation",
  "client": {
    "name": "Jan Kowalski",
    "name_status": "confirmed",
    "phone": null,
    "preferred_channel": "phone"
  },
  "service": {
    "type": "heat_pump_quote",
    "urgency": "normal",
    "address": "Kwiatowa 12",
    "address_status": "confirmed",
    "preferred_date": "thursday",
    "device_brand": { "value": null, "confidence": 0.0, "status": "unknown" }
  },
  "missing_items": [
    { "type": "installation_photo", "severity": "high", "blocks": "quote_preparation" },
    { "type": "device_brand", "severity": "medium", "blocks": null }
  ],
  "promises": [],
  "objections": [],
  "risks": [],
  "next_action": {
    "type": "send_photo_request",
    "channel": "sms_or_whatsapp",
    "requires_human_approval": false
  },
  "human_review_required": false,
  "handoff_reason": null,
  "returning_client_reference": false,
  "summary": "Client requested heat pump quote. Missing: installation_photo, device_brand.",
  "certainty_audit_id": "101f6598-066a-49cb-bc4f-2884fcecbe05",
  "audit_events": [
    "CALL_STARTED",
    "INTENT_DETECTED",
    "case.created",
    "MISSING_INFO_DETECTED",
    "NEXT_ACTION_CREATED",
    "CALL_ENDED"
  ]
}
```

Shape rules, as implemented:

- `service.address` and `service.preferred_date` surface a plain value **only
  when status is `confirmed`** — otherwise `null`, with the true state carried
  by the `*_status` field. `service.device_brand` is always the full
  `{value, confidence, status}` object (needed for the S11 uncertain-brand
  case, where a value exists but must not read as a fact).
- `client.phone` is always `null` in the scaffold — reserved for channel
  metadata (caller id) in production.
- `risks` currently carries at most `["client_refused_address"]` (S5).
- `audit_events` lists the event types whose payload references this session or
  whose `case_id` matches — a self-describing audit trailer.

### Deviations / additions vs the mission spec's example output

The spec's example carried the core shape (`intent`, `case_type`, `client`,
`service`, `missing_items`, `promises`, `objections`, `next_action`,
`human_review_required`, `summary`). The implementation **adds** fields; none
of the spec's fields were dropped:

| Added field | Why |
|---|---|
| `client.name_status`, `service.address_status`, `device_brand.{confidence,status}` | **Confidence-status transparency** — the extractor's core no-hallucination rule (`unknown \| uncertain \| confirmed`) must survive into the output, so a downstream consumer can never mistake an ASR-uncertain guess for a confirmed fact. Confirmed-only surfacing of plain values depends on these. |
| `languages_detected` | Mixed-language calls (S8: pl + de) need the full per-utterance language set recorded, not just one `language`, for TTS routing and Evaluation Lab cohorts. |
| `certainty_audit_id` | The LGGT Certainty-Core seam (doc 32): every session output is stamped through `NullAdapter.certify()` (verdict `heuristic` in Phase 1), so all decisions are stored in an LGGT-compatible shape from day one. |
| `handoff_reason` | `human_review_required: true` alone is ambiguous — the human agent needs to know *why* (`human_requested` vs `anger` vs `legal_advice` vs `medical_advice`) before picking up. |
| `tenant_id`, `voice_session_id`, `returning_client_reference`, `risks`, `audit_events` | Multi-tenancy explicitness, session traceability, returning-client linking (S10), refusal-risk surfacing (S5), and a self-describing audit trailer for test/ops verification. |

One honest wrinkle: the `certainty.stamped` audit event itself does not appear
in `audit_events`, because its payload carries `decision_ref` rather than
`voice_session_id` and it precedes case linkage — the stamp is instead
reachable via `certainty_audit_id`.

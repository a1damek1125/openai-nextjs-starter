# Finalis Voice Engine — Enterprise Controls

> Status vocabulary, used honestly throughout:
> - **Implemented-scaffold** — real code on `claude/finalis-voice-engine-open-core`, covered
>   by tests in `tests/test_voice_engine.py`, but operating at transcript level (no audio
>   path, no persistence layer, no network).
> - **Designed** — specified in the doc set (cited), zero code.
> - **Missing** — neither code nor an adequate design; called out explicitly.
>
> Nothing in this file is production-attested. The scaffold proves control *logic*; the
> production control surface (storage, network, infra) does not exist yet.

---

## 1. Consent

| Control | Status |
|---|---|
| Recording consent flag on session | **Implemented-scaffold + tested** |
| Transcript-processing consent, mid-call opt-out, per-jurisdiction scripts | **Designed** (doc 04 `Call` entity: consent-gated recordings; doc 06) |

What exists: `VoiceSession.recording_allowed` and `consent_asked`
(`finalis/voice/models.py`); `VoiceEngine.start_session(recording_consent=...)` sets both
and writes `recording_allowed` into the `CALL_STARTED` audit event (`finalis/voice/engine.py`).
Tested (`TestSessionAndConsent::test_no_recording_without_consent`): with no consent,
`recording_allowed` is `False`, the audit event says so, and `audio_uri` stays `None` —
nothing is recorded.

Designed, not built: the spoken consent prompt itself, verbal-consent capture with timestamp
evidence, mid-call revocation ("stop recording") that halts and purges the buffer,
per-jurisdiction consent scripts (some jurisdictions require two-party consent), and
transcript-processing consent as distinct from recording consent.

**Acceptance criteria**
1. No audio byte is ever persisted for a session with `recording_allowed == False`
   (scaffold: proven at flag level; production: proven at storage level — object store audit
   shows zero writes).
2. Consent state (asked / granted / refused / revoked, with utterance evidence) is on the
   session record and in the audit chain.
3. Revocation mid-call stops recording within one utterance and deletes already-buffered
   audio for that call.
4. Jurisdiction-appropriate consent script is selected by tenant region config; absence of
   config blocks recording (fail-closed).

## 2. Privacy (PII redaction, retention, deletion/export)

| Control | Status |
|---|---|
| PII redaction in logs | **Designed** |
| Retention policy | **Designed** (doc 04) |
| Deletion (GDPR erasure) & export | **Designed** (doc 04) |

Redaction rule (design, to be enforced in VS6): **transcripts and PII never appear in
structured logs — only IDs.** Log lines reference `voice_session_id`, `utterance_id`,
`case_id`; a redaction filter sits in front of every log sink and drops/masks `text`,
`client_name`, `address`, phone fields before emission. The scaffold is consistent with this
shape (audit payloads carry IDs, event types, and field *keys*, not transcript text), but no
logging pipeline or filter exists — Designed, honestly.

Retention (doc 04): **audio 90 days default** (region-configurable, consent-gated);
**transcripts follow the case** retention (default active + 24 months post-close). Deletion:
GDPR erasure removes audio object + transcript + derived extractions, leaving tombstoned
audit entries (chain integrity preserved, content removed). Export: per-case bundle of
transcript, extractions, and audit trail.

**Acceptance criteria**
1. Redaction filter test: log capture of a full Stage-2 call contains zero transcript
   substrings and zero PII values; a "canary PII" fixture proves the filter, not luck.
2. Automated retention job deletes audio at tenant-configured TTL (default 90d); deletion is
   itself audit-logged.
3. Erasure request completes ≤30 days, covers all derived artifacts, and is verifiable
   (query for the subject returns nothing except tombstones).
4. Export produces a machine-readable bundle within the API surface of doc 22.

## 3. Tenant isolation

| Control | Status |
|---|---|
| `tenant_id` mandatory on `VoiceSession` | **Implemented-scaffold + tested** |
| Cross-tenant access prevention | **Designed** — production RLS requirement |

What exists: `VoiceSession.tenant_id` is a required constructor field (no default —
`finalis/voice/models.py`); `VoiceEngine` is constructed per tenant and stamps `tenant_id`
into every session and output (`tests: test_session_object_lifecycle` asserts it; S1 asserts
it in the output JSON). Cases created from voice inherit the engine's tenant.

Not existing: any datastore. Isolation today is by construction in-process, which proves the
data model, not the boundary. Production requirement: Postgres **row-level security** keyed
on `tenant_id` for all voice tables (voice_sessions, utterances, extractions, metrics),
tenant-scoped API keys (doc 22), and tenant-prefixed object-store paths for audio.

**Acceptance criteria**
1. Every voice row carries a non-null `tenant_id`; inserts without one are rejected at the
   DB layer.
2. RLS test suite: a session authenticated as tenant A issuing every voice endpoint against
   tenant B's IDs gets 404/permission-denied, never data — including via list endpoints and
   audio URLs.
3. Signed audio URLs are tenant- and time-scoped.
4. Load tests confirm no cross-tenant leakage under connection pooling (RLS variable set per
   transaction, not per connection).

## 4. Security

| Control | Status |
|---|---|
| No secrets in logs/repo | **True today** (scaffold has no credentials; nothing to leak — keep it that way with scanning) |
| Signed webhooks | **Designed** (doc 22: provider HMAC/JWT signature verification, replay protection via timestamp + nonce) |
| Rate limits / abuse prevention | **Designed** |

Rate-limit design: **per-tenant concurrent-session cap** (voice sessions are the expensive
unit — GPU seconds), per-tenant session-start rate limit, per-caller-number throttle
(robodial abuse), and rejection of calls when the tenant is over cap with a polite TTS
message + audit event rather than a silent drop.

**Acceptance criteria**
1. Secret scanning in CI (repo + image); structured-log scan finds zero credential-shaped
   strings; all engine/API keys via secret manager, never env-committed.
2. Webhook endpoints reject unsigned/stale/replayed payloads (unit-tested with recorded
   provider payloads); always-2xx-fast enqueue semantics per doc 22.
3. Concurrency cap enforced: cap+1st simultaneous session for a tenant is refused, audited,
   and visible in tenant metrics; caps configurable per plan.
4. Pen-test items for the audio path: SIP trunk auth, WebRTC token scoping (short-lived,
   single-session), no unauthenticated TURN relay.

## 5. Observability

| Control | Status |
|---|---|
| Structured logs, metrics, traces, health checks | **Designed** |
| `VoiceMetric` entity | **Implemented-scaffold + tested** — with honest `measured = False` |

What exists: `VoiceMetric` (`finalis/voice/models.py`) reserves the exact production metric
slots — `p50/p95_first_response_latency_ms`, `asr_latency_ms`, `llm_latency_ms`,
`tts_latency_ms`, `barge_in_success` — all `None`, with `measured: bool = False`, and the
test suite **asserts** they stay unmeasured in transcript mode
(`test_metrics_marked_not_measured`). This is deliberate: the schema exists so VS1
instrumentation fills real values, and no dashboard can ever show a fabricated latency.

Designed: OTel traces spanning ASR→LLM→TTS per turn; per-stage latency histograms; health
checks per engine (ASR/TTS/LLM liveness + queue depth) feeding the routers' failover;
per-tenant call dashboards; alerting on P95 breach, handoff-rate spike, ASR-confidence drop.

**Acceptance criteria**
1. Every turn produces one trace with child spans per stage; `VoiceMetric.measured` flips to
   `True` only when populated from real timestamps.
2. Health endpoint per engine; router failover events are counted and alertable.
3. Dashboards show the §2 harness metrics per tenant/language; no metric displays without a
   sample-size annotation.
4. Log lines pass the §2 redaction gate (IDs only).

## 6. Cost control

| Control | Status |
|---|---|
| Per-tenant voice-minute limit | **Designed** |
| Model runtime budget (GPU pool) | **Designed** |
| Fallback policy | **Implemented-scaffold + tested** (routing logic; real engines pending) |
| Kill switch | **Designed** |

Fallback is the one piece with real code: `ASRRouter` fails over on engine crash or
low confidence and keeps the more confident result; `TTSRouter` picks by language and falls
back on synthesis failure (`finalis/voice/routers.py`; tests
`test_asr_failover_on_low_confidence`, `test_asr_failover_on_crash`,
`test_tts_language_aware_selection_and_fallback`). The engines behind it are mocks — the
*policy* is tested, the *cost effect* is not.

Designed: per-tenant monthly voice-minute quota with soft warning and hard cap (over-cap
inbound calls get a human-callback flow, never a dead line); a shared GPU pool budget with
per-model runtime allocation (ASR/TTS/LLM) and admission control when saturated (degrade to
smaller models before refusing calls); per-tenant and global **kill switch** that disables
AI voice answering (falls back to voicemail/human routing) within seconds, without deploy.

**Acceptance criteria**
1. Minute metering per session reconciles with telephony provider CDRs within 1%.
2. Hard cap enforced and audited; tenant sees usage in dashboard before hitting it.
3. Degradation ladder tested: GPU saturation triggers fallback engines (already-tested
   router path) before call refusal; refusal is last and audited.
4. Kill switch drill: flip-to-effect ≤ 60 s, in-flight calls handed off gracefully, restore
   is equally fast.

# Finalis AI — API & Event Model

> Developer-ready contract for the HTTP surface (dashboard + server-to-server + inbound
> webhooks) and the internal domain-event model that drives the Orchestrator. Entities,
> states, and scores referenced here are defined in `04-data-model.md`,
> `03-case-lifecycle-state-machine.md`, and `05-algorithms-and-scoring.md`; the worker I/O
> contract is in `20-final-build-specification.md` §2. Nothing here introduces a new entity,
> score, or state.

---

# PART 1 — API DESIGN

## 1.1 Principles

| Principle | Rule |
|---|---|
| Style | REST + JSON over HTTPS for dashboard and server-to-server; resource nouns, standard verbs. |
| Real-time | SSE (default) or WebSocket at `/v1/stream` for live dashboard updates (case timeline, approvals, scores). Webhooks **in** from providers; no polling for channel events. |
| Tenancy | Every endpoint is tenant-scoped. `tenant_id` derives from the auth principal, never from the request body. Postgres RLS is the second enforcement layer (`04`) — the API layer sets `SET LOCAL app.tenant_id`. |
| Auth | Dashboard: NextAuth session (OAuth2/OIDC) → `UserRole` permissions. Server-to-server: API keys (`Authorization: Bearer fnls_sk_...`), scoped per tenant + capability. Webhooks: provider signature verification (HMAC/JWT per provider). |
| Idempotency | All mutating endpoints accept `Idempotency-Key` header (uuid, retained ≥24h). Replays return the original response with `Idempotent-Replay: true`. |
| Pagination | Cursor-based: `?cursor=...&limit=` (default 25, max 100). Responses: `{ data: [...], next_cursor, has_more }`. Sorted by `created_at desc` unless stated. |
| Autonomy | Endpoints that trigger outbound client contact or commitments are gated by the case's effective autonomy level (`13`); below-threshold requests are **not rejected** — they enqueue a `HumanApproval` and return `202` with the approval id. |
| Audit | Every mutation writes an `AuditEvent` (append-only, hash-chained). The API never edits or deletes audit rows. |
| Evidence | Any response carrying AI claims (briefs, comparisons, risk flags, extracted fields) embeds `evidence_ref_ids` and `confidence` — the UI contract of `11`. |

Base URL: `https://api.finalis.ai/v1` (dashboard uses the same routes via Next.js API proxy).

## 1.2 Resource endpoints

Common conventions: `GET /{resource}` = list (cursor-paginated, filterable), `GET /{resource}/{id}` = fetch, `POST` = create, `PATCH` = partial update. All ids are uuids. Read endpoints require `read_only`+; mutations require the `UserRole.permissions` noted.

### Cases

| Method & path | Purpose | Key request / response fields | Autonomy / permission notes |
|---|---|---|---|
| `GET /cases` | List/filter cases | Filters: `status`, `owner_id`, `min_lead_score`, `due_before`, `q` (semantic via pgvector). Returns `Case` projections incl. `lead_score, risk_score, mis_score, stuck_score, escalation_score, next_best_action, next_action_due_at, autonomy_level`. | Any role. |
| `GET /cases/{id}` | Full case file | Case + embedded counts, `primary_party`, latest `DecisionBrief`, open `MissingItem`s/`Promise`s. `?include=graph` returns `graph_edges` adjacency. | Any role. |
| `POST /cases` | Manually create a case | `{ goal, industry_type, playbook_id, primary_party_id \| party: {...}, source_channel: "manual", value_estimate?, owner_id? }` → `201` Case in `NEW_CONTACT`. | `agent`+. Emits `case.created`. |
| `POST /cases/{id}/transitions` | Request a state transition | `{ to_state, reason, evidence_ref_ids? }`. Server validates against the transition table in `03` §4; illegal transitions → `409`. Human-initiated transitions always allowed within the table; AI callers restricted per state's allowed-actions. | `agent`+ for most; transitions out of `HUMAN_REVIEW_REQUIRED` require `manager`+ (they *are* the human decision). Writes `AuditEvent{from_state,to_state,actor}`. |
| `GET /cases/{id}/next-action` | Current NBA | `{ next_best_action, next_action_due_at, utility_score, chosen_over }` (from `Action` selection, `05` §3). | Any role. |
| `POST /cases/{id}/next-action/recompute` | Force score + NBA recompute | Returns recomputed scores + NBA. | `agent`+. Emits `scores.recomputed`. |
| `PATCH /cases/{id}` | Update mutable fields | `owner_id, goal, value_estimate, autonomy_level (≤ tenant default), wake_at (RECOVERY_LATER only), closed_reason`. Status is **not** patchable — use `/transitions`. | `agent`+ (autonomy_level: `manager`+). |

### Parties

| Method & path | Purpose | Notes |
|---|---|---|
| `GET /parties`, `GET /parties/{id}` | Lookup by `phone`, `email`, `whatsapp_id`, `type` | PII — access is audit-logged. |
| `POST /parties` | Create | `{ type, display_name, phones[], emails[], preferred_channel, preferred_language, quiet_hours }`. Dedup check on phone/email; `409` with existing id on match. |
| `PATCH /parties/{id}` | Update contact prefs, opt-outs | Setting `contact_opt_outs` is **one-way sticky** for hard opt-outs (suppression hash survives erasure, `04`). |
| `POST /cases/{id}/parties` | Attach party to case | `{ party_id, role }` → `CasePartyRole`. |
| `POST /parties/{id}/erasure` | GDPR erasure (DSAR) | `owner` only; async job; audit-logged; opt-out suppression retained. |

### Conversations & Messages

| Method & path | Purpose | Notes |
|---|---|---|
| `GET /cases/{id}/conversations` | List threads | Includes `channel, intent, sentiment, last_inbound_at/last_outbound_at`. |
| `GET /conversations/{id}/messages` | List messages | Cursor by `created_at asc`; each `Message` includes `direction, sent_by, delivery_status, detected_promises, detected_missing`. |
| `POST /conversations/{id}/messages` | **Send outbound message** | `{ body, channel?, template_id?, attachments? }`. **Autonomy-gated**: caller `sent_by=human` executes directly (still audited); `sent_by=ai` requires effective Level ≥3 (Communicate) for non-committal content, ≥4 for commitments (quote send, booking confirm). Below level → `202 { human_approval_id }`. Hard blocks regardless of level: opt-out, quiet hours, AnnoyanceRisk cool-down, `HUMAN_REVIEW_REQUIRED` freeze → `403 autonomy_blocked` with reason. Emits `message.sent` on execution. |

### Calls

| Method & path | Purpose | Notes |
|---|---|---|
| `POST /webhooks/telephony` | Call event ingest (see §1.3) | Signature-verified; not a dashboard route. |
| `GET /cases/{id}/calls` | List calls | `direction, duration_ms, summary, handoff_to_human, latency_metrics`. |
| `GET /calls/{id}` | Call detail | Includes `sentiment_timeline, detected_promises, detected_missing, next_actions`. |
| `GET /calls/{id}/transcript` | Diarized transcript | `{ segments: [{ts_start, ts_end, speaker, text, language}] }`. Recording URL is a short-lived signed S3 link; access audit-logged (consent-gated per `VoiceProfile`). |
| `POST /calls` | Initiate outbound call | `{ case_id, party_id, objective, script_hints? }`. Autonomy ≥3 (info calls) / ≥4 (commitment calls); else `202` approval. |

### Documents & Photos

| Method & path | Purpose | Notes |
|---|---|---|
| `POST /cases/{id}/documents` | Upload | Multipart or `{ storage_url }` after presigned-URL flow (`POST /uploads` → S3 URL). Creates `Document{status: received}`; emits `document.received`; pipeline runs async. Photos: same route with `kind=photo` → `Photo`. |
| `GET /documents/{id}` | Metadata + status | `status: received\|processing\|analyzed\|needs_rescan`, `ocr_quality, overall_confidence, doc_risk_score`. |
| `GET /documents/{id}/analysis` | Full analysis | `{ extracted_fields: [ExtractedField incl. confidence, page, bbox, verified_by_human], risk_flags: [RiskFlag], evidence_refs, summary }`. `404` until `analyzed`. |
| `POST /documents/{id}/rescan` | Request re-scan | Marks `needs_rescan`, emits `document.needs_rescan` → Follow-up Worker asks client for a clearer copy (that outbound message is itself autonomy-gated). |
| `PATCH /extracted-fields/{id}` | Human verify/correct a field | Sets `verified_by_human`; audited; feeds Evaluation Lab calibration. `agent`+. |

### Offers & Comparisons

| Method & path | Purpose | Notes |
|---|---|---|
| `GET /cases/{id}/offers` | List offers | `origin: ours\|competitor\|client_provided`, `offer_score, status, version`. |
| `POST /cases/{id}/offers` | Create offer (draft) | `{ origin, price, currency, scope, deadline, warranty, payment_terms, exclusions, document_id? }` → `draft`. Emits `offer.created`. |
| `POST /offers/{id}/send` | Send offer to client | **High-gate**: requires Level ≥4 *and* price within `price_rules` bounds *and* `mis_score` below quote-blocking threshold; otherwise `202` approval. On execute: `status=sent`, `offer.sent`, case → `OFFER_SENT`. |
| `POST /cases/{id}/comparisons` | Run offer comparison | `{ offer_ids[], weights_version? }` → `202 { comparison_id }`; Offer Comparator runs async; emits `comparison.completed`. |
| `GET /comparisons/{id}` | Result | `{ axis_scores, recommendation, hidden_risk_flags → evidence_refs, confidence }`. |

### Promises / MissingItems

| Method & path | Purpose | Notes |
|---|---|---|
| `GET /cases/{id}/promises` | List | Filter `status: open\|fulfilled\|broken\|waived`, `due_before`. Includes `breach_score, evidence_ref_id`. |
| `POST /cases/{id}/promises` | Create (human or worker proposal applied) | `{ promisor_party_id, what, due_at, importance }`. Emits `promise.created`. |
| `PATCH /promises/{id}` | Fulfil / waive | `{ status, evidence_ref_id? }`. Emits `promise.fulfilled`; `broken` is set by the sweep, not this endpoint. |
| `GET /cases/{id}/missing-items` | List | `status: missing\|requested\|received\|waived`, `weight, blocks_quote, satisfied_by`. |
| `PATCH /missing-items/{id}` | Waive / mark satisfied manually | `agent`+; emits `missing_item.satisfied` when moved to `received`/`waived`. |

### Actions & Tasks

| Method & path | Purpose | Notes |
|---|---|---|
| `GET /cases/{id}/actions` | Scheduled + executed actions | Filter `status`, `scheduled_after`. Includes `type, channel, autonomy_level_used, utility_score, chosen_over, approved_by, result`. Read-only audit surface — actions are created by the Orchestrator, never by this API directly. |
| `POST /actions/{id}/cancel` | Cancel a scheduled action | `agent`+; only `status=scheduled`; audited. |
| `GET /tasks`, `GET /tasks/{id}` | Human work queue | Filter `assignee_id, status, due_before, priority`. |
| `POST /tasks`, `PATCH /tasks/{id}` | Create / progress a task | `{ title, case_id, assignee_id, priority, due_at }`; status flow `open→in_progress→done\|snoozed`. |

### HumanApprovals — the critical HITL endpoint

| Method & path | Purpose | Notes |
|---|---|---|
| `GET /approvals?pending=true` | Pending approvals queue | Sorted by `deadline asc`; each: `{ id, case_id, action: {type, payload}, context, options, recommended_option, requested_at, deadline, sla_breached }`. Powers the Command Center approval inbox + SSE push. |
| `GET /approvals/{id}` | Full context | Includes evidence refs and the draft content the AI prepared (Level 2 output). |
| `POST /approvals/{id}/decision` | **Decide** | `{ decision: "approve" \| "reject" \| "edit_and_approve", chosen_option?, edited_payload?, note }`. Requires `manager`+ (or per-`permissions` grant). Records `decided_by/decided_at`, emits `approval.decided`; on approve the Orchestrator executes the gated `Action` (→ `action.approved` → `action.executed`) and applies any queued transition. Idempotent: second decision → `409 already_decided`. |

### DecisionBriefs

| Method & path | Purpose | Notes |
|---|---|---|
| `GET /cases/{id}/briefs` | Brief history | Latest first; `superseded` flag. |
| `GET /briefs/{id}` | One brief | `{ summary, value_range, situation, recommended_step, rationale, risk_note, confidence, evidence_ref_ids, generated_by_model }`. |
| `POST /cases/{id}/briefs/refresh` | Ask Decision Worker for a fresh brief | `202`; supersedes prior on completion. `agent`+. |

### FollowUpSequences

| Method & path | Purpose | Notes |
|---|---|---|
| `GET /cases/{id}/followup` | Current sequence | `{ name, steps, active_step_index, state: running\|paused\|exhausted, max_attempts, quiet_hours }`. |
| `POST /followups/{id}/pause` / `POST /followups/{id}/resume` | Pause/resume cadence | `agent`+; audited; resume re-evaluates `FollowUpPriority` before scheduling. Pausing cancels scheduled follow-up `Action`s. |
| `PATCH /followups/{id}` | Tune steps/limits for this case | Within playbook bounds (`max_attempts`, `min_interval`). `manager`+. |

### BusinessProfile & IndustryPlaybook

| Method & path | Purpose | Notes |
|---|---|---|
| `GET /business-profile` | Tenant config | Thresholds (`θ_qualify, θ_escalate, θ_docrisk, θ_conf, θ_mis, θ_stuck, θ_breach`), `autonomy_defaults`, quiet hours, price rules, `high_value_threshold`, `data_region`. |
| `PATCH /business-profile` | Update config | `owner`/`manager` only; threshold and autonomy changes are audited with before/after. |
| `GET /playbooks`, `GET /playbooks/{id}` | Playbooks | `intake_schema, required_fields, scoring_weights, offer_weights, followup_defaults, escalation_rules, templates, version`. |
| `PATCH /playbooks/{id}` | Update playbook | Creates a new `version` (immutable history — scores persist `weights_version` for reproducibility). `manager`+. |

### IntegrationAccounts

| Method & path | Purpose | Notes |
|---|---|---|
| `GET /integrations` | Connected providers + status | Never returns secrets — `credentials_ref` handle only. |
| `POST /integrations/{provider}/connect` | Start OAuth / credential flow | Returns provider auth URL; callback stores tokens in the secrets manager and writes `IntegrationAccount`. `owner`/`manager`. |
| `DELETE /integrations/{id}` | Disconnect | Revokes tokens, disables dependent webhooks/actions; audited. |

### AuditEvents & Metrics (read-only)

| Method & path | Purpose | Notes |
|---|---|---|
| `GET /audit-events` | Query the log | Filters: `case_id, event_type, actor, from/to time`. Returns events incl. `from_state, to_state, payload, evidence_ref_ids, hash_prev`. **No mutation routes exist.** `GET /audit-events/verify?case_id=` re-checks the hash chain. |
| `GET /metrics` | Evaluation Lab metrics (`15`) | Per-tenant: voice latency P50/P95, intake completion, OCR field F1 + ECE, follow-up success, hallucination rate, escalation precision/recall, approval + reversal rate, close-assist rate. Filter by period/vertical. |
| `GET /metrics/evaluations` | Golden-set run results | Read-only; CI writes them via internal path. |

### Real-time stream

`GET /v1/stream` (SSE; `Accept: text/event-stream`) — tenant-scoped feed of domain events
(filtered server-side by the caller's `UserRole`): `case.state_changed`, `approval.requested`,
`message.received`, `scores.recomputed`, `document.analysis_completed`, etc. Payloads are the
same envelopes as Part 2. `?case_id=` narrows to one case (Case Detail live timeline).
WebSocket upgrade at the same path for bidirectional dashboard needs; SSE is the default.

## 1.3 Inbound webhook endpoints

All under `/v1/webhooks/*`; authenticated by provider signature (per `IntegrationAccount.webhook_config`), rate-limit-exempt but replay-protected (timestamp + nonce), always `2xx`-fast (enqueue, then process). Each maps a provider payload to a domain event; unmatched contacts trigger case creation/dedup per `NEW_CONTACT` entry rules (`03` §3.1).

| Endpoint | Provider events | Maps to domain event(s) |
|---|---|---|
| `POST /webhooks/telephony` | call initiated / answered / completed / recording ready / DTMF / SIP failure | `call.started`, `call.ended`, then async `call.transcribed`; no-match caller → `case.created` + `contact.inbound_received{channel: phone}` |
| `POST /webhooks/whatsapp` | inbound message/media, delivery receipts, template status, STOP/opt-out | `contact.inbound_received{channel: whatsapp}` + `message.received`; media → `document.received`; delivery receipt updates `Message.delivery_status`; opt-out → forced transition per invariant 6 |
| `POST /webhooks/sms` | inbound SMS, DLRs, STOP | `contact.inbound_received{channel: sms}` + `message.received`; STOP handled as hard opt-out |
| `POST /webhooks/email` | inbound parse (provider or IMAP bridge), bounce, spam report | `contact.inbound_received{channel: email}` + `message.received`; attachments → `document.received`; bounce → delivery status + `FollowUpPriority` input |
| `POST /webhooks/calendar` | event created/updated/cancelled/RSVP | maps to reschedule/cancel handling in `SCHEDULED`; cancellation emits an inbound event that recomputes scores and may transition `SCHEDULED → FOLLOW_UP_ACTIVE/LOST` |

Web form and web chat submit to `POST /v1/webhooks/webform` / first-party chat API — same
`contact.inbound_received` mapping.

## 1.4 Error model, rate limits, versioning

**Errors** — RFC 9457 problem+json, `Content-Type: application/problem+json`:

```json
{
  "type": "https://api.finalis.ai/errors/autonomy_blocked",
  "title": "Action requires human approval",
  "status": 403,
  "detail": "Case is in HUMAN_REVIEW_REQUIRED; outbound actions are frozen (autonomy capped at Level 2).",
  "instance": "/v1/conversations/9f.../messages",
  "case_id": "c1...",
  "human_approval_id": "ha7...",
  "trace_id": "..."
}
```

| Status | `type` slug (examples) | When |
|---|---|---|
| 400 | `validation_error` | Bad fields (with `errors[]` per field) |
| 401 / 403 | `unauthenticated` / `forbidden`, `autonomy_blocked`, `opt_out_suppressed`, `quiet_hours` | Auth, role, or safety gate |
| 404 | `not_found` | Or cross-tenant id (RLS makes it indistinguishable — always 404, never 403) |
| 409 | `invalid_transition`, `already_decided`, `duplicate_party`, `idempotency_conflict` | State conflicts |
| 422 | `confidence_below_threshold` | AI asked to assert below `θ_conf` — it abstains |
| 429 | `rate_limited` | With `Retry-After` |
| 5xx | `internal`, `provider_unavailable` | Degradation per `02` §7; safe to retry with same idempotency key |

**Rate limits** — per API key / session, headers `RateLimit-Limit/Remaining/Reset`:
reads 600/min, mutations 120/min, `POST .../messages` and `POST /calls` additionally
capped by the per-party anti-spam gate (AnnoyanceRisk — this one returns 403, not 429,
because backoff won't help). Webhooks: burst-tolerant queue ingestion.

**Versioning** — path-versioned `/v1`; additive changes (new fields, new event types) are
non-breaking and undocumented fields must be ignored by clients. Breaking changes → `/v2`
with ≥6-month overlap. Event envelopes carry `schema_version`. Playbook/scoring versions are
data (`weights_version`), not API versions.

---

# PART 2 — EVENT MODEL

## 2.1 Event-sourcing approach

- **`AuditEvent` is the append-only source of truth** (`04`): every domain event is persisted
  as an `AuditEvent` row (hash-chained via `hash_prev`) *in the same transaction* as its
  state change. Derived tables (`Case`, scores, projections) can be rebuilt by replay.
- **Domain events drive the Orchestrator.** Publication uses the **transactional outbox**
  pattern: the AuditEvent insert doubles as the outbox; a relay publishes to the bus
  (Postgres queue at MVP; Temporal signals for durable timers — `18`). Workers **consume
  events and return proposals**; only the Orchestrator applies transitions and emits the
  resulting events (worker contract, `20` §2).
- **Envelope** (all events):

```json
{
  "event_id": "uuid",
  "event_type": "document.analysis_completed",
  "schema_version": 1,
  "tenant_id": "uuid",
  "case_id": "uuid",
  "occurred_at": "2026-07-07T10:14:03Z",
  "actor": { "kind": "ai_worker|human|system", "id": "doc-intel-worker" },
  "causation_id": "event_id of the event that caused this",
  "correlation_id": "root event_id of the chain",
  "payload": { }
}
```

## 2.2 Domain event catalog

Producers: **ORCH** = Orchestrator, **GW** = channel/webhook gateway, worker names per `02` §4.
Consumers listed are the primary ones; the SSE stream, Case Timeline projection, and
Evaluation Lab metrics pipeline consume **everything** and are omitted per-row.

| Event | Payload sketch | Producer | Consumers |
|---|---|---|---|
| `case.created` | `{ source_channel, party_id, industry_type, playbook_id, initial_intent? }` | ORCH (on GW no-match or `POST /cases`) | Intake Worker; scoring (initial `LeadScore`/`MIS`) |
| `case.state_changed` | `{ from_state, to_state, reason, evidence_ref_ids }` | ORCH (sole emitter — invariant 4, `03`) | Completion Loop (re-plan NBA); Follow-up Worker; Command Center |
| `contact.inbound_received` | `{ channel: phone\|whatsapp\|sms\|email\|webform\|webchat, party_id?, raw_ref, matched_case_id? }` | GW | ORCH router (dedup/match → route to state's owning worker); EscalationScore recompute (invariant 5) |
| `call.started` | `{ call_id, direction, party_id, provider_call_id }` | GW/Voice Worker | ORCH; Command Center live indicator |
| `call.ended` | `{ call_id, duration_ms, handoff_to_human, latency_metrics }` | Voice Worker | ORCH; transcription job |
| `call.transcribed` | `{ call_id, summary, detected_promises[], detected_missing[], next_actions[], sentiment_timeline }` | Voice Worker (post-call) | ORCH (applies Promise/MissingItem proposals); Promise Tracker; Missing-Info Hunter; Quality Worker |
| `message.received` | `{ message_id, conversation_id, channel, body_ref, attachments[], detected_promises[], detected_missing[], sentiment }` | GW (+NLU enrich) | ORCH router; Promise Tracker; Objection Handler (in `NEGOTIATION`); Follow-up Worker (stops pending cadence step) |
| `message.sent` | `{ message_id, channel, sent_by: ai\|human, autonomy_level_used, template_id?, delivery_status }` | ORCH (after send `Action` executes) | Follow-up sequence advance; AnnoyanceRisk accounting; Conversation projection |
| `document.received` | `{ document_id \| photo_id, source, mime, case_id, via_channel }` | GW / upload API | Document Intelligence Worker (starts pipeline); Missing-Info Hunter (candidate match) |
| `document.analysis_completed` | `{ document_id, extracted_field_ids[], doc_risk_score, overall_confidence, risk_flag_ids[], evidence_ref_ids[] }` | Doc Intel Worker | ORCH (may transition `DOCUMENT_ANALYSIS → QUOTE_PREPARATION`/`HUMAN_REVIEW_REQUIRED` if `DocRisk ≥ θ_docrisk`); Missing-Info Hunter; Offer Comparator (if offer doc); Quality Worker |
| `document.needs_rescan` | `{ document_id, reason: low_ocr_quality\|missing_pages\|unreadable, ocr_quality }` | Doc Intel Worker | ORCH → Follow-up Worker (request clearer copy; autonomy-gated) |
| `offer.created` | `{ offer_id, origin, price, currency, version, document_id? }` | ORCH / Quote Builder | Offer Comparator (if competitor offer exists); Decision Worker |
| `offer.sent` | `{ offer_id, channel, sent_at, autonomy_level_used, approved_by? }` | ORCH | Follow-up Worker (start post-offer cadence, `03` §3.8); case → `OFFER_SENT` |
| `offer.response_received` | `{ offer_id, response: accepted\|rejected\|counter\|question, source_message_id }` | ORCH (classified from inbound) | ORCH transitions (`WON`/`NEGOTIATION`/...); Objection Handler; Decision Worker |
| `comparison.completed` | `{ comparison_id, offer_ids[], axis_scores, recommendation, hidden_risk_flags[], confidence }` | Offer Comparator | Decision Worker (brief); ORCH (RiskFlags may trip escalation); Command Center |
| `promise.created` | `{ promise_id, promisor_party_id, what, due_at, importance, evidence_ref_id, source_type }` | ORCH (from worker proposals) | Promise Tracker (deadline timer via durable scheduler) |
| `promise.fulfilled` | `{ promise_id, evidence_ref_id }` | Promise Tracker / API | scores recompute (`PromiseBreachScore` ↓); Follow-up Worker |
| `promise.breached` | `{ promise_id, due_at, breach_score, days_overdue }` | Promise Tracker (sweep/timer) | ORCH (NBA re-plan: chase or escalate per `θ_breach`); Decision Worker |
| `missing_item.created` | `{ missing_item_id, field_key, weight, blocks_quote }` | ORCH (Intake/Doc proposals) | Missing-Info Hunter (plan targeted request) |
| `missing_item.satisfied` | `{ missing_item_id, satisfied_by: {type: document\|photo\|message, id}, status: received\|waived }` | Missing-Info Hunter / API | scores recompute (`MIS` ↓); ORCH (unblock: e.g. `WAITING_FOR_DOCUMENTS → DOCUMENT_ANALYSIS`) |
| `scores.recomputed` | `{ scores: {lead_score, risk_score, mis_score, stuck_score, escalation_score, followup_priority?, promise_breach_score?}, inputs_ref, weights_version, trigger }` | ORCH scoring engine | ORCH gates (`θ_escalate` interrupt, `θ_qualify`); NBA selector; dashboard |
| `action.proposed` | `{ action_id, type, channel, payload, utility_score, chosen_over[], autonomy_required, effective_level }` | ORCH (NBA selection from worker proposals) | Guardrails validators; autonomy gate (→ execute or `approval.requested`) |
| `action.approved` | `{ action_id, human_approval_id, approved_by, edited_payload? }` | ORCH (after decision) | Executor |
| `action.executed` | `{ action_id, result, executed_at, produced: {message_id?\|call_id?\|offer_id?\|task_id?} }` | ORCH executor | Follow-up sequence; projections; Evaluation Lab |
| `action.failed` | `{ action_id, error, retry_count, will_retry, degraded_mode? }` | ORCH executor | Retry/DLQ handler; Command Center SLA surface (`02` §7) |
| `approval.requested` | `{ human_approval_id, action_id, context, options[], recommended_option, deadline }` | ORCH | Command Center (push/SSE); notification per `UserRole.notify_channels`; SLA timer |
| `approval.decided` | `{ human_approval_id, decision, decided_by, decided_at, sla_breached }` | ORCH (from `POST /approvals/{id}/decision`) | Executor (on approve); Evaluation Lab (approval + reversal rate) |
| `escalation.triggered` | `{ trigger: threshold\|hard_rule, rule?, escalation_score, θ_escalate, evidence_ref_ids }` | ORCH (invariant 5, `03` §2) | ORCH (forced `case.state_changed → HUMAN_REVIEW_REQUIRED`, autonomy cap L2); `approval.requested` follows |
| `followup.scheduled` | `{ sequence_id, step_index, channel, scheduled_at, followup_priority }` | Follow-up Worker via ORCH | Durable scheduler (Temporal/queue) |
| `followup.sent` | `{ sequence_id, step_index, message_id \| call_id }` | ORCH executor | Sequence advance (`active_step_index`++); AnnoyanceRisk accounting |
| `followup.exhausted` | `{ sequence_id, attempts, last_channel }` | Follow-up Worker | ORCH (transition → `RECOVERY_LATER` with `wake_at`, or `ABANDONED`) |
| `case.parked` | `{ to_state: RECOVERY_LATER, wake_at, recovery_reason }` | ORCH | Durable wake timer |
| `case.woken` | `{ from: RECOVERY_LATER, wake_reason, to_state: FOLLOW_UP_ACTIVE }` | ORCH (timer fire) | Follow-up Worker (fresh context-aware opener); scores recompute |
| `webscout.research_completed` | `{ query, facts: [{claim, source_url, trust_score, evidence_ref_id}], confidence }` | WebScout Worker | Decision Worker; Offer Comparator; ORCH (facts attach to Case Graph) |
| `quality.check_failed` | `{ checked_output_ref, failures: [unsupported_claim\|missing_evidence\|dishonest_confidence\|gap], severity }` | Quality/Eval Worker | ORCH (block/retract the output, re-run or escalate — never ship a failed output); Evaluation Lab (hallucination-rate metric) |

## 2.3 Delivery semantics

| Concern | Design |
|---|---|
| Delivery guarantee | **At-least-once.** Outbox relay retries until acked; consumers must tolerate duplicates. |
| Idempotent consumers | Every consumer dedups on `event_id` (processed-events table / `ON CONFLICT DO NOTHING` on a consumer-offset row). Side-effecting executions (send message, place call) additionally carry a deterministic idempotency key = `action_id`, so a redelivered `action.approved` can't double-send. |
| Ordering | Guaranteed **per case only**: partition key = `case_id` (single consumer-lane per case; in the Postgres-queue MVP: `SELECT ... FOR UPDATE SKIP LOCKED` on the case lane). Cross-case ordering is not guaranteed and nothing may depend on it. Tenant-level events (`BusinessProfile` changes) partition on `tenant_id`. |
| Retries | Exponential backoff with jitter (1s → 5m cap), max 8 attempts for transient failures. `action.failed` is emitted per attempt with `will_retry`. |
| Dead-letter | After max attempts → DLQ table with full envelope + error; emits a `system` AuditEvent and surfaces as a Command Center SLA item (`02` §7). DLQ replays are manual (`manager`+) and re-enter the case lane in order. |
| Causality | `causation_id`/`correlation_id` let the Timeline and Evaluation Lab reconstruct chains (e.g. everything descending from one inbound message). |
| Nightly stuck sweep | The sweep (`03` §5, `09`) is itself an event producer: it iterates active cases, recomputes `StuckScore`, `FollowUpPriority`, `PromiseBreachScore` → emits `scores.recomputed` per case, `promise.breached` for lapsed promises, `case.woken` for due `wake_at`, and `action.proposed` for the chosen NBA. If it finds an active case **without** a future action (invariant 1 violation) it emits a `system` `escalation.triggered{trigger: hard_rule, rule: "no_next_action"}` — failing loudly, as required. Sweep events flow through the same per-case lanes, so they interleave safely with live traffic. |
| Timers | Follow-up offsets, promise deadlines, `wake_at`, approval SLAs are durable timers (Temporal or Postgres-queue `scheduled_at` polling) that fire as events — surviving restarts (`18`). |

## 2.4 Sequence example — inbound WhatsApp photo to autonomous (or approved) reply

Case is in `WAITING_FOR_DOCUMENTS`; the blocking `MissingItem` is `boiler_nameplate_photo`
(`blocks_quote: true`). Client sends the photo on WhatsApp.

```
 1. WhatsApp provider → POST /v1/webhooks/whatsapp  (signature verified, 200 fast)
 2. GW matches party+case → emits  contact.inbound_received{channel: whatsapp}
      └ media attachment stored to S3 → emits  document.received{photo_id, via_channel: whatsapp}
 3. ORCH routes to Document Intelligence Worker (owning worker for WAITING_FOR_DOCUMENTS)
      · quality pre-check passes (else → document.needs_rescan and stop)
 4. Doc Intel Worker returns proposals {extracted: [ExtractedField...], evidence, confidence}
      → ORCH applies → emits  document.analysis_completed{overall_confidence: 0.93, ...}
 5. Missing-Info Hunter consumes it, matches field_key=boiler_nameplate_photo
      → ORCH emits  missing_item.satisfied{satisfied_by: {type: photo, id}, status: received}
      → graph edge DOCUMENT_SATISFIES_MISSING_ITEM written
 6. ORCH recomputes scores → emits  scores.recomputed{mis_score ↓ below quote-block, ...}
      · no blocking MissingItem left → case.state_changed{WAITING_FOR_DOCUMENTS → DOCUMENT_ANALYSIS}
      · analysis already complete → case.state_changed{DOCUMENT_ANALYSIS → QUOTE_PREPARATION}
 7. NBA selector picks "send acknowledgement + quote ETA message"
      → emits  action.proposed{type: send_message, channel: whatsapp,
                utility_score, autonomy_required: 3, effective_level: min(tenant, case)}
 8a. effective_level ≥ 3 (non-committal ack) → guardrails pass (quiet hours, opt-out,
     AnnoyanceRisk, PII) → executor sends via WhatsApp MCP tool
      → emits  action.executed  +  message.sent{sent_by: ai, autonomy_level_used: 3}
 8b. If instead the NBA were "send draft quote" (commitment, requires L4) and the case runs
     at L3 → emits  approval.requested{options, recommended_option, deadline}
      → Command Center push → human POST /approvals/{id}/decision {approve}
      → approval.decided → action.approved → action.executed → message.sent{sent_by: ai}
 9. Every step above was written as a hash-chained AuditEvent in the same transaction as
    its state change; the dashboard timeline received each event live over /v1/stream.
```

Duplicate webhook delivery at step 1 replays `event_id` dedup at step 2; a crash between
6 and 7 is recovered by the durable orchestrator resuming from the checkpoint, and — worst
case — the nightly sweep re-plans the NBA, because an active case must never lack one.

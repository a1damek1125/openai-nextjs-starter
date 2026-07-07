# Finalis AI — Data Model

> Design principles: (1) **Everything is evidence-linked** — any AI assertion traces to a
> `Message`, `Call` segment, `ExtractedField`, or web `Source`. (2) **Event-sourced core** —
> the case's truth is an append-only `AuditEvent` log; derived tables are projections that can
> be rebuilt. (3) **Relational + graph + vector**, not one or the other (see rationale in
> `18-technology-stack.md`). (4) **Privacy by default** — PII columns are tagged, encrypted at rest,
> and carry retention policies.

Storage strategy (justified in the tech-stack doc):
- **PostgreSQL** is the system of record for all entities below (strong consistency, easy
  audit, transactions).
- **Case Graph** relationships are modeled as first-class `graph_edges` rows in Postgres for
  the MVP (adjacency + typed edges), with an optional migration path to Neo4j if traversal
  depth/complexity demands it. Postgres recursive CTEs cover MVP traversals.
- **pgvector** columns/tables provide semantic search over messages, documents, and past
  cases (Deal Memory).

Notation: `PK` primary key, `FK` foreign key, `→` relation. All tables have `id (uuid)`,
`tenant_id (uuid, FK BusinessProfile)`, `created_at`, `updated_at` unless noted. **Every**
table is tenant-scoped and every query is tenant-filtered (row-level security).

---

## Core entities

### `Case`
- **Purpose**: the living case file; the unit the Completion Loop drives.
- **Fields**: `status (enum, see 03)`, `industry_type`, `playbook_id (FK)`, `owner_id (FK
  UserRole)`, `goal (text)`, `source_channel`, `value_estimate (numeric)`,
  `value_currency`, `lead_score`, `risk_score`, `mis_score`, `stuck_score`,
  `escalation_score`, `next_best_action (jsonb)`, `next_action_due_at`, `autonomy_level (1–5)`,
  `primary_party_id (FK Party)`, `closed_reason`, `closed_at`, `wake_at (for RECOVERY_LATER)`,
  `linked_case_id (FK Case, nullable)`.
- **Relations**: → many `Conversation`, `Call`, `Document`, `Photo`, `Offer`, `Promise`,
  `MissingItem`, `Action`, `Task`, `DecisionBrief`, `RiskFlag`, `HumanApproval`. → one
  `IndustryPlaybook`, one owner.
- **Indexes**: `(tenant_id, status)`, `(tenant_id, next_action_due_at)`,
  `(tenant_id, owner_id)`, `(tenant_id, lead_score desc)`, `(tenant_id, wake_at)`.
- **Retention/privacy**: retained per tenant policy (default: active + 24 months post-close);
  contains no raw PII beyond FKs (PII lives in `Party`).

### `Party`
- **Purpose**: any actor in a case — client, the business, technician, supplier, notary,
  lawyer, insurer. A case has many parties via `CasePartyRole`.
- **Fields**: `type (enum: client|company|technician|supplier|notary|lawyer|insurer|other)`,
  `display_name`, `phones (jsonb, E.164)`, `emails (jsonb)`, `whatsapp_id`, `preferred_channel`,
  `preferred_language`, `quiet_hours (jsonb)`, `contact_opt_outs (jsonb)`,
  `deal_memory_embedding (vector)`, `notes`.
- **Relations**: → many `Case` (through `CasePartyRole{case_id, party_id, role}`), → many
  `Message`/`Call`.
- **Indexes**: `(tenant_id, phone)`, `(tenant_id, email)`, vector index on
  `deal_memory_embedding`.
- **Retention/privacy**: **PII-heavy** — encrypted at rest, subject to GDPR erasure; opt-out
  flags are permanent (surviving erasure as a suppression hash). See `16-risks-and-mitigations.md`.

### `Conversation`
- **Purpose**: a channel-bound thread (one WhatsApp thread, one email thread, one chat
  session). Groups `Message`s.
- **Fields**: `channel (enum)`, `party_id (FK)`, `status (open|closed)`, `summary`, `intent`,
  `sentiment`, `language`, `last_inbound_at`, `last_outbound_at`.
- **Relations**: → `Case`, → `Party`, → many `Message`.
- **Indexes**: `(tenant_id, case_id)`, `(tenant_id, channel, party_id)`.
- **Retention/privacy**: transcripts may contain PII; retention follows `Case`.

### `Message`
- **Purpose**: a single inbound/outbound text-channel message (WhatsApp/SMS/email/chat).
- **Fields**: `conversation_id (FK)`, `direction (in|out)`, `channel`, `body (text)`,
  `attachments (jsonb → Document/Photo ids)`, `sent_by (ai|human|client)`, `provider_msg_id`,
  `delivery_status`, `embedding (vector)`, `detected_promises (jsonb)`,
  `detected_missing (jsonb)`, `sentiment`.
- **Relations**: → `Conversation`. Source for `Promise`, `MissingItem`, `EvidenceReference`.
- **Indexes**: `(tenant_id, conversation_id, created_at)`, vector index on `embedding`.
- **Retention/privacy**: PII; encrypted; retention follows `Case`.

### `Call`
- **Purpose**: a voice call (inbound/outbound), its recording, transcript, and derived items.
- **Fields**: `party_id (FK)`, `direction`, `provider_call_id`, `recording_url`,
  `duration_ms`, `transcript (jsonb: timestamped diarized segments)`, `summary`,
  `language(s)`, `sentiment_timeline (jsonb)`, `barge_in_events (jsonb)`,
  `latency_metrics (jsonb: ttfa_p50, p95)`, `handoff_to_human (bool)`,
  `detected_promises (jsonb)`, `detected_missing (jsonb)`, `next_actions (jsonb)`.
- **Relations**: → `Case`, → `Party`; segments referenced by `EvidenceReference`.
- **Indexes**: `(tenant_id, case_id, created_at)`, `(tenant_id, party_id)`.
- **Retention/privacy**: **recordings are sensitive** — consent-gated, region-configurable
  retention (default 90 days for audio, transcript retained with case); some jurisdictions
  require call-recording consent notices (config in `BusinessProfile`).

### `Document`
- **Purpose**: an uploaded/received file (PDF, scan, image-of-doc, offer, invoice, contract).
- **Fields**: `type (enum)`, `source (client|company|web|email)`, `storage_url (S3)`,
  `mime`, `pages`, `ocr_engine`, `ocr_text (text)`, `ocr_quality (0–1)`,
  `layout_json (jsonb: reading order, tables, regions)`, `doc_risk_score`,
  `overall_confidence (0–1)`, `status (received|processing|analyzed|needs_rescan)`,
  `language(s)`, `embedding (vector)`.
- **Relations**: → `Case`; → many `ExtractedField`, `EvidenceReference`, `RiskFlag`; may
  underlie an `Offer`.
- **Indexes**: `(tenant_id, case_id)`, `(tenant_id, type)`, vector index on `embedding`.
- **Retention/privacy**: may contain highly sensitive PII (IDs, contracts) — encrypted,
  access-logged, tenant-configurable retention; erasure removes the object + OCR text.

### `ExtractedField`
- **Purpose**: one structured field pulled from a `Document` (or `Message`), with confidence.
- **Fields**: `document_id (FK)`, `field_key`, `field_value (jsonb)`, `data_type`,
  `page`, `bbox (jsonb)`, `ocr_q`, `extraction_q`, `source_q`, `consistency_q`,
  `confidence (product, 0–1)`, `verified_by_human (bool)`.
- **Relations**: → `Document`; → `EvidenceReference` (self-describing evidence).
- **Indexes**: `(tenant_id, document_id, field_key)`.
- **Retention/privacy**: inherits document sensitivity.

### `EvidenceReference`
- **Purpose**: the universal citation object — links any AI claim to its source location.
- **Fields**: `claim_id (polymorphic: RiskFlag|DecisionBrief|Comparison|ExtractedField...)`,
  `source_type (message|call_segment|document_region|web_source)`, `source_id`,
  `locator (jsonb: page+bbox | call ts range | url+snippet)`, `snippet (text)`,
  `confidence`.
- **Relations**: many-to-one to whatever it substantiates; → `Document`/`Call`/`Message`/
  `Source`.
- **Indexes**: `(tenant_id, claim_id)`, `(tenant_id, source_type, source_id)`.
- **Retention/privacy**: snippet may contain PII; follows source retention.

### `Source`
- **Purpose**: a WebScout-recorded external source — the storage home for every web research
  fact (see `08-webscout-web-research.md` §5 output contract).
- **Fields**: `url`, `source_type (manufacturer|registry|gov|retailer|marketplace|forum|blog|pdf|other)`,
  `date_checked`, `title`, `snippet (text)`, `trust_score (0–100, see 05 §11)`,
  `relevance (0–1)`, `confidence (0–1)`, `extracted_facts (jsonb)`, `case_id (FK, nullable)`.
- **Relations**: → `Case`; referenced by `EvidenceReference.source_id` when
  `source_type=web_source`; feeds `Source_q` in Evidence Confidence (`05` §6).
- **Indexes**: `(tenant_id, case_id)`, `(tenant_id, url)`.
- **Retention/privacy**: public-web content, low sensitivity; snippet retained with case;
  respect deletion of case-linked rows on erasure.

### `Photo`
- **Purpose**: a client/site photo (job site, appliance nameplate, damage) — a specialization
  of media used by intake & quoting.
- **Fields**: `storage_url`, `source_channel`, `vision_tags (jsonb)`, `ocr_text (nullable)`,
  `quality (0–1)`, `linked_missing_item_id (nullable)`, `embedding (vector)`.
- **Relations**: → `Case`; may satisfy a `MissingItem`.
- **Indexes**: `(tenant_id, case_id)`.
- **Retention/privacy**: images may reveal home/PII; encrypted; retention follows case.

### `Offer`
- **Purpose**: a commercial offer/quote — ours or a competitor's (client-provided).
- **Fields**: `origin (ours|competitor|client_provided)`, `document_id (nullable FK)`,
  `price (numeric)`, `currency`, `scope (jsonb)`, `deadline`, `warranty (jsonb)`,
  `payment_terms (jsonb)`, `exclusions (jsonb)`, `hidden_costs (jsonb)`, `offer_score`,
  `sent_at`, `status (draft|sent|accepted|rejected|expired)`, `version`.
- **Relations**: → `Case`; participates in `Comparison`; may be backed by a `Document`.
- **Indexes**: `(tenant_id, case_id)`, `(tenant_id, status)`.
- **Retention/privacy**: business-confidential; follows case.

### `Comparison`
- **Purpose**: a stored offer-comparison result (table + scores + recommendation).
- **Fields**: `offer_ids (jsonb)`, `weights_version`, `axis_scores (jsonb)`,
  `recommendation (text)`, `hidden_risk_flags (jsonb → EvidenceReference)`, `confidence`.
- **Relations**: → `Case`; → many `Offer`; → `EvidenceReference`.
- **Indexes**: `(tenant_id, case_id)`.

### `Promise`
- **Purpose**: a commitment by any party; the Promise Tracker's unit.
- **Fields**: `promisor_party_id (FK)`, `promisee_party_id (FK, nullable)`,
  `what (text)`, `due_at`, `importance (0–1)`, `dependency_impact (0–1)`, `status
  (open|fulfilled|broken|waived)`, `breach_score`, `evidence_ref_id (FK)`, `source_type`.
- **Relations**: → `Case`, → `Party` (×2), → `EvidenceReference`.
- **Indexes**: `(tenant_id, status, due_at)`, `(tenant_id, case_id)`.
- **Retention/privacy**: follows case.

### `MissingItem`
- **Purpose**: a piece of information/document blocking progress; Missing-Info Hunter's unit.
- **Fields**: `field_key`, `label`, `weight (w_i)`, `blocks_quote (bool)`,
  `status (missing|requested|received|waived)`, `requested_at`, `channel_used`,
  `satisfied_by (Document/Photo/Message id)`, `example_hint`.
- **Relations**: → `Case`; may be satisfied by `Document`/`Photo`/`Message`.
- **Indexes**: `(tenant_id, case_id, status)`.

### `Action`
- **Purpose**: an executed or scheduled system/human action (call, message, doc-request,
  escalate, schedule). The audit-facing record of "what the worker did".
- **Fields**: `type (enum)`, `channel`, `autonomy_level_used`, `scheduled_at`, `executed_at`,
  `result (jsonb)`, `utility_score`, `chosen_over (jsonb: runner-up actions)`,
  `approved_by (FK UserRole, nullable)`, `next_action (jsonb)`, `status`.
- **Relations**: → `Case`; → `HumanApproval` (if gated); produces `Message`/`Call`.
- **Indexes**: `(tenant_id, case_id, executed_at)`, `(tenant_id, scheduled_at, status)`.
- **Retention/privacy**: audit — long retention.

### `Task`
- **Purpose**: a unit of human work surfaced in the Command Center ("call this client",
  "approve this quote").
- **Fields**: `title`, `assignee_id (FK UserRole)`, `priority`, `due_at`, `status
  (open|in_progress|done|snoozed)`, `origin (ai|human)`, `related_action_id (nullable)`.
- **Relations**: → `Case`, → `UserRole`.
- **Indexes**: `(tenant_id, assignee_id, status)`, `(tenant_id, due_at)`.

### `FollowUpSequence`
- **Purpose**: the templated, tenant-tunable cadence a case follows while awaiting a client.
- **Fields**: `name`, `steps (jsonb: [{offset, channel, template_id, condition}])`,
  `quiet_hours`, `max_attempts`, `min_interval`, `active_step_index`, `state (running|paused|
  exhausted)`.
- **Relations**: → `Case`; references message `templates`.
- **Indexes**: `(tenant_id, case_id)`.

### `DecisionBrief`
- **Purpose**: the short owner-facing recommendation ("call today after 16:00, offer premium").
- **Fields**: `summary (text)`, `value_range (jsonb)`, `situation`, `recommended_step`,
  `rationale`, `risk_note`, `confidence`, `evidence_ref_ids (jsonb)`, `generated_by_model`,
  `superseded (bool)`.
- **Relations**: → `Case`; → `EvidenceReference`.
- **Indexes**: `(tenant_id, case_id, created_at)`.

### `RiskFlag`
- **Purpose**: a specific risk detected on a document/offer/case, always evidence-linked.
- **Fields**: `category (asymmetry|missing_element|contradiction|payment|clause|quality|legal)`,
  `severity (0–1)`, `description`, `evidence_ref_id (FK)`, `requires_human (bool)`,
  `status (open|acknowledged|resolved)`.
- **Relations**: → `Case`/`Document`/`Offer`; → `EvidenceReference`.
- **Indexes**: `(tenant_id, case_id, severity desc)`.

### `HumanApproval`
- **Purpose**: a gated decision the AI prepared but a human must authorize (HITL).
- **Fields**: `action_id (FK)`, `requested_at`, `context (jsonb)`, `options (jsonb)`,
  `recommended_option`, `decided_by (FK UserRole, nullable)`, `decision`, `decided_at`,
  `deadline`, `sla_breached (bool)`.
- **Relations**: → `Case`, → `Action`, → `UserRole`.
- **Indexes**: `(tenant_id, decided_at is null, deadline)`.
- **Retention/privacy**: audit — long retention.

### `AuditEvent`
- **Purpose**: append-only event log = source of truth. Every state transition, score
  computation, action, approval, and data change writes one.
- **Fields**: `event_type`, `case_id (nullable)`, `actor (ai_worker|human|system)`,
  `actor_id`, `from_state`, `to_state`, `payload (jsonb: inputs, scores, weight_version)`,
  `evidence_ref_ids (jsonb)`, `hash_prev (tamper-evidence chain)`.
- **Relations**: → anything (polymorphic `case_id`/`entity_ref`).
- **Indexes**: `(tenant_id, case_id, created_at)`, `(tenant_id, event_type)`.
- **Retention/privacy**: **immutable**, long retention; the compliance backbone. Never
  edited; PII minimized (store references, not raw PII, where possible).

### Metering

### `CostEvent`
- **Purpose**: per-call metering record for every LLM/STT/TTS/OCR/telephony/message unit
  consumed.
- **Fields**: `case_id (nullable)`, `worker`, `provider`,
  `unit_type (tokens|minutes|pages|messages|requests)`, `quantity`,
  `unit_cost_ref (FK CostRateCard)`, `computed_cost`, `currency`.
- **Indexes**: `(tenant_id, created_at)`, `(tenant_id, case_id)`.
- **Retention/privacy**: financial/audit — long.

### `CostRateCard`
- **Purpose**: versioned vendor rate table used to price `CostEvent`s.
- **Fields**: `provider`, `unit_type`, `rate`, `currency`, `valid_from`, `valid_to`.
- **Indexes**: `(provider, unit_type, valid_from)`.

### `IntegrationAccount`
- **Purpose**: a connected external system (Google Calendar, Gmail/Outlook, WhatsApp Business,
  SMS provider, telephony, CRM, Drive).
- **Fields**: `provider`, `scopes (jsonb)`, `credentials_ref (secret store handle, NOT the
  secret)`, `status`, `connected_by (FK UserRole)`, `webhook_config (jsonb)`.
- **Relations**: → `BusinessProfile`.
- **Indexes**: `(tenant_id, provider)`.
- **Retention/privacy**: **secrets never in DB** — only a handle to a secrets manager; tokens
  encrypted; least-privilege scopes.

### `BusinessProfile` (tenant)
- **Purpose**: the customer business; the tenant root.
- **Fields**: `name`, `services (jsonb)`, `service_area (jsonb)`, `default_language`,
  `timezone`, `quiet_hours`, `price_rules (jsonb)`, `high_value_threshold`,
  `thresholds (jsonb: θ_qualify, θ_escalate, θ_docrisk, θ_conf, θ_mis, θ_stuck, θ_breach)`,
  `autonomy_defaults (jsonb per action type)`, `recording_consent_config (jsonb)`,
  `data_region`.
- **Relations**: → many everything (tenant root); → many `UserRole`, `IntegrationAccount`,
  `IndustryPlaybook`, `VoiceProfile`.
- **Indexes**: `PK id`.
- **Retention/privacy**: tenant config; drives all privacy/retention behavior.

### `IndustryPlaybook`
- **Purpose**: vertical-specific config: intake questions, required fields + weights, scoring
  weight overrides, offer-comparison weights, state-machine timings, escalation rules.
- **Fields**: `vertical (hvac|plumbing|electrical|renovation|auto|property|...)`,
  `intake_schema (jsonb)`, `required_fields (jsonb: [{key, weight, blocks_quote}])`,
  `scoring_weights (jsonb)`, `offer_weights (jsonb)`, `followup_defaults (jsonb)`,
  `escalation_rules (jsonb)`, `templates (jsonb)`, `version`.
- **Relations**: → `BusinessProfile`; referenced by `Case`.
- **Indexes**: `(tenant_id, vertical)`.
- **Retention/privacy**: config, non-PII.

### `VoiceProfile`
- **Purpose**: voice/telephony configuration per tenant/number.
- **Fields**: `phone_numbers (jsonb)`, `tts_voice`, `stt_vendor`, `languages`,
  `greeting_script`, `barge_in_enabled`, `max_latency_targets (jsonb)`,
  `handoff_rules (jsonb)`, `recording_enabled`, `consent_prompt`.
- **Relations**: → `BusinessProfile`; used by `Call`.
- **Indexes**: `(tenant_id, phone_number)`.

### `UserRole`
- **Purpose**: a human user of the Command Center + their permissions.
- **Fields**: `user_id (FK auth)`, `role (owner|manager|agent|technician|read_only)`,
  `permissions (jsonb)`, `assignable (bool)`, `notify_channels (jsonb)`.
- **Relations**: → `BusinessProfile`; owns `Case`/`Task`; decides `HumanApproval`.
- **Indexes**: `(tenant_id, role)`.
- **Retention/privacy**: user PII; standard auth handling.

---

## Case Graph edges (`graph_edges`)

A typed edge table realizes the "case is a graph" requirement without a separate graph DB at
MVP:

- **Fields**: `from_node (polymorphic ref)`, `to_node (polymorphic ref)`, `edge_type`,
  `weight`, `created_at`, `evidence_ref_id (nullable)`.
- **Edge types (examples)**: `CLIENT_SENT_DOCUMENT`, `DOCUMENT_SATISFIES_MISSING_ITEM`,
  `OFFER_CONTRADICTS_AGREEMENT`, `MISSING_PHOTO_BLOCKS_QUOTE`, `PROMISE_DUE`,
  `CASE_REQUIRES_HUMAN_APPROVAL`, `CALL_CONTAINS_PROMISE`, `FOLLOWUP_TARGETS_OFFER`,
  `RISK_FLAG_ON_DOCUMENT`.
- **Indexes**: `(tenant_id, from_node)`, `(tenant_id, to_node)`, `(tenant_id, edge_type)`.
- **Traversal**: recursive CTEs for MVP ("what blocks this quote?", "which promises are
  overdue and block a close?"). Migration trigger to Neo4j: if typical queries exceed 3–4 hop
  traversals across >10⁵ edges per case set with latency issues (see `18-technology-stack.md`).

---

## Retention & privacy summary

| Class | Examples | Default retention | Notes |
|---|---|---|---|
| Immutable audit | `AuditEvent`, `HumanApproval`, `Action` | Long (e.g. 7y config) | Tamper-evident; references not raw PII |
| PII / sensitive media | `Party`, `Message`, `Call` recordings, `Document`, `Photo` | Case + 12–24 mo; audio 90d default | Encrypted at rest; GDPR erasure supported; opt-out suppression survives erasure |
| Business config | `BusinessProfile`, `IndustryPlaybook`, `VoiceProfile` | Life of tenant | Non-PII |
| Secrets | `IntegrationAccount` tokens | External secret store | Never stored in DB |

All PII access is logged (`AuditEvent`); data region is tenant-configurable
(`BusinessProfile.data_region`); erasure and export (DSAR) are first-class operations. See
`16-risks-and-mitigations.md` for the full privacy/compliance posture.

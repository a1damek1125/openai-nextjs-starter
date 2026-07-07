# Finalis AI — Data Model & API Verification (Audit)

> **STATUS: DOCUMENTED / ARCHITECTURE SPECIFIED — NOT IMPLEMENTED.**
> The schema in `04-data-model.md` and the API/event contract in `22-api-and-event-model.md`
> are **design documents only**. This repository contains **zero DDL** (no migrations, no
> SQL, no ORM models), **zero API endpoints**, and no database. Every ✓ below means
> "specified well enough to implement", never "exists in code".
>
> Companion artifact: `openapi.finalis.yaml` (OpenAPI 3.1 **skeleton**, equally a design
> artifact — no server implements it).

Audited inputs: `04-data-model.md` (all entities), `22-api-and-event-model.md` (all
endpoints + event catalog), `03-case-lifecycle-state-machine.md` (17-state enum).

---

## 1. Implementability audit — entity by entity

Legend: **P** purpose stated · **F** fields complete · **R** relations resolvable ·
**I** indexes sensible · **PR** privacy/retention stated · **A** audit requirements stated.
✓ = adequate to implement, ~ = implementable with a stated correction, ✗ = missing.

| Entity | P | F | R | I | PR | A | Notes / corrections |
|---|---|---|---|---|---|---|---|
| `Case` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 17-state enum defined in doc 03 and matches `status`. `linked_case_id` self-FK fine. All score fields present. |
| `Party` | ✓ | ~ | ✓ | ~ | ✓ | ✓ | **Correction:** `phones`/`emails` are `jsonb` arrays, but indexes are declared as `(tenant_id, phone)` / `(tenant_id, email)` — not directly implementable. Needs generated columns (`primary_phone`, `primary_email`), a `party_contact_points` side table, or GIN indexes. Suppression-hash-survives-erasure mechanism is stated but the hash column itself is not in the field list. |
| `CasePartyRole` | ✓ | ~ | ✓ | ✗ | ✗ | ✗ | Defined only inline (`{case_id, party_id, role}`). Implementable, but deserves its own section: needs PK/uniqueness `(case_id, party_id, role)`, indexes both directions, and retention note (follows Case). Low severity. |
| `Conversation` | ✓ | ~ | ✓ | ✓ | ✓ | ~ | Field list omits `case_id` although relations and the `(tenant_id, case_id)` index require it. Doc-consistency nit; same pattern in several entities (implied by "→ Case" relation). |
| `Message` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Vector + promise/missing detection fields all present. Attachments as jsonb id list is fine for MVP. |
| `Call` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Consent gating and 90-day audio retention stated. Segment-level evidence works via `EvidenceReference.locator` ts-range — see §2 (VoiceTranscript). |
| `Document` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Full OCR/layout/confidence/status lifecycle. Erasure removes object + OCR text — stated. |
| `ExtractedField` | ✓ | ✓ | ✓ | ✓ | ✓ | ~ | Carries the full confidence decomposition (`ocr_q`, `extraction_q`, `source_q`, `consistency_q`) — see §2 (OCRConfidence). `verified_by_human` changes should be explicitly required to write an `AuditEvent` (doc 22 says "audited" — align doc 04). |
| `EvidenceReference` | ✓ | ~ | ✓ | ✓ | ✓ | ✓ | **Correction:** polymorphic `claim_id` needs a companion `claim_type` column (the doc lists possible claim kinds but no discriminator field). Same for the `source_*` pair, which *does* have `source_type` — mirror that. |
| `Source` | ✓ | ✓ | ✓ | ✓ | ✓ | ~ | Exists and matches WebScout output contract (doc 08 §5). `trust_score` 0–100 vs other confidences 0–1 — inconsistent scale, keep but document. |
| `Photo` | ✓ | ~ | ✓ | ✓ | ✓ | ~ | Missing `case_id` in field list (implied). `linked_missing_item_id` gives the satisfaction link. |
| `Offer` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Versioned; competitor offers handled via `origin` + backing `Document`. |
| `Comparison` | ✓ | ✓ | ✓ | ✓ | ~ | ~ | Retention/audit not explicitly stated; inherits Case in practice — should be written down. `offer_ids` jsonb array is acceptable MVP denormalization. |
| `Promise` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Evidence-linked by design (`evidence_ref_id`). Breach detection is sweep-driven (doc 22 event model), consistent. |
| `MissingItem` | ✓ | ✓ | ✓ | ✓ | ~ | ~ | `satisfied_by` is polymorphic (Document/Photo/Message id) — needs a type discriminator column, same correction as EvidenceReference. |
| `Action` | ✓ | ~ | ✓ | ✓ | ✓ | ✓ | **Correction:** no `payload` field, yet `GET /approvals` (doc 22) returns `action: {type, payload}` and `action.proposed` events carry `payload`. Add `payload (jsonb)` for the prepared/draft content. Also see §2 (FollowUpAttempt): add `attempt_index`. |
| `Task` | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | Retention/privacy and audit posture not stated — Low severity, follows Case/tenant defaults. |
| `FollowUpSequence` | ✓ | ~ | ✓ | ✓ | ✗ | ~ | `case_id` implied not listed; `template_id` references a `templates` store that exists only inside `IndustryPlaybook.templates (jsonb)` — resolvable but weakly typed. Individual attempts are not modeled — see §2 (FollowUpAttempt). |
| `DecisionBrief` | ✓ | ✓ | ✓ | ✓ | ~ | ✓ | `superseded` flag + `generated_by_model` good for reproducibility. Retention unstated (follows Case). |
| `RiskFlag` | ✓ | ✓ | ✓ | ✓ | ~ | ✓ | Polymorphic parent (Case/Document/Offer) needs discriminator columns. Evidence-linked. |
| `HumanApproval` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | The HITL backbone; partial index `(tenant_id, decided_at is null, deadline)` is exactly right for the pending queue. Long retention stated. |
| `AuditEvent` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Append-only, hash-chained (`hash_prev`), PII-minimized. **Correction (minor):** chain needs the row's *own* hash (or the chain must be defined as hash-over-canonical-payload); add `hash_self` or specify the derivation. |
| `CostEvent` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Metering per unit type with FK to rate card. **No API endpoint exposes it** — see §4. |
| `CostRateCard` | ✓ | ✓ | ✓ | ✓ | ~ | ~ | Global (not tenant-scoped?) — index `(provider, unit_type, valid_from)` lacks `tenant_id`, implying a shared table; state that explicitly. Validity-window overlap constraint should be specified. |
| `IntegrationAccount` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Secrets-by-reference (`credentials_ref`) — correct design, secrets never in DB. Serves the "IntegrationCredential" requirement — see §2. |
| `BusinessProfile` | ✓ | ✓ | ✓ | ✓ | ✓ | ~ | Tenant root; thresholds + autonomy defaults + data region all present. Threshold changes audited per doc 22 — align doc 04 wording. |
| `IndustryPlaybook` | ✓ | ~ | ✓ | ✓ | ✓ | ~ | Has `version` but **no version-history table**, while doc 22 `PATCH /playbooks/{id}` promises "immutable history" and scores persist `weights_version` for reproducibility. Contradiction — see §2 (PlaybookVersion). |
| `VoiceProfile` | ✓ | ✓ | ✓ | ✓ | ~ | ~ | Consent prompt + recording toggle present; changes audited per doc 22. |
| `UserRole` | ✓ | ✓ | ✓ | ✓ | ✓ | ~ | FK to external auth (`user_id`) fine. |
| `graph_edges` | ✓ | ~ | ✓ | ✓ | ✗ | ~ | Polymorphic `from_node`/`to_node` need `(node_type, node_id)` pairs — implied, not written. Retention unstated (should follow the case the edge belongs to; edges also lack an explicit `case_id`, which would make per-case traversal and erasure much cheaper — recommended addition). Recursive-CTE MVP + Neo4j migration trigger are sensibly specified. |

**Cross-cutting verdict:** the model is implementable as specified. The recurring defects are
(a) polymorphic references without a type discriminator column, (b) fields implied by
relations/indexes but absent from field lists (`case_id`), and (c) jsonb-array fields with
scalar-style index declarations (`Party.phones`).

---

## 2. Required-entity check (honest report)

| Required concept | Verdict | Detail & recommendation |
|---|---|---|
| `Source` | **EXISTS** in doc 04 | Full WebScout storage entity with trust/relevance/confidence and `extracted_facts`. |
| `EvidenceReference` | **EXISTS** | Universal citation object; needs `claim_type` discriminator (see §1). |
| `OCRConfidence` | **NOT a separate entity — and shouldn't be** | The confidence decomposition lives as fields: `ExtractedField.ocr_q/extraction_q/source_q/consistency_q/confidence` and `Document.ocr_quality/overall_confidence`. This is **sufficient**: confidence is an attribute of an extraction, not an independent noun; a separate table would add a join on every evidence lookup for zero modeling gain. **Recommendation: keep as fields, no new entity.** |
| `VoiceTranscript` | **Lives on `Call.transcript (jsonb)`** — adequate for MVP | Diarized timestamped segments in jsonb; `EvidenceReference.locator` addresses segments by ts-range, so segment-level citation works today. Weakness: segments are not individually indexable/queryable (e.g., "all segments where a promise was made", per-segment embeddings). **Recommendation: add a `CallSegment` projection table (rebuildable from `Call.transcript`, consistent with the event-sourced projection principle) as Phase 2. No schema change needed for MVP.** |
| `CallMetric` | **Lives in `Call.latency_metrics (jsonb)`** — sufficient for MVP | ttfa_p50/p95 per call is enough for the per-call record. **Note:** the Evaluation Lab (`GET /metrics`, doc 15) needs an aggregated metrics store (time-series/rollup) that no entity in doc 04 provides — flag as a gap for the metrics pipeline (can be a projection/rollup table, Phase 2). |
| `FollowUpAttempt` | **MISSING as an explicit entity — GAP** | `FollowUpSequence` holds `steps` + `active_step_index`; individual attempts exist only as `Action` rows produced when a step executes (`followup.sent{sequence_id, step_index}` event). There is no queryable per-attempt record linking sequence → step → action → outcome. **Recommendation: add `attempt_index` (and `sequence_id`) to `Action`, or define a `follow_up_attempts` DB view over Actions joined to sequence events. Flagged as a gap (Medium).** |
| `LGGTCertificate` | **MISSING — Phase 2 placeholder** | Referenced as a placeholder defined in doc 32; **note: no `32-*.md` exists in this repo** (docs run 00–23 + README + this file), so the placeholder itself is unwritten. Not required for MVP; carry as an explicit Phase-2 backlog item and create the doc when scoped. |
| `HumanApproval` | **EXISTS** | Complete, with SLA and pending-queue index. |
| `IntegrationCredential` | **EXISTS as `IntegrationAccount`** | Correctly modeled with secrets-by-reference (`credentials_ref` → external secret store, never the secret). No separate credential entity needed. |
| `PlaybookVersion` | **PARTIAL — GAP** | `IndustryPlaybook.version` is a scalar; there is no version-history table, yet doc 22 promises immutable history on `PATCH /playbooks/{id}` and score reproducibility depends on resolving `weights_version` → the exact weights used. **Recommendation: add an append-only `PlaybookVersion` table (`playbook_id, version, snapshot jsonb, created_by, created_at`, unique `(playbook_id, version)`), written on every playbook mutation. Flagged as a gap (High — reproducibility/audit promise currently unbacked by schema).** |
| `AuditEvent` | **EXISTS** | Append-only, hash-chained, long retention. |

---

## 3. Example objects (HVAC scenario: boiler replacement for a homeowner)

### Case
```json
{
  "id": "c7a1e2f0-4b3d-4c8e-9a51-2f6d8e901a11",
  "tenant_id": "t0b9...",
  "status": "QUOTE_PREPARATION",
  "industry_type": "hvac",
  "playbook_id": "pb-hvac-001",
  "owner_id": "ur-owner-01",
  "goal": "Replace failed 24kW gas combi boiler at Lindenstraße 12, quote and book install",
  "source_channel": "whatsapp",
  "value_estimate": 3800.00,
  "value_currency": "EUR",
  "lead_score": 0.82, "risk_score": 0.21, "mis_score": 0.08,
  "stuck_score": 0.05, "escalation_score": 0.14,
  "next_best_action": { "type": "send_message", "channel": "whatsapp", "template_id": "quote_eta_ack" },
  "next_action_due_at": "2026-07-07T16:00:00Z",
  "autonomy_level": 3,
  "primary_party_id": "p-4d2c...",
  "closed_reason": null, "closed_at": null, "wake_at": null, "linked_case_id": null
}
```

### Party
```json
{
  "id": "p-4d2c9e7a-88b1-4f0e-b2d3-6a5c4e3f2b10",
  "tenant_id": "t0b9...",
  "type": "client",
  "display_name": "Marta Kowalczyk",
  "phones": ["+4915123456789"],
  "emails": ["marta.k@example.com"],
  "whatsapp_id": "4915123456789",
  "preferred_channel": "whatsapp",
  "preferred_language": "de",
  "quiet_hours": { "start": "20:00", "end": "08:00", "tz": "Europe/Berlin" },
  "contact_opt_outs": [],
  "notes": "Boiler is in the basement; prefers afternoon appointments."
}
```

### Promise
```json
{
  "id": "pr-91c0aa32-1f7e-4b6d-8c2a-0e9d7f6a5b43",
  "tenant_id": "t0b9...",
  "case_id": "c7a1e2f0-4b3d-4c8e-9a51-2f6d8e901a11",
  "promisor_party_id": "p-4d2c...",
  "promisee_party_id": null,
  "what": "Client will send a photo of the boiler nameplate",
  "due_at": "2026-07-06T18:00:00Z",
  "importance": 0.8,
  "dependency_impact": 0.9,
  "status": "fulfilled",
  "breach_score": 0.0,
  "evidence_ref_id": "ev-33f1...",
  "source_type": "message"
}
```

### MissingItem
```json
{
  "id": "mi-5b8e2d10-7c4f-4a9b-9e01-3d2c1b0a9f88",
  "tenant_id": "t0b9...",
  "case_id": "c7a1e2f0-...",
  "field_key": "boiler_nameplate_photo",
  "label": "Photo of the boiler nameplate (model & serial)",
  "weight": 0.35,
  "blocks_quote": true,
  "status": "received",
  "requested_at": "2026-07-05T14:12:00Z",
  "channel_used": "whatsapp",
  "satisfied_by": { "type": "photo", "id": "ph-77aa..." },
  "example_hint": "Metal plate on the boiler side, includes model like 'Vaillant ecoTEC plus VC 246'"
}
```

### Document
```json
{
  "id": "doc-a1b2c3d4-e5f6-4789-a012-b3c4d5e6f708",
  "tenant_id": "t0b9...",
  "case_id": "c7a1e2f0-...",
  "type": "competitor_offer",
  "source": "client",
  "storage_url": "s3://finalis-t0b9/docs/doc-a1b2....pdf",
  "mime": "application/pdf",
  "pages": 2,
  "ocr_engine": "textract-v3",
  "ocr_quality": 0.94,
  "doc_risk_score": 0.58,
  "overall_confidence": 0.91,
  "status": "analyzed",
  "languages": ["de"]
}
```

### ExtractedField
```json
{
  "id": "ef-0f9e8d7c-6b5a-4433-9221-1a0b9c8d7e6f",
  "tenant_id": "t0b9...",
  "document_id": "doc-a1b2c3d4-...",
  "field_key": "offer_total_price",
  "field_value": { "amount": 4290.00, "currency": "EUR" },
  "data_type": "money",
  "page": 1,
  "bbox": { "x": 412, "y": 688, "w": 96, "h": 22 },
  "ocr_q": 0.97, "extraction_q": 0.95, "source_q": 0.90, "consistency_q": 0.99,
  "confidence": 0.82,
  "verified_by_human": false
}
```

### EvidenceReference
```json
{
  "id": "ev-33f1c2b4-9d8e-4f7a-8b60-5c4d3e2f1a09",
  "tenant_id": "t0b9...",
  "claim_id": "rf-66dd...",
  "source_type": "document_region",
  "source_id": "doc-a1b2c3d4-...",
  "locator": { "page": 2, "bbox": { "x": 55, "y": 910, "w": 480, "h": 40 } },
  "snippet": "Anfahrt, Entsorgung des Altgeräts und hydraulischer Abgleich werden nach Aufwand berechnet.",
  "confidence": 0.88
}
```

### Source
```json
{
  "id": "src-2e1d0c9b-8a7f-4655-b344-3c2b1a0f9e8d",
  "tenant_id": "t0b9...",
  "case_id": "c7a1e2f0-...",
  "url": "https://www.vaillant.de/heizung/produkte/ecotec-plus/",
  "source_type": "manufacturer",
  "date_checked": "2026-07-06",
  "title": "Vaillant ecoTEC plus — technical data",
  "snippet": "ecoTEC plus VC 246: 24 kW output, ErP class A, dimensions 720×440×338 mm",
  "trust_score": 92,
  "relevance": 0.95,
  "confidence": 0.9,
  "extracted_facts": { "model": "ecoTEC plus VC 246", "output_kw": 24, "erp_class": "A" }
}
```

### Offer
```json
{
  "id": "of-8c7b6a59-4d3e-4f21-a0b9-c8d7e6f5a4b3",
  "tenant_id": "t0b9...",
  "case_id": "c7a1e2f0-...",
  "origin": "ours",
  "document_id": null,
  "price": 3790.00,
  "currency": "EUR",
  "scope": { "items": ["Vaillant ecoTEC plus VC 246", "installation", "old boiler disposal", "hydraulic balancing"] },
  "deadline": "2026-07-21",
  "warranty": { "manufacturer_years": 5, "labor_years": 2 },
  "payment_terms": { "deposit_pct": 30, "balance_on": "completion" },
  "exclusions": ["flue liner replacement"],
  "hidden_costs": [],
  "offer_score": 0.87,
  "status": "draft",
  "version": 1
}
```

### HumanApproval
```json
{
  "id": "ha-7f6e5d4c-3b2a-4190-8877-6655a4b3c2d1",
  "tenant_id": "t0b9...",
  "case_id": "c7a1e2f0-...",
  "action_id": "ac-11aa...",
  "requested_at": "2026-07-07T09:30:00Z",
  "context": { "reason": "Offer send requires Level 4; case runs at Level 3", "offer_id": "of-8c7b..." },
  "options": ["send_as_drafted", "send_with_5pct_discount", "hold"],
  "recommended_option": "send_as_drafted",
  "decided_by": null,
  "decision": null,
  "decided_at": null,
  "deadline": "2026-07-07T17:30:00Z",
  "sla_breached": false
}
```

### AuditEvent
```json
{
  "id": "ae-9a8b7c6d-5e4f-4321-b098-7654c3d2e1f0",
  "tenant_id": "t0b9...",
  "event_type": "case.state_changed",
  "case_id": "c7a1e2f0-...",
  "actor": "ai_worker",
  "actor_id": "orchestrator",
  "from_state": "WAITING_FOR_DOCUMENTS",
  "to_state": "DOCUMENT_ANALYSIS",
  "payload": { "reason": "blocking missing_item boiler_nameplate_photo satisfied", "mis_score": 0.08, "weights_version": "hvac-w7" },
  "evidence_ref_ids": ["ev-33f1..."],
  "hash_prev": "sha256:4f2a9c...",
  "created_at": "2026-07-06T17:44:02Z"
}
```

---

## 4. Gaps & required corrections

| # | Gap / correction | Where | Severity |
|---|---|---|---|
| 1 | **No `PlaybookVersion` history table** while API promises immutable version history and score reproducibility depends on `weights_version` resolution. Add append-only `PlaybookVersion`. | doc 04 `IndustryPlaybook` vs doc 22 §1.2 | **High** |
| 2 | **`FollowUpAttempt` not an explicit entity** — attempts are implicit `Action` rows; no queryable sequence→step→action→outcome link. Add `Action.sequence_id` + `Action.attempt_index` or a `follow_up_attempts` view. | doc 04 `FollowUpSequence`/`Action` | Medium |
| 3 | `Party.phones/emails` (jsonb arrays) declared with scalar indexes `(tenant_id, phone)` — needs generated columns, contact-point side table, or GIN indexes for the dedup lookups doc 22 requires (`409 duplicate_party`). | doc 04 `Party` | Medium |
| 4 | Polymorphic refs lack type discriminators: `EvidenceReference.claim_id` (no `claim_type`), `MissingItem.satisfied_by`, `graph_edges.from_node/to_node`, `RiskFlag` parent. Specify `(type, id)` pairs. | doc 04, multiple | Medium |
| 5 | `Action` lacks a `payload` field, but `GET /approvals` and `action.proposed`/`action.approved` events expose `action.payload`/`edited_payload`. Add `payload (jsonb)`. | doc 04 `Action` vs doc 22 | Medium |
| 6 | **`CostEvent`/`CostRateCard` have no API endpoints** — cost visibility (doc 23) has no read surface. Add read-only `GET /cost-events` (or `/metrics/costs`). | doc 22 | Medium |
| 7 | Evaluation Lab metrics (`GET /metrics`) has no backing store in the data model — per-call jsonb metrics exist but no aggregate/rollup entity. Define a metrics projection (Phase 2 acceptable, must be named). | doc 04 vs doc 22/15 | Medium |
| 8 | `AuditEvent` hash chain underspecified: `hash_prev` exists but the row's own hash/derivation is not defined — chain is unverifiable as written (`GET /audit-events/verify` needs it). Add `hash_self` or a canonical-hash spec. | doc 04 `AuditEvent` | Medium |
| 9 | `graph_edges` lacks `case_id` — per-case traversal (`?include=graph`) and GDPR erasure of case-linked edges require scans. Add denormalized `case_id`. | doc 04 `graph_edges` | Low–Medium |
| 10 | `case_id` omitted from several field lists though required by relations/indexes (`Conversation`, `Photo`, `FollowUpSequence`, `Offer`, ...). Doc consistency fix. | doc 04 | Low |
| 11 | `CasePartyRole` needs a real definition: PK/uniqueness, indexes, retention. API also lacks list/detach routes (attach only). | doc 04 / doc 22 | Low |
| 12 | `Task`, `Comparison`, `DecisionBrief`, `graph_edges`: retention/privacy not stated. Default "follows Case" should be written. | doc 04 | Low |
| 13 | `LGGTCertificate` placeholder: referenced as doc 32, but **doc 32 does not exist in the repo**. Create the placeholder doc or drop the reference. Phase 2. | docs index | Low |
| 14 | `CostRateCard` tenancy ambiguous (index lacks `tenant_id` — presumably global/shared); validity-window overlap constraint unspecified. | doc 04 | Low |
| 15 | `VoiceTranscript`/`CallSegment`: jsonb transcript sufficient for MVP; add rebuildable `CallSegment` projection in Phase 2 for segment-level indexing/embeddings. | doc 04 `Call` | Low (Phase 2) |
| 16 | `OCRConfidence`: intentionally **not** an entity — confirmed correct; keep `ocr_q` etc. as `ExtractedField`/`Document` fields. No action. | — | None |

---

## 5. API endpoint coverage vs doc 22 (entity → endpoint check)

| Entity | Endpoints in doc 22 | Coverage |
|---|---|---|
| Case | `GET/POST /cases`, `GET/PATCH /cases/{id}`, `POST /cases/{id}/transitions`, `GET /cases/{id}/next-action` (+recompute) | ✓ Full |
| Party | `GET/POST /parties`, `PATCH /parties/{id}`, `POST /parties/{id}/erasure` | ✓ Full (incl. DSAR) |
| CasePartyRole | `POST /cases/{id}/parties` (attach) | **Partial — no list or detach route** |
| Conversation | `GET /cases/{id}/conversations` | Partial — no `GET /conversations/{id}` (minor; messages route exists) |
| Message | `GET/POST /conversations/{id}/messages` (autonomy-gated 202/403) | ✓ Full |
| Call | `POST /calls`, `GET /calls/{id}`, `/transcript`, `GET /cases/{id}/calls`, telephony webhook | ✓ Full |
| Document | upload, `GET /documents/{id}`, `/analysis`, `POST /rescan` | ✓ Full |
| Photo | `GET /photos/{id}` (upload via documents route, `kind=photo`) | ✓ Adequate |
| ExtractedField | `PATCH /extracted-fields/{id}`; read via `/analysis` | ✓ Adequate |
| EvidenceReference | `GET /evidence-refs/{id}` | ✓ Adequate (read-only by design) |
| Source | `GET /sources/{id}` | Partial — no per-case list (`GET /cases/{id}/sources` recommended) |
| Offer | list/create per case, `POST /offers/{id}/send` (high-gate) | ✓ Full |
| Comparison | `POST /cases/{id}/comparisons`, `GET /comparisons/{id}` | ✓ Full |
| Promise | list/create per case, `PATCH /promises/{id}` | ✓ Full |
| MissingItem | list per case, `PATCH /missing-items/{id}` (creation is ORCH-only — intentional) | ✓ Adequate |
| Action | `GET /cases/{id}/actions`, `POST /actions/{id}/cancel` | ✓ Adequate (read-only surface by design; no `GET /actions/{id}` — minor) |
| Task | `GET/POST /tasks`, `PATCH /tasks/{id}` | ✓ Full |
| FollowUpSequence | `GET /cases/{id}/followup`, pause/resume, `PATCH /followups/{id}` | ✓ Full |
| DecisionBrief | `GET /cases/{id}/briefs`, `GET /briefs/{id}`, `POST .../refresh` | ✓ Full |
| RiskFlag | `PATCH /risk-flags/{id}` (reads embedded in case/analysis) | Partial — no standalone list (`GET /cases/{id}/risk-flags` recommended) |
| HumanApproval | `GET /approvals?pending`, `GET /approvals/{id}`, `POST .../decision` | ✓ Full |
| AuditEvent | `GET /audit-events`, `/verify` (no mutation routes — correct) | ✓ Full |
| **CostEvent** | — | **✗ No endpoint** (gap #6) |
| **CostRateCard** | — | **✗ No endpoint** (gap #6) |
| IntegrationAccount | `GET /integrations`, connect, `DELETE` | ✓ Full |
| BusinessProfile | `GET/PATCH /business-profile` | ✓ Full |
| IndustryPlaybook | `GET /playbooks(/{id})`, `PATCH` | ✓ Full (pending gap #1 for version history reads) |
| VoiceProfile | `GET/PATCH /voice-profile` | ✓ Full |
| UserRole | `GET/POST /users`, `PATCH /users/{id}` | ✓ Full |
| graph_edges | only via `GET /cases/{id}?include=graph` | Partial — embedded only (acceptable MVP) |

**Entities with no endpoint at all: `CostEvent`, `CostRateCard`.** Everything else has at
least an adequate read or embedded surface.

---

*Prepared 2026-07-07. Re-run this audit when the first migration or route handler lands —
at that point ✓ must be re-verified against code, not prose.*

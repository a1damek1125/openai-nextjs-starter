# Action & Communication Engine — Data Model

> **Ground truth**: `finalis/actions/models.py` on branch
> `claude/finalis-action-communication-engine`; exercised by
> `tests/test_action_communication.py` (25 tests, 185 repo-wide passing).
> Canonical spec schema: `docs/finalis-ai/04-data-model.md`;
> API/event contract: `docs/finalis-ai/22-api-and-event-model.md`.
> Same scaffold principle as the case graph: dataclasses, not ORM — the
> scaffold proves logic, not persistence; field names match the spec so the
> production schema can be generated from the same shapes.

## 1. Entities AS CODED

All ids are uuid strings minted by `field(default_factory=_uuid)`.
**Implemented** below means: exists in `finalis/actions/models.py` and is
driven by passing tests.

### 1.1 `ActionRequest` — Implemented

The intent record: something (usually the completion loop) asks the engine to
act. It is *always* audited (`ACTION_REQUESTED`) before any gate runs.

| Field | Type | Notes |
|---|---|---|
| `tenant_id` | str | required |
| `case_id` | str | required |
| `action_type` | str | e.g. `send_photo_request`, `handoff_to_human` |
| `reason` | str | human-readable why |
| `source` | str | default `"completion_loop"` (spec `source_engine`) |
| `proposed_by` | str | default `"ai"` — becomes the audit `actor` |
| `payload` | dict | free-form: `recipient`, `urgent`, `confidence`, `variables`, `purpose`, `summary`, `owner` |
| `risk_level` | str | `low \| medium \| high` (default `low`) |
| `created_at` | datetime? | default `None` (scaffold does not stamp it) |
| `id` | str (uuid) | |

```json
{
  "id": "6f0c…",
  "tenant_id": "hvac-1",
  "case_id": "c-42",
  "action_type": "send_photo_request",
  "reason": "missing installation photo blocks quote",
  "source": "completion_loop",
  "proposed_by": "ai",
  "payload": {"recipient": "+48600100200", "purpose": "installation_photo"},
  "risk_level": "low",
  "created_at": null
}
```

### 1.2 `MessageDraft` — Implemented (carries the approval state)

Every outbound message is composed and **stored before sending — always**
(engine step 8, audited as `MESSAGE_DRAFT_CREATED`).

| Field | Type | Notes |
|---|---|---|
| `tenant_id`, `case_id`, `action_request_id` | str | provenance chain back to the request |
| `language` | str | e.g. `"pl"`, `"en"` |
| `channel` | str | routed channel at compose time |
| `text` | str | AI-composed text — never overwritten |
| `variables` | dict | template variables actually used |
| `risk_level` | str | copied from the request |
| `approval_status` | str enum | `NOT_REQUIRED \| PENDING \| APPROVED \| REJECTED \| EXPIRED \| CANCELLED` (default `NOT_REQUIRED`) |
| `edited_text` | str? | human's edit at approval time; `None` if unedited |
| `final_text` | property | `edited_text or text` — the only string ever sent |
| `id` | str (uuid) | doubles as the approval-queue key (`approval_id`) |

```json
{
  "id": "d-91…",
  "tenant_id": "hvac-1",
  "case_id": "c-42",
  "action_request_id": "6f0c…",
  "language": "pl",
  "channel": "whatsapp",
  "text": "[SZKIC DO EDYCJI PRZEZ CZŁOWIEKA] Dzień dobry, wracam do tematu naszej oferty. …",
  "variables": {},
  "risk_level": "high",
  "approval_status": "APPROVED",
  "edited_text": "Dzień dobry, wracam do tematu oferty — zapraszam do kontaktu."
}
```

Honest note on the enum: code paths set `PENDING` (queued), `APPROVED`,
`REJECTED`. `EXPIRED` and `CANCELLED` are **declared but never set** — there
is no approval-timeout worker yet (see `human-approval-queue.md`).

### 1.3 `ActionExecution` — Implemented (status flow)

One row per send attempt lifecycle; appended to `engine.executions`.

| Field | Type | Notes |
|---|---|---|
| `tenant_id`, `case_id`, `action_request_id` | str | |
| `channel` | str | mutated to the fallback channel on provider failure |
| `provider` | str | adapter `name` (`novu-mock`, `chatwoot-mock`) |
| `status` | str enum | `created → queued → scheduled → sent → delivered \| failed \| read \| replied` (default `created`) |
| `scheduled_at`, `executed_at` | datetime? | |
| `result` | dict | e.g. `{"conversation_id": "cw-1"}` for handoffs |
| `retry_count` | int | incremented on channel fallback |
| `id` | str (uuid) | |

Statuses actually driven by code: `created` (constructor), `sent`/`failed`
(in `_send`/`_handoff`/`_internal`), then `delivered`/`read`/`replied`/`failed`
via `record_delivery` (provider webhook path). `queued`/`scheduled` are in the
declared flow but no scaffold path sets them on the execution itself —
scheduling is represented by the Temporal workflow record instead.

```json
{
  "id": "x-17…",
  "tenant_id": "hvac-1",
  "case_id": "c-42",
  "action_request_id": "6f0c…",
  "channel": "sms",
  "provider": "novu-mock",
  "status": "delivered",
  "scheduled_at": "2026-07-07T11:00:00",
  "executed_at": "2026-07-07T11:00:00",
  "result": {},
  "retry_count": 1
}
```

### 1.4 `DeliveryEvent` — Implemented

Immutable record of a provider status callback, appended to
`engine.deliveries` by `record_delivery` (which also mutates the execution's
`status` and writes the matching audit event).

| Field | Type | Notes |
|---|---|---|
| `tenant_id`, `case_id`, `action_execution_id` | str | |
| `provider` | str | copied from the execution |
| `provider_message_id` | str | provider-side id |
| `status` | str enum | `sent \| delivered \| failed \| read \| replied \| clicked \| uploaded` |
| `payload` | dict | raw provider payload (see privacy note §3) |
| `id` | str (uuid) | |

```json
{
  "id": "de-3…",
  "tenant_id": "hvac-1",
  "case_id": "c-42",
  "action_execution_id": "x-17…",
  "provider": "novu-mock",
  "provider_message_id": "novu-1",
  "status": "replied",
  "payload": {}
}
```

### 1.5 `UploadLink` — Implemented (token_hash, never the token)

| Field | Type | Notes |
|---|---|---|
| `tenant_id`, `case_id` | str | |
| `purpose` | str | `installation_photo \| document \| …` |
| `token_hash` | str | SHA-256 hex of the raw token — **the raw token is never persisted** (`UploadLink.hash_token`) |
| `expires_at` | datetime | `now + 72h` default TTL |
| `status` | str enum | `CREATED \| SENT \| OPENED \| USED \| EXPIRED \| REVOKED` (default `CREATED`) |
| `allowed_types` | tuple | default `("image/jpeg", "image/png", "application/pdf")` |
| `max_size_mb` | int | default `25` |
| `used_at` | datetime? | |
| `id` | str (uuid) | |

```json
{
  "id": "ul-8…",
  "tenant_id": "hvac-1",
  "case_id": "c-42",
  "purpose": "installation_photo",
  "token_hash": "9b74c9897bac770ffc029102a200c5de…",
  "expires_at": "2026-07-10T11:00:00",
  "status": "USED",
  "allowed_types": ["image/jpeg", "image/png", "application/pdf"],
  "max_size_mb": 25,
  "used_at": "2026-07-07T15:00:00"
}
```

Full lifecycle and generator semantics: `upload-link-generator.md`.

### 1.6 `ConsentPreference` — Implemented

Per-party, per-channel consent fact.

| Field | Type | Notes |
|---|---|---|
| `tenant_id`, `party_id` | str | |
| `channel` | str | `sms \| whatsapp \| email \| phone \| any` — `any` is the hard opt-out of everything |
| `status` | str | `opted_in \| opted_out` |
| `source` | str | default `"intake"` |

```json
{"tenant_id": "hvac-1", "party_id": "p1", "channel": "any",
 "status": "opted_out", "source": "intake"}
```

No `id` field in the scaffold — production keys it `(tenant_id, party_id,
channel)`. Doc 04's rule applies unchanged: hard opt-outs are one-way sticky
(suppression hash survives GDPR erasure).

### 1.7 `ChannelPreference` — Implemented

| Field | Type | Notes |
|---|---|---|
| `tenant_id`, `party_id` | str | |
| `preferred_channel` | str | default `"whatsapp"` |
| `preferred_time_window` | tuple[int, int] | local hours, default `(8, 21)` — the business-hours window the consent gate enforces |
| `do_not_contact` | bool | default `False` — absolute block, checked before anything else |
| `available_channels` | tuple | default `("whatsapp", "sms", "email")` |
| `notes` | str | |

```json
{"tenant_id": "hvac-1", "party_id": "p1", "preferred_channel": "sms",
 "preferred_time_window": [8, 21], "do_not_contact": false,
 "available_channels": ["whatsapp", "sms", "email"], "notes": ""}
```

### 1.8 `RateLimitRule` — Implemented

| Field | Type | Notes |
|---|---|---|
| `tenant_id` | str | |
| `action_type` | str | default `"*"` (scaffold guard applies one rule to all) |
| `channel` | str | default `"*"` |
| `max_per_day` | int | default `3` — per case per calendar day |
| `cooldown_minutes` | int | default `20 * 60` = **20 hours** between attempts of the same (case, action_type) |
| `max_attempts` | int | default `3` — lifetime attempts per (case, action_type) |

```json
{"tenant_id": "hvac-1", "action_type": "*", "channel": "*",
 "max_per_day": 3, "cooldown_minutes": 1200, "max_attempts": 3}
```

The 20h cooldown + 3 max attempts is what produces the ~24h/48h/72h follow-up
cadence (see `follow-up-executor.md`).

## 2. Spec entities NOT (yet) coded — honest mapping

| Spec entity (docs 04/22) | Status | Where the behavior lives today |
|---|---|---|
| `HumanApproval` (first-class row: `deadline`, `sla_breached`, `decided_by`, `options`, `recommended_option` — doc 22 §HumanApprovals) | **Designed** — no dataclass | The approval **state** lives on `MessageDraft.approval_status` + `edited_text`; the pending **queue entry** is a plain dict on `engine.approval_queue` (`{draft, request, case, route, requested_at}`); the decision record is the audit pair `HUMAN_APPROVAL_GRANTED/REJECTED` with `actor=approver`. Production promotes this to a real `HumanApproval` table backing `GET /approvals` + `POST /approvals/{id}/decision`. |
| `CommunicationTemplate` (tenant-editable, versioned templates) | **Designed** — currently a code dict | `TEMPLATES: dict[(action_type, language), str]` in `finalis/actions/services.py`, with `FORBIDDEN_PATTERNS` safety. Production = per-tenant template table (playbook `templates`, doc 22 §Playbooks), versioned like `weights_version`, same forbidden-content validation on save *and* on render. |
| `AuditEvent` | **Implemented — shared**, not ACE-local | ACE writes to the same `finalis/audit.py` `AuditLog` (append-only, SHA-256 hash-chained, `verify_chain()`) as the case graph. No ACE-specific audit store exists or should. |
| `IntegrationAccount` (per-provider credentials) | **Designed** | Adapters take no credentials in the scaffold (mocks). See `integrations.md`. |
| `FollowUpSequence` (named multi-step cadence, doc 22) | **Designed** | Cadence is emergent from `RateLimitRule` defaults + post-send `FollowUpWorkflow` scheduling, not a stored sequence entity. |

## 3. Privacy & retention notes

- **Message content is PII.** `MessageDraft.text` / `edited_text`,
  `NovuMock.sent[].text` / `recipient`, and `ChatwootMock` conversation
  contact/notes all carry client-identifying content. Production stores them
  under the tenant's `data_region`, RLS-scoped, and inside the GDPR erasure
  path (doc 04) — with the one-way-sticky opt-out suppression hash exempted.
- **Upload tokens: hash only.** `UploadLink` stores `token_hash` (SHA-256);
  the raw token exists only in the returned URL handed to the client. The
  scaffold's `UploadLinkGenerator._urls` map (id → full URL) is a test
  convenience that production must not keep — persisting the URL would defeat
  the hashing.
- **Delivery payloads may carry provider PII.** `DeliveryEvent.payload` is
  the raw provider callback (phone numbers, WhatsApp profile names, error
  strings quoting message text). Treat it as PII: minimize what is stored,
  strip message bodies where the status alone suffices, and apply the same
  retention window as messages.
- **Audit events reference, not quote.** ACE audit payloads carry ids
  (`draft_id`, `execution_id`, `link_id`) and reasons — never message text —
  so the immutable hash chain does not become an unerasable PII store.
- **Consent records outlive content.** `ConsentPreference` rows (especially
  `opted_out`) must be retained past erasure as suppression hashes, per
  doc 04.

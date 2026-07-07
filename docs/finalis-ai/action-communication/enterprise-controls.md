# Action & Communication Engine — Enterprise Controls (vs. Reality)

> Branch `claude/finalis-action-communication-engine`; ground truth is
> `finalis/actions/*` + `tests/test_action_communication.py` (25 passing; 185 repo-wide).
> Status vocabulary per `37-enterprise-readiness-audit.md`: **Designed** (spec only),
> **Scaffolded** (field/hook exists, behavior not enforced), **Implemented and tested**
> (working code with passing tests — scaffold-level: in-memory, no persistence, no
> network), **Missing**. This document is deliberately honest: an in-memory engine cannot
> leak or lose data, so "no incidents possible today" is a property of the stage, not a
> control.

## 1. Multi-tenancy — Scaffolded

- `tenant_id` is a required field on **every coded ACE entity**: `ActionRequest`,
  `MessageDraft`, `ActionExecution`, `DeliveryEvent`, `UploadLink`, `ConsentPreference`,
  `ChannelPreference`, `RateLimitRule` (`finalis/actions/models.py`) — **Scaffolded**.
  The seam is right; nothing enforces it because nothing persists.
- Cross-tenant access checks exist and are **tested at the case-graph service level**
  (elsewhere in the repo suite), not at ACE level: the engine trusts the `Case` and
  `ActionRequest` it is handed.
- ACE-level enforcement (Postgres RLS on every ACE table, `tenant_id NOT NULL`,
  cross-tenant read/write test suite) — **Designed** (`37` §1). Must land with the first
  ACE migration, not after.
- Per-tenant configuration hook exists: `RateLimitRule(tenant_id=...)` and
  `RateLimitSpamGuard(rule=...)` accept a tenant-specific rule — Scaffolded (default
  rule is used in tests).

## 2. RBAC — Designed (identity recording Implemented)

- **Approver identity is recorded** on every approval decision:
  `decide_approval(..., approver="owner-1")` writes `actor=approver` into the
  `HUMAN_APPROVAL_GRANTED` / `HUMAN_APPROVAL_REJECTED` audit event — Implemented and
  tested (`test_16`, `test_reject_records_reason`, `test_19`).
- **Nothing checks who the approver is.** Role verification (owner/operator/viewer
  matrix, `37` §2) is Designed, 0% implemented.
- **AI-cannot-approve-its-own-action** is a **Designed rule to enforce at the API
  layer**: reject `approve` when the authenticated principal equals
  `ActionRequest.proposed_by` (or is any non-human principal). The data to enforce it
  already exists (`proposed_by` on the request, `approver` on the decision); the
  enforcement point is `/actions/{id}/approve` / `/messages/drafts/{id}/approve`
  (see `api-contracts.md` §1.1/§1.2). Until an API exists, callers of
  `decide_approval` are trusted.

## 3. Audit — Implemented and tested (strongest area)

- **Append-only, hash-chained log shared with the rest of the platform**
  (`finalis/audit.py`): every event carries `hash_prev`/`hash_self`; no update/delete
  API exists; `verify_chain()` walks the chain. ACE tests assert `verify_chain()` after
  full E2E flows (`test_17`, `test_18`, `test_20`) — the engine's events live on the
  same chain as case-graph events, so tampering anywhere breaks verification.
- **Every decision point writes an event** (engine docstring is enforced by
  `test_20_audit_written_for_all_important_steps`): `ACTION_REQUESTED`, gate outcome
  (`ACTION_CREATED`/`ACTION_BLOCKED`/`HUMAN_REVIEW_REQUESTED`/`ACTION_ABSTAINED`),
  `ACTION_GATE_BLOCK` (no channel / consent), `FOLLOW_UP_RATE_LIMITED`,
  `UPLOAD_LINK_CREATED/OPENED/USED`, `MESSAGE_DRAFT_CREATED`,
  `HUMAN_APPROVAL_REQUESTED/GRANTED/REJECTED`, `ACTION_SCHEDULED`,
  `TEMPORAL_WORKFLOW_STARTED/COMPLETED`, `NOVU_NOTIFICATION_TRIGGERED`,
  `MESSAGE_SENT/DELIVERED/READ/FAILED`, `CLIENT_REPLIED`, `CHATWOOT_HANDOFF_CREATED`,
  `MISSING_INFO_RESOLVED`.
- **Before/after edit stored — tested**: on human edit-and-approve, the AI draft
  (`MessageDraft.text`) is immutable and the human version goes to `edited_text`;
  `final_text` resolves to the edited version. The `HUMAN_APPROVAL_GRANTED` payload
  records `edited: true`. Asserted in `test_16_approve_edit_and_send`.
- Gap: persistence/partitioning/export of the chain — Designed (`37` §4).

## 4. Privacy — Partially implemented

- **PII surface is known and narrow**: recipient identifiers (phone numbers) live in
  `ActionRequest.payload["recipient"]` and adapter send records; message text lives in
  `MessageDraft.text/edited_text` and provider payloads; `DeliveryEvent.payload` may
  carry provider PII. Audit payloads written by the engine deliberately reference **ids**
  (draft_id, execution_id, link_id, channel), not message bodies or phone numbers —
  implemented by construction, not yet guarded by a redaction test.
- **No raw upload tokens stored — Implemented**: `UploadLink` persists only
  `token_hash = sha256(token)` (`UploadLink.hash_token`); the raw token exists only in
  the returned URL. Verified implicitly by `test_11`/`test_17` (open/use resolve via
  hash).
- **No secrets in logs**: the scaffold requires no credentials at all (verified repo-wide
  in `37` §6); adapters take no keys. Keep true via secret-scanning in CI before real
  adapters land.
- Retention (drafts/delivery payloads per `04` retention table), DSAR export/erasure
  with audit-skeleton preservation, and PII redaction middleware for logs/prompts —
  **Designed** (`37` §5). Suppression records (`ConsentPreference` opted_out) must
  survive erasure — Designed.

## 5. Consent — Implemented and tested

The strongest client-protection area, all enforced in code:

- **Per-channel opt-in/out**: `ConsentPreference(channel, status)`; `channel="any"`
  blocks everything. Enforced twice — `ChannelRouter.route` excludes opted-out channels
  from routing (tested: `test_optout_channel_excluded`), and
  `ConsentPermissionService.check` hard-blocks (tested: `test_9` — "any" opt-out yields
  `no_permitted_channel`).
- **Do-not-contact**: `ChannelPreference.do_not_contact=True` → hard block, no defer.
- **Business hours**: `preferred_time_window` (default 8–21 local); out-of-window,
  non-urgent sends are **deferred, not dropped** — durably scheduled via
  `temporal.schedule` with `ACTION_SCHEDULED` audit (tested:
  `test_business_hours_defer_via_temporal`). `urgent=True` overrides the window only,
  never opt-out.
- **Purpose**: upload links carry an explicit `purpose`
  (`installation_photo`/`document`/...), recorded in `UPLOAD_LINK_CREATED`; messages
  carry `ActionRequest.reason` in `ACTION_REQUESTED`.
- Additionally, the shared ActionGate blocks any `send_*`/`call_*`/`ask_*` on a case
  with `opted_out=True` (tested: `test_3`) — belt and braces with the consent gate.
- Gap: wiring real STOP webhooks to `ConsentPreference` records — Designed.

## 6. Reliability — Mixed

- **Retry + channel fallback — Implemented and tested**: provider failure on the primary
  channel retries once on `RouteDecision.fallback` with `retry_count` incremented
  (`test_provider_failure_uses_fallback_channel`); double failure → `MESSAGE_FAILED`
  audit + blocked outcome, never silent.
- **Durable deferral — mock-proven**: `TemporalMock` keeps scheduled work as plain data
  (the property real Temporal provides); `advance_to` fires due workflows
  (`test_12`). Real Temporal — Designed.
- **Idempotency keys — Designed** (`Idempotency-Key` on every mutating REST endpoint,
  replay returns original response); the in-process engine has no dedup — calling
  `handle` twice sends twice unless the rate limiter catches it (which it does for same
  action_type within cooldown — tested, `test_10` — but that is anti-spam, not
  idempotency).
- **DLQ + replay tooling — Designed** (`37` §7); no queue exists.

## 7. Observability — Designed metric set, derivable today

No metrics pipeline exists. The **8 required metrics** are specified as a designed set,
and each is already derivable by counting audit events (which is exactly how the tests
assert behavior today):

| Metric | Derivation from audit events (today) |
|---|---|
| `action_requests_total` | count `ACTION_REQUESTED` |
| `actions_sent_total` | count `MESSAGE_SENT` |
| `actions_blocked_total` | count `ACTION_BLOCKED` + `ACTION_GATE_BLOCK` + `ACTION_ABSTAINED` |
| `approvals_pending_total` | gauge: `HUMAN_APPROVAL_REQUESTED` − (`GRANTED` + `REJECTED`) |
| `followups_scheduled_total` | count `TEMPORAL_WORKFLOW_STARTED` (workflow=FollowUpWorkflow) |
| `delivery_failures_total` | count `MESSAGE_FAILED` |
| `upload_links_used_total` | count `UPLOAD_LINK_USED` |
| `opt_out_blocks_total` | count `ACTION_GATE_BLOCK` where reason ∈ {opted_out:*, do_not_contact, no_permitted_channel} + `ACTION_BLOCKED` (client_opted_out) |

Production plan: emit these as Prometheus/OTel counters keyed by `tenant_id` at the same
code points that write the audit events — Designed. Structured logging and alerting have
no spec (`37` §8 gap applies unchanged).

## 8. Cost control — Designed (one tenant-configurable knob Implemented)

- **`RateLimitRule` is tenant-configurable — Implemented**: `max_per_day` (default 3),
  `cooldown_minutes` (default 20h), `max_attempts` (default 3) per tenant/action/channel;
  the guard enforces all three plus client-reply pause (tested: `test_10`,
  `test_client_reply_pauses_followups`). These are the runaway-loop brakes that exist.
- **Per-tenant spend limits / quotas** (CostEvent metering, 80% warn / 100% stop) —
  Designed (`23`, `37` §9).
- **Kill switch** — Designed and Critical (`37` §9 gap #3): per-tenant per-action-type
  switch forcing observe-only + global outbound halt, built on the gate as the single
  choke point. ACE makes this cheap — `ActionGateService.evaluate` is the one call every
  outbound action passes through.

## 9. Security — Mixed

- **Token hashing — Implemented**: upload tokens stored only as SHA-256 hashes;
  URL-safe 24-byte `secrets.token_urlsafe` tokens; TTL expiry, MIME allowlist, size cap,
  revocation all enforced and tested (`test_11`).
- **Rate limits (anti-spam) — Implemented and tested**: see §8; these are hard
  guarantees, non-overridable by config below the floor (Designed invariant).
- **Signed webhooks — Designed**: HMAC-SHA256 + timestamp + replay window on
  `/webhooks/delivery-status` and `/webhooks/chatwoot` (spec in `api-contracts.md`
  §1.4); no webhook receiver exists, so nothing verifies signatures today.
- **Content safety — Implemented and tested**: `MessageComposer.FORBIDDEN_PATTERNS`
  rejects drafts whose variables smuggle prices/currency, over-promises, or legal-advice
  language (`test_8`); high-risk templates are human-edit skeletons that never contain
  prices.
- API auth, key scoping, encryption at rest/in transit — Designed per `22`/`37` §6.

## Bottom line

Real today: the shared tamper-evident audit chain with edit history, the consent stack
(opt-out, do-not-contact, business-hours deferral), anti-spam hard limits, hashed upload
tokens, channel fallback, and human approval with recorded identity — all in-memory.
Designed but not built: idempotency, signed webhooks, RBAC enforcement (including
AI-cannot-approve-own-action), RLS, metrics emission, kill switch, retention/DSAR. No
enterprise pilot until the Designed column's security items (webhook signing, RBAC,
RLS, kill switch) are code.

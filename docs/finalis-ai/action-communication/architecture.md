# Action & Communication Engine — Architecture

Code: `finalis/actions/{models,services,adapters,engine}.py`.
Tests: `tests/test_action_communication.py` (25, all passing).
Status vocabulary: **Implemented and tested** / **Mocked** (real behind a
protocol, deterministic stand-in today) / **Designed** (documented, not built).

## 1. The pipeline

```
Completion Loop ──> NBA ──> ActionRequest
                              │
                              ▼
                        ActionGate  ── BLOCK / ABSTAIN ──> audit + stop
                              │ ALLOW / REQUIRE_HUMAN_APPROVAL
                              ▼
                     ChannelRouter ── no permitted channel ──> audit + stop
                              │
                              ▼
              Consent & business hours ── opted out ──> audit + stop
                              │            └─ outside hours ──> defer (Temporal)
                              ▼
                    RateLimit / SpamGuard ── limited ──> audit + stop
                              │
                              ▼
              UploadLinkGenerator (photo/doc actions)
                              │
                              ▼
                    MessageComposer ──> MessageDraft (stored, audited)
                              │
              ┌── high risk / gate says approve ──> HumanApprovalQueue
              │                                        │ approve (± edit) / reject
              ▼                                        ▼
        Temporal (durable schedule: deferred send, follow-up cadence)
                              │
                              ▼
     ChannelRouter fallback ⇄ delivery adapters (provider seam / Chatwoot)
                              │
                              ▼
                      DeliveryTracker (sent/delivered/read/replied/failed)
                              │
                              ▼
        Case Graph update (MissingInfoService.resolve, reply pauses follow-ups)
                              │
                              ▼
                    AuditLog (hash-chained, every step above)
```

The audit log is not the last step so much as the substrate: **every** stage
above appends an event before control moves on, and the E2E tests assert
`audit.verify_chain()` at the end.

## 2. `engine.handle` — the 10 steps, as numbered in the source

`ActionCommunicationEngine.handle(case, request, *, prefs, consents, now,
language="pl") -> ExecutionOutcome` (`finalis/actions/engine.py`). Outcome
statuses: `executed | scheduled | pending_approval | blocked | deferred`.
Entry always appends `ACTION_REQUESTED` first.

| Step (source comment) | What happens | Audit events | Status |
|---|---|---|---|
| **1. Human handoff** | `handoff_to_human` short-circuits to `_handoff()` → `ChatwootMock.create_handoff` (AI summary as private note, `finalis-handoff` + reason labels); execution recorded with the conversation id | `CHATWOOT_HANDOFF_CREATED` | Implemented and tested (adapter Mocked) |
| **2. Internal actions** | `notify_owner` / `create_internal_task` skip client gates → `_internal()` sends to the owner's `inbox` channel | `NOVU_NOTIFICATION_TRIGGERED` | Implemented and tested |
| **3. ActionGate** | Reuses `finalis/case_services.py::ActionGateService.evaluate`; high-risk action types map to the gate's `send_out_of_rule_price`, everything else to `send_follow_up`; `BLOCK` and `ABSTAIN_MISSING_DATA` stop here | `ACTION_CREATED` / `ACTION_BLOCKED` / `HUMAN_REVIEW_REQUESTED` / `ACTION_ABSTAINED` (written by the gate) | Implemented and tested |
| **4. Channel routing** | `ChannelRouter.route(action_type, prefs, consents)`; `None` channel → blocked | `ACTION_GATE_BLOCK` (`no_permitted_channel`) | Implemented and tested |
| **5. Consent & business hours** | `ConsentPermissionService.check`: do-not-contact, per-channel/`any` opt-out, preferred time window (default 8–21 local); outside hours yields `defer_until` instead of a hard block (unless `urgent`) | `ACTION_GATE_BLOCK` on hard block | Implemented and tested |
| **6. Rate limit / anti-spam** | `RateLimitSpamGuard.check`: max attempts (3), cooldown (20 h), daily cap (3/case/day), and a hard pause once the client replied | `FOLLOW_UP_RATE_LIMITED` | Implemented and tested |
| **7. Upload link** | For `send_photo_request` / `send_document_request` / `send_upload_link`: `UploadLinkGenerator.create` mints a hashed-token, 72 h-TTL link and injects it into the template variables | `UPLOAD_LINK_CREATED` | Implemented and tested |
| **8. Compose** | `MessageComposer.compose` renders the template and runs the forbidden-pattern guard; **the draft is stored before anything is sent — always** | `MESSAGE_DRAFT_CREATED` | Implemented and tested |
| **9. Human approval** | Gate outcome `REQUIRE_HUMAN_APPROVAL` or `risk_level == "high"` → draft goes `PENDING` into `approval_queue`; nothing sends until `decide_approval` (approve, optionally with `edited_text`, or reject with reason) | `HUMAN_APPROVAL_REQUESTED`, later `HUMAN_APPROVAL_GRANTED` / `HUMAN_APPROVAL_REJECTED` | Implemented and tested |
| **10. Defer or send** | If consent said `defer_until`: durable `FollowUpWorkflow` scheduled on the workflow adapter → status `deferred`. Otherwise `_send()`: deliver on the routed channel, **fall back to the next channel on provider failure** (`retry_count` incremented), record the send in the rate limiter, and durably schedule the next follow-up check at +24 h | `ACTION_SCHEDULED` / `MESSAGE_SENT` / `MESSAGE_FAILED`, `TEMPORAL_WORKFLOW_STARTED` | Implemented and tested (transport Mocked) |

After send, `record_delivery(execution, status=...)` ingests provider callbacks
→ `DeliveryEvent`, updates execution status, appends `MESSAGE_DELIVERED` /
`MESSAGE_READ` / `CLIENT_REPLIED` / `MESSAGE_FAILED`, and on `replied` pauses
the case's automated follow-ups (Implemented and tested).

## 3. The 15 core services (spec) mapped to implementation

| # | Spec service | Implementation | Status |
|---|---|---|---|
| 1 | ActionRequestService | `ActionCommunicationEngine.handle()` — intake, audit, orchestration of steps 1–10 | Implemented and tested |
| 2 | ActionGateService | **Reused** from the Case Graph: `finalis/case_services.py::ActionGateService` (one gate, one autonomy model across modules) | Implemented and tested |
| 3 | ChannelRouter | `finalis/actions/services.py::ChannelRouter` (see `channel-router.md`) | Implemented and tested |
| 4 | MessageComposer | `finalis/actions/services.py::MessageComposer` (see `message-composer.md`) | Implemented and tested |
| 5 | ConsentPermissionService | `finalis/actions/services.py::ConsentPermissionService` | Implemented and tested |
| 6 | RateLimitSpamGuard | `finalis/actions/services.py::RateLimitSpamGuard` (+ `RateLimitRule` model) | Implemented and tested |
| 7 | HumanApprovalQueue | `engine.approval_queue` + `engine.decide_approval()` (approve-with-edit / reject-with-reason) | Implemented and tested |
| 8 | TemporalWorkflowAdapter | `finalis/actions/adapters.py::TemporalMock` behind the `WorkflowAdapter` protocol (schedule / `advance_to` simulated clock; state as plain data = the durability property Temporal provides for real) | Mocked; real Temporal Designed |
| 9 | ~~NovuAdapter~~ → **delivery-adapter seam** | `NovuMock` behind the `NotificationAdapter` protocol. Per the ADR, Novu is replaced by direct provider adapters; `NovuMock` is explicitly the mock of this **generic delivery seam**, and its `send()` signature is the production `deliver()` contract | Mocked |
| 10 | ChatwootAdapter | `finalis/actions/adapters.py::ChatwootMock` — `create_handoff` with private-note summary + labels (production: Chatwoot AgentBot webhook API) | Mocked; real Chatwoot Designed |
| 11 | DirectChannelAdapters | Meta WhatsApp Cloud API, Twilio SMS/WhatsApp, SES/SendGrid, Slack/Teams — each implementing the seam from row 9, retries/timeouts supplied by Temporal activities | **Designed** |
| 12 | DeliveryTracker | `engine.record_delivery()` → `DeliveryEvent`, execution status update, reply-pause | Implemented and tested |
| 13 | UploadLinkGenerator | `finalis/actions/services.py::UploadLinkGenerator` — SHA-256 token hash stored (never the token), TTL, mime/size allow-list, CREATED→SENT→OPENED→USED / EXPIRED / REVOKED lifecycle | Implemented and tested |
| 14 | AuditLogger | **Shared** `finalis/audit.py::AuditLog` — append-only, hash-chained, `verify_chain()` | Implemented and tested |
| 15 | CaseGraphUpdater | `MissingInfoService.resolve(case, field_key, source="upload")` on successful upload + case-side updates via delivery events (reply pause; E2E test 17 shows photo upload resolving `installation_photo` while `address` stays open) | Implemented and tested |

## 4. Action types (17)

Gate risk classes in code: `HIGH_RISK_ACTION_TYPES = {close_case_won,
close_case_lost, send_quote_status_update_with_price, send_price_negotiation,
send_contract_response}`; `UPLOAD_ACTIONS = {send_photo_request,
send_document_request, send_upload_link}`.

| # | Action type | Routing | Template | Status |
|---|---|---|---|---|
| 1 | `send_photo_request` | whatsapp → sms → email → phone_callback | pl + en, with upload-link suffix | **Implemented and tested** (E2E test 17: send → deliver → open → upload → missing-item resolved) |
| 2 | `send_document_request` | whatsapp → email → sms → phone_callback | none yet (compose would raise) | Routing + upload link Implemented; composition **Designed** |
| 3 | `ask_for_missing_info` | whatsapp → sms → email | pl (`{items}` list) | **Implemented and tested** (forbidden-pattern injection test) |
| 4 | `send_address_request` | whatsapp → sms → email | pl | Implemented (not directly exercised by a dedicated test) |
| 5 | `send_follow_up_after_offer` | whatsapp → email → sms | pl + en | **Implemented and tested** (E2E test 18: 72 h follow-up on preferred email) |
| 6 | `send_upload_link` | whatsapp → sms → email | none yet | Routing + link generation Implemented; composition **Designed** |
| 7 | `confirm_document_received` | whatsapp → sms → email | pl | Implemented |
| 8 | `notify_owner` | inbox → email → slack | free text (request reason) | **Implemented and tested** (internal path, step 2) |
| 9 | `create_internal_task` | internal (step 2 path) | free text | Implemented (shares the tested `_internal` path) |
| 10 | `handoff_to_human` | chatwoot → internal_task → phone_callback | pl (client-facing courtesy text) + Chatwoot private-note summary | **Implemented and tested** (step 1 path) |
| 11 | `schedule_callback` | internal_task | none (task payload, not a message) | Routing Implemented; task creation **Designed** |
| 12 | `mark_recovery_later` | default order | pl | Implemented (template only; no dedicated test) |
| 13 | `send_quote_status_update` | default order | pl (**no price** — status only) | Implemented |
| 14 | `send_quote_status_update_with_price` | high-risk variant of 13 | deliberately **no template** — a human drafts price content | Gate mapping Implemented; execution **Designed** |
| 15 | `send_price_negotiation` | default order | pl **skeleton** `[SZKIC DO EDYCJI PRZEZ CZŁOWIEKA]` | **Implemented and tested** (approval flow with human edit, E2E test 19) |
| 16 | `send_contract_response` | default order | pl **skeleton** `[SZKIC DO EDYCJI PRZEZ CZŁOWIEKA]` | **Implemented and tested** (rejection flow, "needs lawyer") |
| 17 | `close_case_won` / `close_case_lost` | n/a (case transition, not a message) | n/a | Gate classification Implemented (always high-risk → approval); state-machine execution **Designed** (lives with the Case Graph close flow) |

## 5. Production swap plan

The engine constructor wires `TemporalMock` / `NovuMock` / `ChatwootMock`
directly today; production replaces each behind its protocol
(`WorkflowAdapter`, `NotificationAdapter`, and the Chatwoot handoff seam)
without touching `handle`, `decide_approval`, or `record_delivery`. What is
Designed and not yet built: real provider adapters (row 11 above), a real
Temporal worker hosting `FollowUpWorkflow` (durable timer + signal on client
reply — the canonical human-approval/timeout pattern), a real Chatwoot instance
with AgentBot webhooks feeding `record_delivery` and the handoff path, webhook
signature verification, and persistence for the in-memory queues
(`approval_queue`, `executions`, `deliveries`, upload-link store).

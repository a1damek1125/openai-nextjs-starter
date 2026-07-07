# Action & Communication Engine — API Contracts

> **Status: Designed — no server.** Branch `claude/finalis-action-communication-engine`.
> No HTTP server exists in the repo; these REST contracts are the API projection of the
> engine that IS implemented and tested in `finalis/actions/` (25 passing tests in
> `tests/test_action_communication.py`, 185 repo-wide). Section 1 is the designed REST
> surface; Section 2 documents the internal Python interfaces **as implemented**, which the
> REST layer is a thin adapter over. Conventions follow the existing
> `docs/finalis-ai/openapi.finalis.yaml` (v0.1.0-draft): `/v1` base, RFC 9457
> `application/problem+json` errors, `Idempotency-Key` header (UUID, retained ≥24h,
> replays return the original response), every mutation writes an append-only AuditEvent,
> autonomy blocks return `403 autonomy_blocked`, approval-gated requests return `202` with
> a `human_approval_id`.

---

## 1. REST contracts (Designed)

### 1.1 Actions

#### `POST /v1/actions/request`
Submit an `ActionRequest` for gated execution. This is the REST form of
`ActionCommunicationEngine.handle(...)` — the request runs the full pipeline
(gate → routing → consent → rate limit → upload link → compose → approval/schedule/send).

Headers: `Idempotency-Key` (required for this and every mutating endpoint below).

```jsonc
// Request — mirrors finalis/actions/models.py::ActionRequest
{
  "case_id": "uuid",
  "action_type": "send_photo_request",       // see coded action_type vocabulary below
  "reason": "missing installation photo blocks quote",
  "source": "completion_loop",               // source engine
  "proposed_by": "ai",                       // "ai" | user id
  "risk_level": "low",                       // low | medium | high
  "payload": {
    "recipient": "+48600100200",
    "purpose": "installation_photo",         // upload actions only
    "urgent": false,                         // consent-gate override for business hours
    "confidence": 0.92,                      // feeds gate.evaluate
    "variables": { "items": ["address"] }    // composer variables
  },
  "language": "pl"
}
// tenant_id is NOT a body field — derived from auth context (see 37 §1 multi-tenancy).
```

```jsonc
// Response — mirrors engine.ExecutionOutcome; HTTP status varies by outcome
// 201 executed        → { "status": "executed", "reason": "sent",
//                         "action_request": {...}, "draft": {...},
//                         "execution": {...}, "upload_url": "https://..." }
// 202 pending_approval→ { "status": "pending_approval", "reason": "awaiting_human",
//                         "approval_id": "draft-uuid", "draft": {...} }
// 202 deferred        → { "status": "deferred", "reason": "outside_business_hours",
//                         "draft": {...}, "scheduled_workflow_id": "wf-1" }
// 403 blocked         → problem+json { "type": ".../autonomy_blocked",
//                         "detail": "client_opted_out" | "no_permitted_channel" |
//                                   "rate_limited:cooldown" | "abstain:confidence=0.40<0.5" }
```

Coded `action_type` vocabulary (from `engine.py` + `services.CHANNEL_PRIORITY`):
`send_photo_request`, `send_document_request`, `send_upload_link`,
`ask_for_missing_info`, `send_address_request`, `send_follow_up_after_offer`,
`confirm_document_received`, `send_quote_status_update`, `notify_owner`,
`create_internal_task`, `handoff_to_human`, `schedule_callback`, plus high-risk types
`close_case_won`, `close_case_lost`, `send_quote_status_update_with_price`,
`send_price_negotiation`, `send_contract_response` (set `HIGH_RISK_ACTION_TYPES`).

#### `GET /v1/actions/{id}`
Returns the `ActionRequest` plus its derived objects: latest `MessageDraft`,
`ActionExecution` list (with `retry_count`, `status`: `created|queued|scheduled|sent|
delivered|failed|read|replied`), `DeliveryEvent` list, and the gate decision's `audit_id`.
`404` if not found or not in the caller's tenant.

#### `POST /v1/actions/{id}/evaluate`
Dry-run the ActionGate only (`gate.evaluate`) without composing or sending. Response:
`{ "outcome": "ALLOW|BLOCK|REQUIRE_HUMAN_APPROVAL|ABSTAIN_MISSING_DATA",
"reason": "...", "audit_id": "..." }` — the exact `GateDecision` shape from
`finalis/case_services.py`. Writes the same `ACTION_CREATED|ACTION_BLOCKED|
HUMAN_REVIEW_REQUESTED|ACTION_ABSTAINED` audit event the inline path writes.

#### `POST /v1/actions/{id}/approve` · `POST /v1/actions/{id}/reject`
REST form of `engine.decide_approval(draft_id, approver=..., decision=..., ...)`
addressed by action id (resolves to the pending draft in the approval queue).

```jsonc
// approve body                              // reject body
{ "edited_text": "optional human edit" }     { "reason": "needs lawyer" }
// approve → 200 { "status": "executed", ... }   (draft.approval_status = APPROVED)
// reject  → 200 { "status": "blocked", "reason": "rejected:needs lawyer" }
// 404 if no pending approval entry; 409 already_decided on double-decide (Designed —
// the coded decide_approval returns None for a missing entry).
```

`approver` comes from the authenticated principal, never from the body — this is where
the **AI-cannot-approve-its-own-action RBAC rule** (Designed) is enforced: reject with
`403` if `principal == request.proposed_by` or principal role lacks `approver`.

#### `POST /v1/actions/{id}/schedule`
Durable-schedule the action instead of sending now (`temporal.schedule("FollowUpWorkflow",
run_at=..., payload=...)`). Body: `{ "run_at": "2026-07-08T08:00:00Z" }`. Response
`202 { "workflow_id": "wf-1" }`; writes `ACTION_SCHEDULED` + `TEMPORAL_WORKFLOW_STARTED`.

#### `POST /v1/actions/{id}/execute`
Execute a previously approved/scheduled action immediately (`engine._send` path).
`409` unless the action's draft is `APPROVED` or `NOT_REQUIRED`; never bypasses the gate —
the gate decision recorded at request time is re-checked for staleness (Designed).

### 1.2 Message drafts

#### `POST /v1/messages/draft`
Compose without sending — `composer.compose(...)` exposed directly (used by the Command
Center preview). Body: `{ "action_type", "language", "channel", "case_id",
"action_request_id", "variables": {...}, "risk_level" }`. Response `201` with the
`MessageDraft` (below). `422 forbidden_content` when a variable trips the composer's
`FORBIDDEN_PATTERNS` guard (prices, over-promises, legal advice) — the coded
`MessageComposeError`.

```jsonc
// MessageDraft — mirrors finalis/actions/models.py
{ "id": "uuid", "case_id": "uuid", "action_request_id": "uuid",
  "language": "pl", "channel": "whatsapp", "text": "Dzień dobry, ...",
  "variables": {}, "risk_level": "low",
  "approval_status": "NOT_REQUIRED",  // NOT_REQUIRED|PENDING|APPROVED|REJECTED|EXPIRED|CANCELLED
  "edited_text": null, "final_text": "Dzień dobry, ..." }
```

#### `GET /v1/messages/drafts/{id}`
Fetch a draft, including `final_text` (`edited_text or text`) and approval state.

#### `POST /v1/messages/drafts/{id}/approve`
Draft-addressed form of `decide_approval` — `{ "decision": "approve|reject",
"edited_text": "...", "reason": "..." }`. Same semantics/audit events as
`/actions/{id}/approve|reject`. Before/after edit is preserved: `text` is immutable,
`edited_text` stores the human version (tested in `test_16_approve_edit_and_send`).

#### `POST /v1/messages/drafts/{id}/send`
Send an already-approved (or `NOT_REQUIRED`) draft through the delivery path
(`engine._send`): primary channel, automatic fallback on provider failure
(`retry_count` incremented), `MESSAGE_SENT`/`MESSAGE_FAILED` audit, rate-limit
`record`, and the 24h follow-up cadence `FollowUpWorkflow` scheduled. `409` for
`PENDING|REJECTED|EXPIRED|CANCELLED` drafts.

### 1.3 Upload links

#### `POST /v1/upload-links`
`uploads.create(...)` — body `{ "case_id", "purpose": "installation_photo",
"ttl_hours": 72 }`. Response `201`:

```jsonc
{ "id": "uuid", "case_id": "uuid", "purpose": "installation_photo",
  "url": "https://upload.finalis.example/u/<token>",   // returned ONCE, never stored
  "status": "CREATED",             // CREATED|SENT|OPENED|USED|EXPIRED|REVOKED
  "expires_at": "2026-07-10T11:00:00Z",
  "allowed_types": ["image/jpeg", "image/png", "application/pdf"],
  "max_size_mb": 25 }
```

Only the SHA-256 `token_hash` is persisted (`UploadLink.hash_token` — Implemented);
the raw token appears exactly once in this response and in the composed message.

#### `GET /v1/upload-links/{id}`
Metadata + lifecycle status; never returns the token or URL.

#### `POST /v1/upload-links/{id}/revoke`
`uploads.revoke(link_id)` → status `REVOKED`; a revoked/expired token is refused by the
public upload page (`uploads.open` returns null). Response `204`.

(The public token-bearing upload page itself — `GET/POST upload.finalis.example/u/{token}`,
backed by `uploads.open`/`uploads.use` with MIME/size enforcement — is a separate
unauthenticated surface, Designed; the state machine behind it is Implemented and tested,
`test_11_expiring_link_lifecycle`, `test_17`.)

### 1.4 Webhooks (inbound, signed)

#### `POST /v1/webhooks/delivery-status`
**Naming note:** originally sketched as `POST /webhooks/novu`. Per the provider decision
(see `production-readiness-matrix.md` — Novu-as-hub REPLACED by direct channel adapters),
the path is provider-neutral: every channel adapter (WhatsApp BSP, SMS, SMTP events)
posts delivery status here. REST form of `engine.record_delivery(...)`.

Security (Designed, per `37` §6): HMAC-SHA256 signature header
(`X-Finalis-Signature: t=<unix>,v1=<hmac(t + "." + body)>`), ±5 min replay window,
unsigned/stale/replayed → `401` + security audit event.

```jsonc
// Request                                    // Effect (Implemented in record_delivery)
{ "execution_id": "uuid",                     // → DeliveryEvent appended
  "provider": "whatsapp-bsp",                 // → execution.status updated
  "provider_message_id": "wamid.abc",         // → audit: MESSAGE_DELIVERED | MESSAGE_READ |
  "status": "delivered",                      //   CLIENT_REPLIED | MESSAGE_FAILED
  "payload": { } }                            // status=replied → rate.client_replied(case)
// status ∈ sent|delivered|failed|read|replied|clicked|uploaded (DeliveryEvent.status)
// Response: 200 { "delivery_event_id": "uuid" }; idempotent on (provider, provider_message_id, status).
```

#### `POST /v1/webhooks/chatwoot`
Signed the same way. Consumes Chatwoot conversation events (`conversation_resolved`,
`message_created` by agent) to close the handoff loop: maps `conversation_id` back to the
`ActionExecution` created by `chatwoot.create_handoff` and updates case state / resumes
or keeps paused the follow-up cadence. Designed; the outbound handoff half is Implemented
and tested (`test_14_chatwoot_mock_creates_handoff`).

### 1.5 Communication ops

#### `POST /v1/communication/test-channel`
Ops/onboarding probe: `{ "channel": "whatsapp", "recipient": "+48..." }` → sends a
provider test message via the adapter (`novu.send`-shaped `NotificationAdapter.send`)
and returns `{ "ok": true, "provider": "...", "provider_message_id": "..." }` or the
adapter error. Bypasses composer/consent only for tenant-owned test recipients;
audit-logged.

#### `GET /v1/communication/providers`
Per-tenant provider/channel health: configured adapters, `mode` (mock|live), last
successful send, current `fail_channels`-style outage flags, and active
`RateLimitRule` values (`max_per_day`, `cooldown_minutes`, `max_attempts`).

#### `GET /v1/communication/audit/{case_id}`
Tenant-scoped communication timeline for one case — the filtered projection of
`AuditLog.events(case_id=...)` restricted to communication event types
(`ACTION_REQUESTED`, `ACTION_CREATED/BLOCKED/ABSTAINED`, `MESSAGE_DRAFT_CREATED`,
`HUMAN_APPROVAL_*`, `ACTION_SCHEDULED`, `MESSAGE_SENT/DELIVERED/READ/FAILED`,
`CLIENT_REPLIED`, `FOLLOW_UP_RATE_LIMITED`, `UPLOAD_LINK_*`,
`TEMPORAL_WORKFLOW_*`, `NOVU_NOTIFICATION_TRIGGERED`, `CHATWOOT_HANDOFF_CREATED`),
each with `hash_prev`/`hash_self` so the export re-verifies offline (chain verification
is Implemented — `audit.verify_chain()`, asserted in tests 17/18/20).

### 1.6 Folding into `openapi.finalis.yaml`

The existing spec already has: `GET /actions` (read-only list), `/approvals` +
`/approvals/{id}/decision` (generic HITL), `/missing-items`, `/audit-events`, and
channel webhooks (`/webhooks/whatsapp|sms|email|telephony|calendar`). To fold this
engine in as **new paths**:

| New path | Relation to existing spec |
|---|---|
| `POST /actions/request`, `GET /actions/{id}`, `/actions/{id}/evaluate\|approve\|reject\|schedule\|execute` | Extends the read-only `/actions` tag; `approve/reject` should delegate to the existing `/approvals/{id}/decision` semantics (409 `already_decided`, `edit_and_approve` ≈ `edited_text`). |
| `/messages/draft*` | New; complements `/conversations/{id}/messages` (which is the conversation transcript, not the safe-send path). |
| `/upload-links*` | New; feeds `/documents` + `/missing-items` on use. |
| `POST /webhooks/delivery-status`, `POST /webhooks/chatwoot` | Join the existing `/webhooks/*` family; same signing spec should retro-apply to all of them. |
| `/communication/*` | New `communication` tag. |
| Schemas to add | `ActionRequest`, `MessageDraft`, `ActionExecution`, `DeliveryEvent`, `UploadLink`, `ConsentPreference`, `ChannelPreference`, `RateLimitRule` — field-for-field from `finalis/actions/models.py`. |

---

## 2. Internal interfaces — AS IMPLEMENTED

Source of truth: `finalis/actions/engine.py`, `services.py`, `adapters.py`,
`finalis/case_services.py`, `finalis/audit.py`. These signatures are what the tests run.

### Engine (`finalis/actions/engine.py`)

```python
class ActionCommunicationEngine:
    def __init__(self, audit: AuditLog) -> None
        # wires: gate=ActionGateService(), router=ChannelRouter(),
        # composer=MessageComposer(), consent=ConsentPermissionService(),
        # rate=RateLimitSpamGuard(), temporal=TemporalMock(audit),
        # novu=NovuMock(audit), chatwoot=ChatwootMock(audit),
        # uploads=UploadLinkGenerator(audit)

    def handle(self, case: Case, request: ActionRequest, *,
               prefs: ChannelPreference, consents: list[ConsentPreference],
               now: datetime, language: str = "pl") -> ExecutionOutcome
        # Pipeline: audit ACTION_REQUESTED → handoff/internal shortcuts →
        # gate.evaluate → router.route → consent.check → rate.check →
        # uploads.create (UPLOAD_ACTIONS) → composer.compose →
        # approval queue (REQUIRE_HUMAN_APPROVAL or risk_level=="high") →
        # temporal defer (business hours) → _send

    def decide_approval(self, draft_id: str, *, approver: str, decision: str,
                        now: datetime, edited_text: Optional[str] = None,
                        reason: str = "") -> Optional[ExecutionOutcome]
        # approve → APPROVED (+edited_text), audit HUMAN_APPROVAL_GRANTED, _send
        # reject  → REJECTED, audit HUMAN_APPROVAL_REJECTED, blocked outcome
        # None when draft_id has no pending queue entry

    def record_delivery(self, execution: ActionExecution, *, status: str,
                        provider_message_id: str,
                        payload: dict | None = None) -> DeliveryEvent
        # appends DeliveryEvent, updates execution.status, audits
        # MESSAGE_DELIVERED/MESSAGE_READ/CLIENT_REPLIED/MESSAGE_FAILED,
        # and on "replied" calls rate.client_replied(case_id)

@dataclass
class ExecutionOutcome:
    request: ActionRequest
    status: str        # executed | scheduled | pending_approval | blocked | deferred
    reason: str
    draft: Optional[MessageDraft] = None
    execution: Optional[ActionExecution] = None
    upload_url: Optional[str] = None
    approval_id: Optional[str] = None
```

### Gate (`finalis/case_services.py` — shared with the case brain)

```python
class ActionGateService:
    def evaluate(self, case: Case, action_type: str, *, confidence: float = 1.0,
                 audit: AuditLog, context: dict | None = None) -> GateDecision
        # GateDecision(outcome: ALLOW|BLOCK|REQUIRE_HUMAN_APPROVAL|ABSTAIN_MISSING_DATA,
        #              reason: str, audit_id: Optional[str])  # audit_id always set
```

### Services (`finalis/actions/services.py`)

```python
class ChannelRouter:
    def route(self, action_type: str, prefs: ChannelPreference,
              consents: list[ConsentPreference]) -> RouteDecision
        # RouteDecision(channel, fallback, reason, provider="mock");
        # channel=None + reason="no_permitted_channel" when everything is opted out

class MessageComposer:
    def compose(self, action_type: str, *, language: str, channel: str,
                tenant_id: str, case_id: str, action_request_id: str,
                variables: dict | None = None,
                risk_level: str = "low") -> MessageDraft
        # raises MessageComposeError on missing template or FORBIDDEN_PATTERNS hit

class ConsentPermissionService:
    def check(self, *, prefs: ChannelPreference, consents: list[ConsentPreference],
              channel: str, now: datetime, urgent: bool = False) -> ConsentDecision
        # ConsentDecision(allowed, reason, defer_until);
        # do_not_contact / opted_out → allowed=False, defer_until=None (hard block);
        # outside preferred_time_window & not urgent → defer_until=next window open

class RateLimitSpamGuard:
    def __init__(self, rule: RateLimitRule | None = None) -> None
    def check(self, *, case_id: str, action_type: str, now: datetime) -> RateDecision
        # reasons: paused_client_replied | max_attempts | cooldown | daily_limit | ok
    def record(self, *, case_id: str, action_type: str, now: datetime) -> None
    def client_replied(self, case_id: str) -> None   # pauses automated follow-up
    def resume(self, case_id: str) -> None

class UploadLinkGenerator:
    BASE_URL = "https://upload.finalis.example/u/"
    def create(self, *, tenant_id: str, case_id: str, purpose: str, now: datetime,
               ttl_hours: int = 72) -> tuple[UploadLink, str]   # (link, one-time URL)
    def open(self, token: str, now: datetime) -> Optional[UploadLink]
        # None on unknown/expired/revoked; CREATED|SENT → OPENED (audited)
    def use(self, token: str, now: datetime, *, mime: str, size_mb: float) -> bool
        # MIME allowlist + max_size_mb enforced; → USED (audited)
    def revoke(self, link_id: str) -> None            # → REVOKED
```

### Adapters (`finalis/actions/adapters.py` — Protocols + deterministic mocks)

```python
class WorkflowAdapter(Protocol):        # implemented by TemporalMock
    def schedule(self, workflow: str, *, run_at: datetime, payload: dict) -> str
    def advance_to(self, now: datetime) -> list[dict]   # fires due workflows (sim clock)

class NotificationAdapter(Protocol):    # implemented by NovuMock (name="novu-mock")
    name: str
    def send(self, *, channel: str, recipient: str, text: str,
             tenant_id: str) -> dict    # {"ok": bool, "provider_message_id": str|None}

class ChatwootMock:                     # name = "chatwoot-mock"
    def create_handoff(self, *, tenant_id: str, case_id: str, contact: str,
                       summary: str, labels: list[str] | None = None) -> dict
        # conversation dict; AI summary stored as private_note; audited
```

Mocks are deterministic and observable; production swaps the transport, not the engine —
none of the adapters makes decisions (gate/approval/audit are always upstream).

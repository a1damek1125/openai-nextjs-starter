# Action & Communication Engine — Integrations (Chatwoot + Delivery Adapters)

> **Ground truth**: `finalis/actions/adapters.py` (`NotificationAdapter`
> protocol, `NovuMock`, `ChatwootMock`), send/handoff paths in
> `finalis/actions/engine.py`. Tests:
> `tests/test_action_communication.py::TestAdapters`. Spec: doc 12
> (integrations), doc 18 (stack), doc 21 (state-of-the-art review),
> doc 22 §1.3 (inbound webhooks), §IntegrationAccounts.

Both integrations obey the adapters-module rule: *"production swaps the
transport, not the engine"*, and *"none of these adapters makes decisions —
the Finalis brain (gate/approval/audit) is always upstream."*

## 1. Chatwoot — verdict: ADOPT

**License**: Chatwoot core is MIT; the `enterprise/` directory is under a
separate commercial license (standard open-core carve-out). Self-hosting the
MIT core is compatible with Finalis's model; do not ship `enterprise/` code.

**Role split**: Chatwoot is the **conversation UI** for humans; **Finalis
stays the source of truth** — case state, scores, gates, approvals, and the
audit chain live in Finalis. Chatwoot never decides anything.

### Mock-implemented and tested

- **Handoff**: `handoff_to_human` requests bypass the messaging gates (see
  `action-gate.md` §4) and go straight to
  `ChatwootMock.create_handoff(tenant_id, case_id, contact, summary, labels)`,
  which creates a conversation record with:
  - the **AI summary as a private note** (`private_note` — agent-visible,
    never sent to the client),
  - **labels** `["finalis-handoff", <request.reason>]` for queue routing,
  - `assigned: None` (Chatwoot's own assignment rules pick the agent),
  and audits `CHATWOOT_HANDOFF_CREATED`. The engine records an
  `ActionExecution(channel="chatwoot", provider="chatwoot-mock",
  status="sent", result={"conversation_id": …})`.
  **Tested**: `test_14_chatwoot_mock_creates_handoff` (private note contains
  the AI summary; audit event present).

### Designed (not coded)

- **Contact ↔ Party mapping**: Chatwoot `contact` ↔ Finalis `Party` via a
  stored `chatwoot_contact_id` on the party (dedup on phone/email as in
  doc 22 §Parties); **Case ↔ Conversation mapping**: `conversation_id` kept
  on the execution/case so subsequent handoffs reuse the thread.
- **Webhook ingestion back to Finalis**: Chatwoot `message_created` /
  `conversation_status_changed` / assignment webhooks →
  `POST /v1/webhooks/chatwoot` with **signed-webhook verification** (HMAC,
  per `IntegrationAccount.webhook_config`, replay-protected — the doc 22
  §1.3 pattern). Agent replies map to `message.sent{sent_by: human}`; client
  messages in a Chatwoot conversation map to `contact.inbound_received` →
  `record_delivery(status="replied")` → follow-up pause; conversation
  `resolved` can propose (never force) a case transition.

## 2. The delivery-adapter seam

### The protocol as coded

```python
class NotificationAdapter(Protocol):
    name: str
    def send(self, *, channel: str, recipient: str, text: str,
             tenant_id: str) -> dict: ...   # {"ok", "provider_message_id", "error"?}
```

`NovuMock` implements it: records sends, audits
`NOVU_NOTIFICATION_TRIGGERED`, and simulates outages via `fail_channels`
(returning `{"ok": False, "error": "<channel>_provider_down"}`), which is how
the fallback path is tested (`test_provider_failure_uses_fallback_channel`,
`test_13_novu_mock_sends`). The engine calls only this protocol — never a
provider SDK.

### Research verdict: Novu community self-host — REJECTED

The mock kept the Novu name, but the research decision is **not** to build on
Novu community edition: the features Finalis needs most —
**multi-tenancy and inbound webhook support are cloud/enterprise-only**, not
in the self-hostable community edition. A notification hub that cannot
isolate tenants or receive delivery-status webhooks on-prem fails the
architecture's tenancy and source-of-truth requirements.

### Instead: direct provider adapters behind the same protocol

| Channel | Provider | Role |
|---|---|---|
| WhatsApp | **Meta WhatsApp Cloud API** | primary client channel (template messages outside the 24h window) |
| SMS + WhatsApp | **Twilio** | SMS primary; WhatsApp **fallback** if Meta Cloud API is down/unavailable for the tenant |
| Email | **SES or SendGrid** | client email + owner digests |
| Owner/internal | **Slack / Teams** webhooks | `notify_owner` beyond the in-app inbox |

Each is a small class implementing `NotificationAdapter` — exactly the seam
`NovuMock` currently mocks — so the engine, gate, rate limiter, and audit
trail are untouched by provider choice. Channel fallback order stays a
**router** decision (`RouteDecision.fallback`), not an adapter decision.

### Delivery-status webhooks → `record_delivery`

Provider callbacks (Meta statuses, Twilio DLRs, SES/SendGrid bounce/open
events) arrive on the doc 22 §1.3 webhook endpoints (signature-verified,
replay-protected, 2xx-fast) and are mapped to
`engine.record_delivery(execution, status=…, provider_message_id=…,
payload=…)` — the already-implemented-and-tested path that updates
`ActionExecution.status`, appends a `DeliveryEvent`, audits
(`MESSAGE_DELIVERED`/`MESSAGE_READ`/`CLIENT_REPLIED`/`MESSAGE_FAILED`), and
pauses follow-ups on replies. STOP/opt-out payloads additionally write a
sticky `ConsentPreference(status="opted_out")`.

### Credentials: `IntegrationAccount` — Designed

Per-tenant, per-provider credential config is the doc 22
`IntegrationAccount` entity: tokens live in the secrets manager, the API
exposes only a `credentials_ref` handle, connect/disconnect is
`owner`/`manager`-gated and audited. Adapters receive credentials resolved
per `tenant_id` at send time; the scaffold's mocks take none, which is the
honest current state.

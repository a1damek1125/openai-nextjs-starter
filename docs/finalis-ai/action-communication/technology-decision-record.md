# ADR: Action & Communication Engine technology stack

**Status**: Accepted (2026-07-07). Research-verified against primary sources on
2026-07-07. Evidence tags: **[VP]** = verified primary (source code, repository
license files, release tags inspected directly); **[S]** = secondary (official
docs / vendor statements, not independently reproduced).

**Decision in one line**: **Temporal (durable execution) + Chatwoot (human
conversation & handoff) + a thin direct provider-adapter layer (delivery) +
optional Activepieces (long-tail integrations) — orchestrated by the Finalis
brain, which alone makes decisions.**

---

## 1. The options considered

| Option | Composition | Summary verdict |
|---|---|---|
| **A** | Build everything in-house (own scheduler on Postgres, own inbox, own adapters) | Maximal control, maximal cost; re-invents durable execution and agent inbox poorly |
| **B** | **Chatwoot-only** (Chatwoot + cron jobs) | Great human inbox, but **lacks durability** — no durable timers, retries, or human-approval-with-timeout semantics; follow-up cadence on cron is exactly how cases get silently dropped |
| **C** | **Novu-only** (Novu handles orchestration + delivery) | **Worst on multi-tenancy (1/5)**: Organizations/Tenants are cloud-only in the self-hosted community edition, and so are delivery-status webhooks — fails two hard requirements outright |
| **D** | Workflow-tool-centric (n8n / Activepieces as the engine) | Visual workflow tools on the compliance-critical path; n8n's Sustainable Use license blocks embedding; neither gives durable-execution guarantees |
| **E** | Temporal + Chatwoot + Novu (original composite) | Right shape, wrong delivery layer (see the Novu challenge below) |
| **E-modified** | **Temporal + Chatwoot + direct provider adapters + Finalis brain** | **Winner** — keeps E's durability and handoff quality, replaces Novu with a thin adapter layer we fully control |
| **F** | Fully managed SaaS suite (Twilio Flex / Intercom class) | Fast start, but per-seat/per-message economics, weak data control, and the AI brain becomes a plugin in someone else's product |

## 2. Scoring

Scale 1–5 per criterion (5 best). Criteria weighted by Finalis hard
requirements: multi-tenant isolation, durable execution (never-drop),
license safety for an embedded commercial product, human handoff quality,
delivery-callback fidelity, ops burden, compliance-path control.

| Criterion | A in-house | B Chatwoot-only | C Novu-only | D workflow-tool | E original | **E-modified** | F SaaS |
|---|---|---|---|---|---|---|---|
| Multi-tenancy | 4 | 3 | **1** | 3 | 2 | **4** | 3 |
| Durability / never-drop | 2 | **2** | 2 | 2 | 5 | **5** | 3 |
| License safety (embedding) | 5 | 4 | 3 | 2 | 3 | **5** | 2 |
| Human handoff / inbox | 2 | 5 | 1 | 2 | 5 | **5** | 4 |
| Delivery callbacks | 3 | 3 | **1** (cloud-only) | 3 | 2 | **4** | 4 |
| Ops burden | 1 | 4 | 3 | 3 | 3 | **3** | 5 |
| Compliance-path control | 5 | 3 | 2 | 2 | 4 | **5** | 1 |
| **Total** | 22 | 24 | **11** | 17 | 24 | **31** | 22 |

**E-modified wins.** B-Chatwoot-only loses on durability; C-Novu-only scores
worst overall and bottoms out (1/5) on multi-tenancy; D is disqualified from
the compliance-critical path regardless of score (see §5).

## 3. Per-candidate license & capability matrix

| Candidate | Version checked | License | Key findings | Evidence |
|---|---|---|---|---|
| **Chatwoot** — ADOPT | v4.15.1 | Core **MIT**, with an `enterprise/` directory under a **proprietary carve-out** | SAML/SCIM/audit-logs are gated behind the enterprise carve-out — budget an Enterprise self-host plan **or build our own controls** for those. Channels verified in source: email, webchat, SMS, Telegram, Line, WhatsApp (Meta Cloud API + 360dialog native, plus Twilio). | [VP] (repo/license/channels); AgentBot webhook API as the bot→human handoff primitive and signed webhooks [S] |
| **Temporal** — ADOPT | v1.31.1 | **MIT** | 4 services + PostgreSQL is a legitimate production self-host topology. Python SDK mature. Durable timers (`workflow.sleep`) + signals/`wait_condition` are the canonical human-approval-with-timeout pattern. Worker Versioning GA. | [VP] license/version; [S] self-host topology, versioning GA |
| **Novu** — CHALLENGED → **REPLACED** | current | Core still **MIT** (NOT BSL — a circulating claim we checked and rejected) | See §4. | [VP] license; [S] cloud-only feature gating |
| **Activepieces** — OPTIONAL | v0.86 (pre-1.0) | **MIT** core + `ee/` split | 280+ MCP pieces. Use for internal/long-tail integrations only; **never on the compliance-critical path** (pre-1.0, and the critical path must stay gate→approval→audit in our code). | [VP] |

## 4. The Novu challenge (stated plainly)

Novu was the planned delivery/notification layer. On verification
(2026-07-07):

1. **License is fine**: the core is still MIT, not BSL as sometimes claimed
   [VP]. License was never the problem.
2. **Self-hosted posture is not**: Novu's own guidance frames community
   self-hosting as **"test and experiment"** rather than a supported
   production posture [S].
3. **Two hard requirements fail in the community edition** [S]:
   - **Organizations/Tenants are cloud-only** — Finalis is multi-tenant by
     construction (every entity in `finalis/actions/models.py` carries
     `tenant_id`); a delivery layer without tenant isolation is disqualifying.
   - **Delivery-status webhooks are cloud-only** — the engine's
     `DeliveryTracker` (`record_delivery` → `DeliveryEvent` → status →
     `CLIENT_REPLIED` pausing follow-ups) is built on delivery callbacks;
     without them the never-drop loop is blind.

**Decision**: replace Novu with a thin **direct provider-adapter layer** inside
the Finalis engine — Meta WhatsApp Cloud API (primary) + Twilio SMS/WhatsApp
(fallback) + SES/SendGrid (email) + Slack/Teams (internal) — all behind one
`deliver()` interface, with **Temporal activities supplying retries and
timeouts** (so the adapter layer stays thin: no queues, no retry logic of its
own). Revisit Novu only as a **paid enterprise self-host** if the channel count
ever explodes beyond what a handful of adapters can carry.

**Consequence for the code**: the scaffold's `NovuMock`
(`finalis/actions/adapters.py`) is therefore — explicitly — **the mock of this
generic delivery-adapter seam**, not of Novu the product. It implements the
`NotificationAdapter` protocol (`send(channel, recipient, text, tenant_id) ->
{ok, provider_message_id}`), which is exactly the `deliver()` contract the
direct provider adapters will implement. Nothing in the engine changes when the
mock is swapped for real adapters; only the transport does.

## 5. Alternatives (one-liners)

- **n8n** — Sustainable Use license: **AVOID for embedding** in a commercial
  product; fine as a customer's own tool, not as our engine.
- **Windmill** — capable script/flow platform, but copyleft core + workflow-
  tool posture: a tool for internal jobs at most, never the execution engine.
- **Inngest** — SSPL on the self-hosted server: **caution**; SSPL is
  disqualifying for our embedding model.
- **Restate** — interesting lightweight durable execution, but a younger
  ecosystem and a more restrictive server license than Temporal's MIT; watch,
  don't adopt.
- **DBOS** — the **credible lightweight Temporal alternative** (MIT,
  Postgres-only, durable execution as a library): the designated fallback if
  ops simplicity ever outweighs Temporal's maturity. See revisit triggers.

## 6. The WhatsApp provisioning reality

WhatsApp is the primary client channel in `CHANNEL_PRIORITY`, and it is **an
operational workstream, not a library feature**. Reality: Meta **business
verification**, a dedicated **phone number**, and either the **Cloud API**
directly or a BSP (**360dialog** — which Chatwoot integrates natively — or
**Twilio**). Business-initiated messages **outside the 24-hour customer-service
window require pre-approved message templates** — meaning the Polish templates
in `finalis/actions/services.py` must each be submitted for Meta template
approval per tenant before the engine may send them proactively. Template
approval lead time, per-number quality ratings, and per-conversation pricing
all belong in the tenant-onboarding runbook, not in the codebase.

## 7. Final stack

| Layer | Choice | Status in scaffold |
|---|---|---|
| Decisions (gate, consent, rate limit, routing, composition, approval, audit) | **Finalis brain** — `finalis/actions/` + shared `ActionGateService`/`AuditLog` | Implemented and tested (25 tests) |
| Durable execution (deferred sends, follow-up cadence, approval timeouts) | **Temporal** (MIT, self-host, 4 services + PostgreSQL) | Mocked (`TemporalMock`); real cluster Designed |
| Human conversation & bot→human handoff | **Chatwoot** (MIT core; enterprise features budgeted or rebuilt) | Mocked (`ChatwootMock`); real instance Designed |
| Delivery | **Direct provider adapters** — Meta WhatsApp Cloud API, Twilio SMS/WhatsApp fallback, SES/SendGrid email, Slack/Teams — behind one `deliver()` seam | Mocked (`NovuMock` = the seam's mock); real adapters Designed |
| Long-tail/internal integrations | **Activepieces** (optional, MIT, 280+ MCP pieces) | Designed, off the compliance path |

## 8. Revisit triggers

Re-open this ADR when any of the following becomes true:

1. **Channel count explodes** (≳8–10 client-facing channels): re-evaluate Novu
   **paid enterprise self-host** (tenants + delivery webhooks included) versus
   maintaining more direct adapters.
2. **Temporal ops burden dominates** (the 4-service cluster costs more
   operational attention than the workflows justify): evaluate **DBOS**
   (MIT, Postgres-only) as the lightweight replacement behind the same
   `WorkflowAdapter` protocol.
3. **Chatwoot enterprise pricing or carve-out scope shifts**: re-price
   Enterprise self-host versus building SAML/SCIM/audit-log controls ourselves.
4. **Activepieces reaches 1.0** with a stable security story: reconsider its
   allowed scope (still never the gate/approval/audit path).
5. **Meta/BSP policy changes** to the 24-hour window, template rules, or Cloud
   API pricing: re-balance WhatsApp-primary vs SMS/email-primary routing
   defaults in `CHANNEL_PRIORITY`.

# Finalis AI — Integrations

> How the AI Case & Deal Worker touches the outside world. Every external system is exposed to
> the workers as an **MCP server** (tools/resources/prompts), connected per-tenant through an
> **`IntegrationAccount`** (see `04-data-model.md`), and acted on only within the case's
> **autonomy level** (see `13-autonomy-and-safety.md`). Channels feed the Orchestrator
> (`02-multi-agent-architecture.md`); nothing client-facing goes out without passing the
> autonomy gate.

---

## 1. Integration philosophy

**Every external system is an MCP tool/resource server.** Finalis follows the same stance as the
tooling layer in `02-multi-agent-architecture.md §3`: all external capabilities — calendar,
email, WhatsApp, SMS, telephony, Drive, later CRM/e-sign — are exposed to workers through the
**Model Context Protocol (MCP)**, an open protocol that standardizes how LLM apps integrate
external tools and data. Current spec: **stable spec 2025-11-25** (async tasks, OIDC
discovery, elicitation enums; 2026-07-28 RC in flight) —
https://modelcontextprotocol.io/specification/2025-11-25. Relevant properties we lean on:

- **Tools / resources / prompts** as the three primitives — a booking action is a *tool*, an
  inbox thread is a *resource*, a follow-up template is a *prompt*.
- **Servers are OAuth 2.0 resource servers** — the auth model below maps cleanly
  onto MCP's own authorization story.
- **Structured tool output** — typed results the workers can validate (feeds the Quality Worker).
- **Elicitation** — a server can request mid-session user input, which we use for
  interactive OAuth connect flows and disambiguation.

Why this matters: each integration becomes a **swappable server with a typed contract**,
testable in isolation and reusable across workers. Swap Twilio for Telnyx, or Gmail for
Outlook, without touching worker logic. It also future-proofs against
orchestration-framework churn (LangGraph / OpenAI Agents SDK both speak MCP).

**Credentials never live in the database.** Per the `IntegrationAccount` contract in
`04-data-model.md`, we store `provider`, `scopes (jsonb)`, `status`, `webhook_config (jsonb)`,
`connected_by`, and **`credentials_ref` — a handle to a secrets manager, NOT the secret**.
Tokens (OAuth access/refresh, API keys, WhatsApp system-user tokens) are held in the secrets
store (e.g. AWS Secrets Manager / GCP Secret Manager / Vault); the MCP server resolves the
handle at call time. Consequences:

- Least-privilege scopes are recorded on the account and enforced at connect time.
- Token rotation/refresh happens in the secrets layer; the DB row is stable.
- A DB compromise leaks no usable credentials.
- Every credential *use* is an `AuditEvent`; every connect/disconnect flips
  `IntegrationAccount.status` and audits `connected_by`.

**One MCP server per provider family**, multi-tenant, resolving `credentials_ref` per call. A
server never holds a tenant's secret in memory beyond the call.

> Note: this very session exposes **Google Calendar**, **Gmail**, and **Google Drive** MCP tool
> suites — a live example of exactly the pattern below (e.g. `create_event`, `list_events`,
> `search_threads`, `search_files`). The MVP mirrors these as tenant-scoped servers.

---

## 2. MVP integrations

For each: **purpose · direction · key API/webhooks · auth model · data mapped to Finalis
entities · gotchas**. Entities referenced are those defined in `04-data-model.md` — none are
invented here.

### 2.1 Google Calendar & Outlook Calendar

- **Purpose**: booking site visits / appointments, reminders, reschedules; reading tech
  availability to offer slots during voice/chat/intake.
- **Direction**: **read + write**.
- **Key API / webhooks**:
  - Google: Calendar API v3 (`events.insert/patch/delete`, `freebusy.query`); push
    notifications via `events.watch` → webhook channels (must be renewed before expiry).
  - Outlook/Microsoft 365: Microsoft Graph `/me/events`, `/calendars`, `getSchedule`;
    change notifications via Graph **subscriptions** (also renewal-bound).
- **Auth model (OAuth scopes, least-privilege)**:
  - Google: `https://www.googleapis.com/auth/calendar.events` (+ `calendar.readonly` if only
    reading availability). Avoid full `calendar` unless calendar management is needed.
  - Microsoft Graph: `Calendars.ReadWrite` (delegated or application), `offline_access` for
    refresh tokens.
- **Mapped to Finalis entities**: a booking becomes an `Action` (`type = schedule`,
  `channel = calendar`, `autonomy_level_used`), which writes an appointment reference on the
  `Case`; reminders/reschedules run through the `FollowUpSequence`. Availability reads feed the
  Intake/Voice workers' slot offers.
- **Gotchas**:
  - **Watch/subscription renewal**: both providers expire push channels (Google channels and
    Graph subscriptions are short-lived); a cron must re-subscribe or events are silently
    missed. Track expiry in `IntegrationAccount.webhook_config`.
  - **Timezone / DST correctness** is the classic footgun — always store and send IANA TZ +
    offset; the tenant TZ lives in `BusinessProfile.timezone`, respect `quiet_hours`.
  - **Double-booking races** — use `freebusy`/`getSchedule` immediately before insert, and
    idempotency keys on create.
  - Google unverified-app scope screens and Microsoft admin-consent for some tenants can block
    connect flows in production — plan the app-verification process.

### 2.2 Gmail / Outlook Email

- **Purpose**: inbound email parsing → `Conversation`/`Message`; outbound follow-ups, quote
  delivery, document requests.
- **Direction**: **read + write**.
- **Key API / webhooks**:
  - Gmail API: `users.messages.list/get`, `users.messages.send`, `users.drafts`;
    push via **Pub/Sub `users.watch`** (renew weekly).
  - Graph Mail: `/me/messages`, `/sendMail`; change notifications via Graph subscriptions.
  - Inbound alt-path: a dedicated ingest address via an inbound-parse provider (SendGrid/Mailgun
    inbound webhook) when full-mailbox OAuth is undesirable.
- **Auth model**:
  - Gmail: `gmail.readonly` + `gmail.send` (or `gmail.modify` if labeling/threading is needed —
    prefer narrower). `gmail.compose` for drafts-only Level‑2 "prepare" behavior.
  - Graph: `Mail.Read`, `Mail.Send` (delegated), `offline_access`.
- **Mapped to Finalis entities**: each thread → `Conversation (channel = email)`; each mail →
  `Message (direction = in|out, channel = email, provider_msg_id, attachments → Document ids)`.
  Attachments are ingested as `Document`s (§2.7/§2.8). Outbound follow-ups are `Action`s
  produced by the Follow-up Worker. Extracted promises/missing items ride on the `Message`
  fields (`detected_promises`, `detected_missing`).
- **Gotchas**:
  - **Threading & dedup**: match on `Message-ID`/`References` headers to keep a
    `Conversation` coherent and avoid duplicate `Message` rows on webhook re-delivery.
  - **Deliverability**: outbound needs tenant SPF/DKIM/DMARC alignment or replies land in spam —
    for Level‑4/5 autonomous sends this is a hard prerequisite. Consider sending from the
    tenant's own domain via their provider, not a Finalis relay, to preserve reputation.
  - **HTML/quoted-reply noise** — strip signatures/quoted history before extraction, or promises
    get re-detected from quoted text.
  - Gmail `watch` expires ~7 days; must re-arm.
  - Google **restricted-scope** verification (annual security assessment) applies to broad Gmail
    scopes — narrow scopes avoid it. *(Verify current Google policy at build time.)*

### 2.3 WhatsApp Business (Cloud API)

- **Purpose**: primary customer-service channel in the MVP verticals — inbound questions/photos,
  proactive follow-ups, appointment reminders.
- **Direction**: **read + write** (incl. media).
- **Key API / webhooks**: **WhatsApp Cloud API** (Meta Graph) `POST /{phone-number-id}/messages`
  for send; inbound messages + delivery/read receipts + template-status via the Meta **webhook**
  (subscribe to `messages` field). Media is fetched by media-id then downloaded.
- **Auth model**: Meta **system-user access token** scoped to the WhatsApp Business Account
  (`whatsapp_business_messaging`, `whatsapp_business_management`); the token handle lives in the
  secrets store. Numbers are provisioned through an Embedded Signup / BSP flow.
- **Mapped to Finalis entities**: thread → `Conversation (channel = whatsapp, party_id)`;
  messages → `Message (channel = whatsapp, provider_msg_id, delivery_status)`; inbound images →
  `Photo` (nameplate/damage/site) or `Document`; `Party.whatsapp_id` is the routing key.
  Outbound proactive messages are `Action`s within a `FollowUpSequence`.
- **Gotchas — call these out as real constraints**:
  - **24-hour customer-service window**: you may send **free-form** messages only within 24h of
    the customer's last inbound message. Outside it, you **must** send a pre-approved **template
    (HSM)** — free-form sends are rejected. The Follow-up Worker must therefore choose
    *free-form vs. template* based on `Conversation.last_inbound_at`.
  - **Templates require pre-approval** by Meta (category: utility / marketing / authentication),
    have per-category **pricing** and **quality ratings** that can pause a template.
  - **Opt-in is mandatory**: businesses must obtain user opt-in before messaging; marketing
    templates especially. Track consent on `Party.contact_opt_outs` and honor it.
  - **Messaging limits / tiers** ramp with quality; a low quality rating throttles or blocks.
  - **Media**: download-by-id, size/type limits, and media URLs expire — persist to S3
    (`Document.storage_url` / `Photo.storage_url`) immediately.
  - Store `provider_msg_id` to reconcile async `sent → delivered → read → failed` receipts onto
    `Message.delivery_status`.

### 2.4 SMS (Twilio / Telnyx / Vonage)

- **Purpose**: universal fallback for reminders, short follow-ups, OTP-style confirmations where
  WhatsApp/email aren't available.
- **Direction**: **read + write**.
- **Key API / webhooks**: provider REST send API; inbound SMS + delivery-status via provider
  webhook (e.g. Twilio Messaging + status callbacks). Provider abstracted behind one MCP server.
- **Auth model**: provider **API key/secret** (not OAuth) held in secrets store; per-tenant
  sub-account/messaging-service id recorded on the `IntegrationAccount`.
- **Mapped to Finalis entities**: `Conversation (channel = sms)` / `Message (channel = sms)`;
  `Party.phones` (E.164) is the address; outbound = `Action`s in a `FollowUpSequence`.
- **Gotchas / constraints**:
  - **A2P 10DLC (US)**: application-to-person SMS on US long codes requires **brand + campaign
    registration** (10DLC) or you face heavy filtering/blocking; toll-free needs verification;
    short codes are separate. Non-US has its own **sender-ID / alphanumeric** registration
    regimes. This is a **provisioning lead-time** item, not a code toggle — surface registration
    status on `IntegrationAccount.status`.
  - **STOP/consent (see §5)** — carriers mandate opt-out keyword handling.
  - **Segmentation & Unicode** — emoji/accents shrink segments to 70 chars and multiply cost.
  - No native media in many regions (MMS limited) — link to hosted media instead.

### 2.5 Telephony / Voice (SIP trunking)

- **Purpose**: inbound/outbound phone calls handled by the **Voice Worker** — the real-time
  conversational channel. Full architecture in **`06-voice-architecture.md`**; this section is
  the integration surface only.
- **Direction**: **read + write** (bidirectional audio) + call metadata.
- **Key API / webhooks**: **SIP trunking** into the media stack — **LiveKit SIP** (WebRTC/SIP
  bridge feeding the realtime pipeline) or **Twilio** (Programmable Voice / Elastic SIP
  Trunking + Media Streams). Inbound call events, DTMF, and recording-status via provider
  webhooks; numbers provisioned per tenant.
- **Auth model**: provider **API key/secret** + SIP trunk credentials in secrets store; number
  inventory and routing on `VoiceProfile` (`04-data-model.md`).
- **Mapped to Finalis entities**: each call → `Call` (recording_url, transcript segments,
  sentiment_timeline, barge_in_events, latency_metrics, handoff_to_human, detected_promises /
  detected_missing / next_actions). Config comes from `VoiceProfile` (tts_voice, stt_vendor,
  greeting, barge_in, `recording_enabled`, `consent_prompt`). See `06`.
- **Gotchas**:
  - **Latency budget** (TTFA p50/p95) is the make-or-break metric — see `06`. Region/codec/trunk
    choice matters.
  - **Call-recording consent** is jurisdiction-dependent (two-party states / EU) — driven by
    `VoiceProfile.consent_prompt` + `BusinessProfile.recording_consent_config`; audio retention
    default 90 days (`04-data-model.md`). See §5.
  - **Handoff to human** must be seamless and gated by autonomy level; degraded-model fallback is
    scripted turns + handoff (`02 §7`).
  - Number provisioning / porting and **STIR/SHAKEN** caller-ID attestation affect
    answer rates for outbound.

### 2.6 Web form + Web chat widget (embeddable)

- **Purpose**: capture leads from the tenant's website; live/async chat with the AI worker.
- **Direction**: **read + write** (chat) / **read** (form submit).
- **Key API / webhooks**: an **embeddable JS widget** (script tag / iframe) posting to a Finalis
  ingest endpoint; realtime chat over WebSocket/SSE. First-party — no third-party OAuth.
- **Auth model**: per-tenant **public embed key** (domain-allowlisted, rate-limited) for the
  widget; server-side session tokens for the chat channel. No secrets shipped to the browser.
- **Mapped to Finalis entities**: form submit → new `Case` (`source_channel = web_form`) + a
  `Party`; chat session → `Conversation (channel = web_chat)` + `Message`s. File/photo uploads →
  `Document`/`Photo`.
- **Gotchas**:
  - **Spam/bot abuse** — CAPTCHA/honeypot + rate limits before a submission mints a `Case`.
  - **CSP / cross-origin** embedding on tenant sites; version the widget for cache-busting.
  - **Identity stitching** — a web-chat visitor is anonymous until they give a phone/email; merge
    onto an existing `Party` carefully (dedup on phone/email) to keep Deal Memory coherent.
  - GDPR/cookie consent on the tenant page is the tenant's responsibility but we must support
    a no-tracking mode.

### 2.7 Google Drive / OneDrive (document ingest)

- **Purpose**: ingest existing documents (offers, contracts, invoices, plans) a tenant or client
  keeps in cloud storage.
- **Direction**: **read** (MVP; write is roadmap for filing outputs back).
- **Key API / webhooks**:
  - Google Drive API: `files.list/get`, `files.export`, content download; `files.watch` /
    Drive push for change notifications.
  - Microsoft Graph: `/me/drive`, `/drive/items`; Graph subscriptions for changes.
- **Auth model (least-privilege)**:
  - Google: prefer **`drive.file`** (per-file access granted via picker) over broad
    `drive.readonly`, to avoid restricted-scope verification and over-broad access.
  - Graph: `Files.Read` (or `Files.Read.Selected`), `offline_access`.
- **Mapped to Finalis entities**: each ingested file → `Document` (`source = web`, `storage_url`,
  `mime`, → OCR/extraction by the Document Intelligence Worker per `07`). Images → `Photo`.
- **Gotchas**:
  - **Copy vs. reference** — we ingest a copy to S3 (`Document.storage_url`) so retention/erasure
    are under Finalis control; do not depend on the live Drive link.
  - **Native Google Docs/Sheets** must be **exported** (they have no direct bytes) to PDF/CSV.
  - Broad Drive scopes trigger Google's restricted-scope security assessment — the `drive.file`
    picker flow sidesteps it. *(Confirm current policy at build.)*
  - Large files / rate limits — stream and back off.

### 2.8 PDF upload (direct)

- **Purpose**: the simplest, always-available ingest — a client or agent uploads a PDF (offer,
  invoice, contract, scanned form) directly in chat, web widget, or Command Center.
- **Direction**: **write-in** (upload) → internal processing.
- **Key API / webhooks**: first-party pre-signed S3 upload; on completion, enqueue the Document
  Intelligence pipeline (`07`).
- **Auth model**: first-party session auth; pre-signed URL scoped to one object. No external
  OAuth.
- **Mapped to Finalis entities**: → `Document` (`source = client|company`, `mime = application/pdf`,
  `pages`, `ocr_engine`, `ocr_text`, `ocr_quality`, `layout_json`) → `ExtractedField`s +
  `EvidenceReference`s + possible `RiskFlag`s; may underlie an `Offer`. See `07`.
- **Gotchas**:
  - **Scanned vs. digital** PDFs — image-only scans need OCR; `ocr_quality`/`overall_confidence`
    gate downstream trust and can set `Document.status = needs_rescan`.
  - **Malware / content scanning** on upload; enforce max size/page count.
  - **Password-protected / corrupt** PDFs — detect and ask for a re-send (prefer-ask-over-assume,
    `02 §7`).
  - Encrypted at rest; may hold highly sensitive PII (IDs, contracts) — access-logged
    (`04-data-model.md`).

---

## 3. Later / vertical integrations (roadmap)

Not in the MVP; each still lands as an MCP server + `IntegrationAccount`. Priority order is
indicative, not committed.

**Horizontal (all verticals):**

| Integration | Purpose | Direction | Notes / auth |
|---|---|---|---|
| **CRM — HubSpot / Pipedrive** | Sync `Case`→deal, `Party`→contact; push activity | read+write | OAuth; map pipelines to case states (`03`). Bidirectional sync conflict rules needed. |
| **E-signature — DocuSign** | Send quotes/contracts for signature; capture signed docs | read+write | OAuth (DocuSign) + Connect webhooks; signed doc → `Document`, signature event → `Action`/`AuditEvent`. High-autonomy gated. |
| **Invoicing / accounting** (QuickBooks, Xero, Stripe Invoicing) | Raise invoice on close; reconcile payment | read+write | OAuth; `Offer`→invoice; payment status → `Case` close. Financial writes = high approval. |
| **Field-Service Management — ServiceTitan / Jobber-style** | Sync jobs, dispatch, technician schedules, pricebook | read+write | Vendor APIs/OAuth; `Case`↔job, `Action(schedule)`↔dispatch, availability for booking. Often the **system of record** at the tenant — sync direction must be explicit. |
| **Quoting / estimating tools** | Pull pricebook/estimates into Quote Builder | read | Feeds `Offer` generation (`10`). |

**Per-vertical:**

| Vertical | System | Purpose |
|---|---|---|
| Auto workshop | Workshop/DMS + parts catalogs | job intake, parts availability, estimate → `Offer` |
| Property management | Property-management CRM (e.g. AppFolio/Buildium-style) | tenant/unit context, maintenance tickets → `Case` |
| Legal | Case-/matter-management systems | matter sync, document/deadline (`Promise`) tracking |
| Insurance | Claims workflow / carrier portals | claim intake, document requirements → `MissingItem`, status sync |

> All roadmap items inherit the same rules: secrets by reference only, least-privilege scopes,
> typed MCP contract, and autonomy-gated writes.

---

## 4. Integration → autonomy level → human approval

Autonomy levels are the 1–5 ladder on `Case.autonomy_level` / `Action.autonomy_level_used`,
defined canonically in **`13-autonomy-and-safety.md`** (this table uses that ladder; `03`
already fixes **Level 2 = "Prepare"**). Working shorthand of the ladder:

| Level | Name | Meaning |
|---|---|---|
| **1** | Observe | Read/ingest only; zero outbound client-facing actions. |
| **2** | Prepare | Draft/stage an action (e.g. compose reply, build quote) — human sends. |
| **3** | Communicate | Autonomous low-risk informational sends (reminders, confirmations, missing-info requests, receiving/placing AI voice calls) — no approval; no prices, bookings, or discounts. |
| **4** | Execute Low Risk | Autonomously books appointments and sends rule-covered standard quotes/follow-ups — no approval; outside-rule steps escalate. |
| **5** | Conditional Autopilot | Full workflow within strict rules, without per-action approval; escalates on thresholds/hard overrides. |

The **minimum level required to *act*** on each integration, and whether a human approval gate
(`HumanApproval`) is normally required. Actual behavior is per-tenant via
`BusinessProfile.autonomy_defaults` and can be capped by state (`03`).

| Integration | Read/ingest | Typical autonomous *action* | Min level to act | Human approval? |
|---|---|---|---|---|
| Google/Outlook Calendar | L1 | Book / reschedule appointment | **L4** | No for routine slots; **yes** if it moves a confirmed high-value job |
| Gmail / Outlook email — routine follow-up | L1 | Send reminder / info-request (informational) | **L3** | No (informational, reversible) |
| Gmail / Outlook — quote / contract email | L1 | Send rule-covered standard priced offer | **L4** | No for quotes fully inside `price_rules` and below `high_value_threshold`; **yes — `HumanApproval` regardless of level** for anything priced outside rules, discounts, or legal content |
| WhatsApp — in-window free-form reply | L1 | Reply within 24h window (informational) | **L3** | No |
| WhatsApp — template / proactive (out-of-window) | L1 | Send approved template (informational) | **L3** | No, but **opt-in + approved template** required (§2.3/§5) |
| SMS — reminder / confirmation | L1 | Send SMS reminder | **L3** | No (consent + 10DLC required) |
| Telephony / Voice — inbound | L1 | Answer, converse, qualify (**booking within the call needs L4**) | **L3** | No; **hard handoff** on `θ_escalate` or hot flags (`06`) |
| Telephony / Voice — outbound call | L1 | Place informational AI call (intake / follow-up) | **L3** | **Yes** for cold/high-value; No for expected callbacks |
| Web form | L1 | Create `Case`, auto-acknowledge (informational) | **L3** | No |
| Web chat | L1 | Converse, collect info | **L3** | No; escalate on gate |
| Drive / OneDrive ingest | **L1** | (ingest only in MVP) | n/a (read) | No |
| PDF upload | **L1** | (ingest only) | n/a (read) | No |
| CRM sync (roadmap) | L1 | Write deal/activity | **L4** | No (internal), reconcile conflicts |
| E-signature (roadmap) | L1 | Send for signature | — | **Yes — legal content, `HumanApproval` regardless of level** |
| Invoicing / payment (roadmap) | L1 | Raise invoice / charge | — | **Yes — financial action, `HumanApproval` regardless of level** |
| FSM dispatch (roadmap) | L1 | Create/dispatch job | **L4** | Tenant-config; often **yes** |

Rules of thumb consistent with the rest of the blueprint: **routine informational sends (email
follow-up reminders, in-window WhatsApp session replies, SMS reminders, answering inbound
voice) run autonomously from L3 with no approval; bookings and rule-covered standard quotes
require L4; anything priced outside rules, discounts, and legal content require a
`HumanApproval` regardless of level.** Sending a priced offer requires L4 with full price-rule
coverage; outside rule coverage it requires `HumanApproval` regardless of level (`13` §1). Any
transition into `HUMAN_REVIEW_REQUIRED` **caps autonomy at Level 2** (`03` §2 invariants) —
outbound actions freeze. If `a* = argmax Utility(a)` needs a level above the case's setting,
the Orchestrator emits a `HumanApproval` instead of executing (`05` §3 Next Best Action).

---

## 5. Compliance notes

These are enforced constraints, not documentation niceties. All consent state lives on
`Party.contact_opt_outs` / `Party.quiet_hours`; all sends/consent changes write `AuditEvent`s;
data region is `BusinessProfile.data_region`.

- **WhatsApp opt-in & template policy** — Meta requires **explicit user opt-in** before a
  business messages them, and messages **outside the 24-hour customer-service window must use a
  pre-approved template** (HSM). Marketing templates carry stricter opt-in and category/quality
  rules; poor quality ratings throttle or block. The Follow-up Worker branches on
  `Conversation.last_inbound_at` (in-window free-form vs. out-of-window template) and refuses to
  send if opt-in is absent. *(Meta policies change — re-verify template categories/pricing at
  build time.)*

- **SMS consent & STOP handling** — carriers/regulators (TCPA in the US, plus **A2P 10DLC**
  registration, §2.4) require **prior express consent** to text and honoring of opt-out
  keywords (**STOP/UNSUBSCRIBE/CANCEL/END/QUIT** → suppress; **HELP** → info; **START** →
  resume). Opt-outs set a **permanent suppression** on `Party.contact_opt_outs` that **survives
  GDPR erasure as a suppression hash** (`04-data-model.md` `Party` retention notes). Respect `quiet_hours` /
  time-of-day rules.

- **Call-recording consent** — recording is jurisdiction-dependent (two-party-consent US
  states, EU/GDPR). Driven by `VoiceProfile.consent_prompt` +
  `BusinessProfile.recording_consent_config`; the Voice Worker plays the consent notice before
  recording, and audio retention defaults to 90 days (transcript retained with the case). If
  consent is refused, proceed without recording or hand off per config.

- **OAuth least-privilege** — request the **narrowest scopes** that work (e.g. `drive.file` over
  `drive.readonly`; `gmail.send`+`gmail.readonly` over `gmail.modify`); store only a
  `credentials_ref` (§1); rotate/refresh in the secrets layer; record granted scopes on
  `IntegrationAccount.scopes` and re-consent on scope change. Broad Google scopes (Gmail/Drive)
  can trigger Google's **restricted-scope security assessment** — narrow scopes and per-file
  pickers avoid it. Microsoft Graph application permissions may need **tenant-admin consent**.

- **General** — every PII access is logged (`AuditEvent`); erasure (DSAR) and export are
  first-class (`04-data-model.md` Retention & privacy summary); a disconnected/expired `IntegrationAccount` fails
  closed (workers get no tool, not a stale token).

---

## 6. Uncertain / verify-at-build

Marked honestly, per blueprint convention:

- Exact **OAuth scope strings** and whether a given scope is "restricted/sensitive" shift with
  provider policy — **verify against live Google/Microsoft/Meta docs at implementation time.**
- WhatsApp **template categories, pricing model, and messaging-limit tiers** change frequently.
- **A2P 10DLC** thresholds, throughput, and per-carrier filtering evolve; registration is a
  lead-time dependency to schedule early.
- **Watch/subscription lifetimes** (Gmail `watch`, Drive/Calendar/Graph subscriptions) are
  provider-set and short — confirm current values and build renewal jobs.
- **LiveKit SIP vs. Twilio** final choice depends on the latency/cost analysis in
  `06-voice-architecture.md`; both are viable SIP entry points.

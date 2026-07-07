# Finalis Action & Communication Engine — Founder / CTO Report

**Date**: 2026-07-07 · **Branch**: `claude/finalis-action-communication-engine`
**Test command**: `python3 -m pytest tests/ -q` → **185 passed** (25 ACE-specific; no
network/DB/keys needed).

Wording: **Implemented and tested** = passing tests · **Mocked** = mock behind a production
protocol · **Designed** = docs only · **Scaffolded** = minimal code.

---

## The 22 direct answers

**1. What was implemented?**
The full safe execution path, executable and tested: `ActionRequest` intake → **ActionGate**
(reused, 4 outcomes) → **consent gate** (opt-out, do-not-contact, business hours with
durable deferral) → **RateLimitSpamGuard** (20h cooldown, 3 attempts, daily cap,
client-reply pause) → **ChannelRouter** (preference-first, consent-aware, fallback) →
**MessageComposer** (Polish/English templates, forbidden-pattern price/advice guard,
high-risk human-edit skeletons, drafts always stored before sending) → **HumanApprovalQueue**
(approve/edit/reject with audit of before/after text) → **durable scheduling** (TemporalMock
with simulated clock) → **delivery** (adapter protocol with provider-failure fallback,
tested) → **DeliveryTracker** (sent/delivered/failed/read/replied; reply pauses follow-ups)
→ **UploadLinkGenerator** (hashed tokens, TTL, full state machine, mime/size limits) →
**Case Graph update** (upload resolves MissingItem — E2E tested) → **audit everywhere**
(hash chain verified in every test). All 3 mandated E2E scenarios pass.

**2. What was only documented?** REST API surface, real provider adapters (Meta WhatsApp
Cloud/Twilio/SES), Chatwoot/Temporal real integrations, signed webhooks, RBAC enforcement,
observability metrics, kill switch, the 5 remaining Temporal workflow types.

**3. What is mocked?** Temporal (`TemporalMock` — simulated clock, restart-survivable
plain-data state), the delivery layer (`NovuMock` — which per the ADR now mocks the
**generic direct-provider adapter seam**, not Novu specifically), Chatwoot
(`ChatwootMock` — handoff conversation + AI-summary private note). All behind protocols the
production adapters implement.

**4. What is missing?** Real credentials/providers (WhatsApp Business provisioning is its
own operational workstream — Meta verification + templates), HumanApproval as a first-class
persisted entity (currently draft-status + queue), approval timeout worker
(EXPIRED/CANCELLED states designed), per-tenant CommunicationTemplate table, webhook
ingestion endpoints.

**5. Does ActionGate work?** **Yes — implemented and tested** (ALLOW low-risk;
REQUIRE_HUMAN_APPROVAL for price/contract actions even at L5; BLOCK on opt-out; ABSTAIN on
low confidence).

**6. Does ChannelRouter work?** **Yes — tested**: client preference honored, unavailable
preferred channel falls back, opted-out channels excluded ("any" opt-out blocks everything),
provider failure falls to the fallback channel (retry_count recorded).

**7. Does MessageComposer work?** **Yes — tested**: correct Polish missing-photo message
with upload link; **provably refuses to send prices** (injected "rabat 500 zł" raises
MessageComposeError; follow-up texts asserted digit-free).

**8. Does follow-up execution work?** **Yes — tested**: send → 24h cadence scheduled
durably; duplicate within cooldown rate-limited + audited; business-hours violation deferred
via scheduled workflow; client reply pauses automation.

**9. Does Temporal work or is it mocked?** **Mocked** (schedule + advance_to fire
FollowUpWorkflow — tested). Real Temporal (MIT, v1.31, Postgres self-host, GA worker
versioning) is the ADR-confirmed production choice.

**10. Does Novu work or is it mocked?** **Mocked — and demoted by the ADR.** Research
verdict: Novu community self-host has **tenants and delivery webhooks cloud-only** — wrong
fit. Production = direct provider adapters behind the same protocol. The mock stays valid as
the seam's test double.

**11. Does Chatwoot work or is it mocked?** **Mocked** (handoff conversation with labels +
AI summary as private note — tested). Real Chatwoot (v4.15, MIT core, WhatsApp Cloud/
360dialog verified in source) is ADR-adopted for inbox/handoff; `enterprise/` features
(SAML, audit logs) are paid.

**12. Does upload link generation work?** **Yes — implemented and tested**: SHA-256-hashed
tokens (raw token never stored), 72h TTL, CREATED→SENT→OPENED→USED/EXPIRED/REVOKED, mime +
size enforcement, upload resolves the MissingItem and notifies the loop (E2E scenario 1).

**13. Does human approval work?** **Yes — tested**: pending → approve (with owner edit —
edited text is what sends, both versions stored) → sent; reject → blocked with reason. RBAC
enforcement and timeout expiry are Designed.

**14. Are audit events written?** **Yes — tested** on the shared hash chain: 20+ event
types (ACTION_REQUESTED through UPLOAD_LINK_USED); chain verified in every test.

**15. Is consent/opt-out enforced?** **Yes — tested** at three layers: case-level opt-out
(gate BLOCK), channel-level consent (router exclusion → no_permitted_channel), business
hours (deferral with durable schedule).

**16. Is duplicate follow-up prevented?** **Yes — tested**: cooldown, max attempts, daily
cap, and reply-pause; suppressions are audited (FOLLOW_UP_RATE_LIMITED), never silent.

**17. Is it enterprise-ready?** **No — not production-ready.** Tenancy fields, hashing,
consent, audit, HITL are real; RLS, RBAC, signed webhooks, observability, kill switch,
provider credentials remain (enterprise-controls.md).

**18. What blocks production?** Real providers + credentials (WhatsApp Business
provisioning above all), persistence/API around the tested logic, signed webhook ingestion,
RBAC, observability.

**19. What blocks MVP?** Wiring one real channel (WhatsApp Cloud API or Twilio sandbox) +
one real Temporal deployment behind the existing seams, plus the persistence/API layer
shared with the case-graph module.

**20. How should this connect to Case Graph and Completion Loop?**
Already connected in code: `CompletionLoopService.run_case` selects the action → an
`ActionRequest` feeds `engine.handle` → execution results update the case
(MissingInfoService.resolve on upload, rate-state, next follow-up scheduling) → everything
lands on the same audit chain the timeline reads. The E2E tests exercise exactly this path.

**21. Should LGGT be integrated now or later?** **Later — Option B stands** (docs 32/44).
Phase-1 rule-based ActionGate is live here; every gate decision already returns an
`audit_id`; Phase 2 certifies follow-up permission/safe-send/approval-requirement at the
marked hooks.

**22. What exact next sprint should be done?**
**Provider sprint**: (1) persistence + API for ActionRequest/Draft/Execution/DeliveryEvent/
UploadLink; (2) Meta WhatsApp Cloud API adapter + Twilio fallback behind
`NotificationAdapter` with signed delivery webhooks → `record_delivery`; (3) real Temporal
worker running FollowUpWorkflow + HumanApprovalWorkflow(timeout); (4) Chatwoot AgentBot
handoff against a self-hosted instance; CI gate = existing 185 tests + provider-sandbox
contract tests.

---

## Verified / not verified

**Verified (25 tests)**: gate outcomes ×4 · router preference/fallback/opt-out ·
composer templates + price-guard ×2 · consent block + hours deferral · rate cooldown/pause ·
upload lifecycle incl. expiry + bad mime · Temporal schedule/fire · delivery send/fallback/
status/reply-pause · Chatwoot handoff · approval approve-with-edit/reject · 3 E2E scenarios
· audit completeness + chain integrity.

**Not verified**: anything touching a real network, provider, or credential; concurrency;
webhook signatures; RBAC; timeouts on approvals.

## Top 10 next actions
1. Persistence + `/actions` + `/messages` + `/upload-links` API (contracts ready).
2. WhatsApp Cloud API adapter + Meta business verification + template approvals (start now — longest lead time).
3. Twilio SMS/WA fallback adapter + signed delivery-status webhook endpoint.
4. Real Temporal deployment (Postgres) + FollowUpWorkflow/HumanApprovalWorkflow workers.
5. Chatwoot self-host + AgentBot handoff integration + webhook ingestion.
6. HumanApproval entity + approval timeout worker (EXPIRED) + RBAC enforcement.
7. Per-tenant CommunicationTemplate table + template editor in the Control Center.
8. Observability: the 8 designed metrics emitted from audit events + alerts.
9. Kill switch + per-tenant daily send caps enforcement at the engine entry.
10. Upload service: S3 presigned PUT + AV scan + auto-ingestion into the OCR router.

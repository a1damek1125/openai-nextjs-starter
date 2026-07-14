# ROADMAP-LOCK-1 — Do-Not-Rebuild Execution Map

> **Prime directive: EXTEND EXISTING PRODUCT, DO NOT REBUILD.**
> Every future SP reuses and extends the modules below. Creating a parallel re-implementation of any of them is **forbidden** and must fail code review.

The repository at code HEAD `d95be03` already contains the full product. This document names each existing module, where to extend it, and what a rebuild would look like (so it can be rejected on sight).

---

## Absolute rules

1. **One owner per domain.** Each capability has exactly one owning module. New behavior is added *inside* that module (its engine/store) or *behind its existing seam* (a `*Provider` / `Protocol` interface). Never a second module.
2. **Swap mocks in place.** Every mock is behind a Protocol. Replace the mock implementation; do not fork the engine that calls it.
3. **Governance narrows, never widens.** New TOOL-B layers consume the prior layer's proof and add *more* restriction. No new layer may grant authority a prior layer withheld.
4. **Reuse the shared primitives:** `audit.py` (hash-chained audit), `evidence/transparency.py` (Merkle/consistency), `admin/rbac.py` (access decisions), `governance/runtime.py` (traces/budgets/flags), `ai_employee/*` proof kernels, the canonical-JSON/`_core_hash` hashing helpers.
5. **Extensions ship as configuration or subclass, not copy-paste.** Vertical packs, new providers, new surfaces = config/adapter/subclass over the owning module.

---

## Module-by-module: reuse target, extend here, DO NOT rebuild

### CRM — owner: `finalis/crm/*` + `portal/crm_store.py` (mig v7)
- **Reuse:** parties, contacts, consent (non-overrideable), memory, relationship graph, dedupe/merge, external-sync seam.
- **Extend here:** new relationship types / consent channels via existing enums; external providers via `crm/adapters.py` seam; vertical needs via config.
- **DO NOT:** create `crm2`, a second party/consent model, or a parallel customer store. Slack/Teams/mobile read CRM through existing `/crm` APIs.

### Evidence Trust Fabric — owner: `finalis/evidence/*` + `portal/evidence_store.py` (mig v5,v6,v8)
- **Reuse:** SHA-256 custody chain, Merkle tree + RFC 6962/9162 consistency proofs, content-addressed proof reports, retention/legal-hold, dual view.
- **Extend here:** real AV scanner via `evidence/scanners.py` seam; real KMS/signing/anchoring via new adapter behind existing interfaces; object-store/WORM via `evidence/storage.py` seam; OCR via `ocr_router.py` seam.
- **DO NOT:** create a second evidence store, a second Merkle/transparency implementation, or a parallel report format.

### Case Graph / Completion Loop / Dashboard — owner: `case_services.py`, `completion_loop.py`, `dashboard.py`, `autonomy.py`, `audit.py`
- **Reuse:** CaseGraphService, MissingInfoService, PromiseTrackerService, NextBestActionService, CompletionLoop, DashboardService, autonomy gate, audit chain.
- **Extend here:** CASE-2 upgrades these services in place (completion 2.0, promise 2.0, NBA + autonomy input, owner command center 2.0).
- **DO NOT:** create a second Case Graph, Completion Loop, NBA engine, or Dashboard.

### Scheduling — owner: `finalis/scheduling/*` + `portal/scheduling_store.py` (mig v4)
- **Reuse:** appointment types, availability/slots, double-booking guard, hashed confirm tokens, lifecycle handoff.
- **Extend here:** real calendar/video via `MockCalendarProvider`/`MockVideoMeetingProvider` seams.
- **DO NOT:** create a second scheduling engine or appointment store.

### Telephony — owner: `finalis/telephony/*`
- **Reuse:** call-control engine, permission gate (11 blockers), anti-harassment guard, consent, dispositions.
- **Extend here:** real provider via `TelephonyProvider` Protocol (VOICE-PROD-1 / PILOT-4).
- **DO NOT:** create a second telephony engine or bypass the anti-harassment/consent gates.

### Quote Builder / CPQ — owner: `finalis/quotes/*` + `portal/quote_store.py` (mig v3)
- **Reuse:** CPQ lifecycle, Decimal money math, gates, versioning, change orders, AI-no-self-approve.
- **Extend here:** real PDF/e-signature/invoice via `quotes/providers.py` seam; Offer Comparator + vertical pricing as extensions.
- **DO NOT:** create a second CPQ, pricing engine, or money model. Money stays Decimal-as-TEXT.

### Admin / Tenant / RBAC — owner: `finalis/admin/rbac.py`
- **Reuse:** 9 roles / 45 permissions, deny-by-default (tenant-first), last-owner/escalation/AI-no-self-approve guards, hashed keys.
- **Extend here:** production IAM/SSO/MFA via IAM adapter seams; persist memberships; unify the auth(5)/rbac(9) role vocab (SAAS-1).
- **DO NOT:** create a second RBAC/permission engine or a parallel role catalog.

### Agent Runtime Governance — owner: `finalis/governance/runtime.py`
- **Reuse:** AgentTrace + secret redaction, PolicyEnforcementGate (no bypass), autonomy budgets, shadow mode, feature flags.
- **Extend here:** structured redaction, distributed budgets, real metrics backend (INFRA-3).
- **DO NOT:** create a second policy gate or autonomy budget.

### Voice + Conversation Intelligence — owner: `finalis/voice/*`
- **Reuse:** dialogue policy, evidence-gated fact acceptance, ASR/TTS routing.
- **Extend here:** real ASR/TTS via `MockASR`/`MockTTS` seams; conversation-to-case commit via TOOL-B9.
- **DO NOT:** create a second voice engine or extraction pipeline.

### Action & Communication — owner: `finalis/actions/*`
- **Reuse:** gate→consent→ratelimit→route→compose→approve→send pipeline, forbidden-content patterns, approval queue.
- **Extend here:** real Slack/Teams/email/SMS via `actions/adapters.py` seams (CHAT-*, PILOT-*).
- **DO NOT:** create a second communication pipeline or composer.

### Lifecycle — owner: `finalis/lifecycle/*`, `state_machine.py`, `scoring.py`
- **Reuse:** LifecycleVector, 16-state machine, 11 scoring functions, playbooks.
- **Extend here:** vertical playbooks via `lifecycle/playbooks.py`; LGGT via `certainty_core.py` seam.
- **DO NOT:** create a second state machine, scoring module, or lifecycle vector.

### CORE-A1..A6 + TOOL-B1..B8 — owner: `finalis/ai_employee/*` (mig v9–v23)
- **Reuse:** identity/authority, secure intake, run ledger/replay, approval gate, lifecycle kernel, artifacts, tool registry/quality/contract/pre-action/broker/runtime/write-intent/commit-sim.
- **Extend here:** TOOL-B9+ consume these proofs and narrow further; Autonomy Level Engine (B13) formalizes `min(...)` over existing gates.
- **DO NOT:** fork any kernel; duplicate the proof-bundle/dominance pattern into a parallel module (REFACTOR-3 will factor a shared base instead).

### Portal / Auth / DB / UI — owner: `finalis/portal/*`
- **Reuse:** FastAPI app, PBKDF2 auth, HMAC token, tenant-scoped stores, server-rendered UI, migration ledger.
- **Extend here:** production auth (SAAS-1); Postgres (INFRA-1); router/UI decomposition (REFACTOR-1/2) — behavior-preserving.
- **DO NOT:** create a second app/auth/db/ui; add a duplicate migration version; break v1→vN monotonicity.

---

## Rebuild red flags (reject in review)
- A new file/module whose name mirrors an existing domain (`crm2`, `evidence_v2`, `new_scheduler`, `case_graph_new`, `rbac2`).
- A second migration table for an existing concept.
- A provider call that does not pass through the module's existing Protocol seam (post-ADAPTER-1: through the provider boundary).
- A new proof/dominance kernel that copies an existing TOOL-B kernel instead of extending/sharing it.
- Any surface (Slack/Teams/mobile/voice) embedding business logic instead of calling the server-authoritative APIs.

## Surfaces are thin clients
Slack, Teams, mobile, workbench, and voice are **presentation + capture + approval-relay** only. All decisions, policy, commit, and authority stay in the governed server core. This is what prevents surface proliferation from becoming module proliferation.

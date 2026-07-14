# ROADMAP-LOCK-1 — Finalis AI Employee OS Versioned Roadmap and Do-Not-Rebuild Execution Map

> **Mission type:** DOCS ONLY / ROADMAP ONLY. No product code, tests, migrations, routes or runtime behavior changed by this document.
> **Status:** This roadmap is the **mandatory execution map**. No further coding SP may start unless it conforms to this document (dependencies, do-not-rebuild rules, and "not allowed yet" gates).
> **Branch:** `claude/finalis-ai-casewoker-blueprint-f1huse` · **Doc HEAD:** `4e39dd8` · **Code HEAD:** `d95be03` (TOOL-B8 v5) · **Migration:** v23 · **Tests:** 4601 non-browser passed, 0 failed.
> **Next coding SP after this roadmap:** **TOOL-B9**.

---

## 0. Prime Directive

**EXTEND EXISTING PRODUCT, DO NOT REBUILD.**

The repository already contains the entire product (see Block A). Every SP below **reuses and extends** the existing modules. It is **forbidden** to create a second CRM, Evidence, Case Graph, Scheduling, Telephony, CPQ, or Admin/RBAC. New capability is added *behind the existing seams* (Protocol interfaces, stores, engines) — never as a parallel re-implementation. See `ROADMAP_LOCK_1_DO_NOT_REBUILD.md`.

## 0.1 Core governance rules (invariant across every SP)

```
ActionAllowed =
  IdentityTrust × RolePermission × TenantScope × SegmentPolicy × ObjectPolicy
  × ConsentPolicy × EvidenceVerdict × RiskGate × HumanApproval × ToolSafety
  × RuntimeTraceCompliance × NoAuthorityLeak

LocalCommitAllowed =
  B8EnvelopeVerifiedAsEvidenceOnly × B9FullRevalidationPassed × ActorAuthorized
  × TenantScopeValid × LocalWriteScopeValid × IdempotencyKeyValid
  × ReversibleStateAvailable × EmergencyAbortAvailable × CommitAttestationReady
  × NoExternalSurface

AllowedAutonomyLevel =
  min(RoleAutonomyLimit, TenantPolicyLimit, SegmentPolicyLimit, ToolRiskLimit,
      EvidenceConfidenceLimit, HumanApprovalLimit, HistoricalTrustLimit)
```

Non-negotiable principles (enforced by tests in every SP that touches them):
- **Documents provide facts, never commands.**
- **Scores recommend; policy decides.**
- **Push notification is NOT approval.**
- **Mobile cached data is NOT authoritative.**
- **Artifact is NOT authority.**
- **A B8 envelope is EVIDENCE ONLY, never B9 authority** — B9 must recompute every factor and reject B8 artifacts as authority.

## 0.2 SP status legend
`DONE` (implemented+tested) · `NEXT` (immediately actionable) · `PLANNED` (scheduled, deps unmet) · `BLOCKED_CREDENTIALS` · `BLOCKED_PROVIDER` · `DO_NOT_BUILD_YET` (explicitly gated).
Per-item classification legend: **IMPLEMENTED / MOCKED / SCAFFOLDED / MISSING / BLOCKED**.

---

## Block A — Baseline / Product Inventory Lock  *(status: LOCKED by this doc + AUDIT-REPORT-1)*

### A.1 Product inventory lock (what exists TODAY — reuse targets)

| Module | Source | Routes | Migration | Classification |
|---|---|---|---|---|
| Portal + Case Command Center | `portal/{app,db,ui,auth,seed}.py`, `dashboard.py` | `/auth`,`/cases`,`/dashboard` | v1 | IMPLEMENTED (dev-grade auth) |
| Universal Lifecycle | `lifecycle/*`, `state_machine.py`, `scoring.py`, `completion_loop.py` | `/cases/*/lifecycle`,`/completion-loop` | v2 | IMPLEMENTED (certainty_core = SCAFFOLD seam) |
| Quote Builder / CPQ | `quotes/*`, `portal/quote_store.py` | `/quotes`,`/price-books`,`/pricing*` | v3 | IMPLEMENTED + MOCKED (PDF/sign/invoice) |
| Scheduling | `scheduling/*`, `portal/scheduling_store.py` | `/scheduling`,`/confirm` | v4 | IMPLEMENTED + MOCKED (calendar/video) |
| Evidence Trust Fabric | `evidence/*`, `portal/evidence_store.py` | `/evidence` (40) | v5,v6,v8 | IMPLEMENTED (real crypto) + MOCKED (scanner) + BLOCKED (WORM/anchor) |
| Relationship CRM | `crm/*`, `portal/crm_store.py` | `/crm` (25) | v7 | IMPLEMENTED (+ SCAFFOLD external sync) |
| Telephony | `telephony/*` | `/telephony` | (portal) | MOCKED (provider_is_mock) |
| Voice + Conversation Intelligence | `voice/*` | via `/cases/*/transcripts`,`/analyze-conversation` | — | IMPLEMENTED logic + MOCKED (ASR/TTS) |
| Action & Communication | `actions/*` | `/actions`,`/upload-links` | — | MOCKED (Novu/Chatwoot/Temporal) |
| Case Graph / Completion / Dashboard | `case_services.py`,`completion_loop.py`,`dashboard.py`,`webscout.py`,`documents.py`,`ocr_router.py`,`autonomy.py`,`audit.py` | `/cases`,`/completion-loop`,`/dashboard`,`/audit` | — | IMPLEMENTED + MOCKED (WebScout/OCR) |
| Admin / Tenant / RBAC | `admin/rbac.py` | `/admin` | v1 | IMPLEMENTED (in-memory membership) |
| Agent Runtime Governance | `governance/runtime.py` | `/governance` | — | IMPLEMENTED (in-memory, regex redaction) |
| CORE-A1..A6 | `ai_employee/{identity,authority,tasks,run_ledger,approvals,lifecycle,artifacts}.py` | `/ai-employees`,`/ai-tasks`,`/ai-runs`,`/ai-approvals`,`/ai-artifacts` | v9–v15 | IMPLEMENTED |
| TOOL-B1..B8 | `ai_employee/tool_{registry,quality,contracts,guardrails,broker,runtime,write_intent,commit_simulation}.py` | `/ai-tools/*` (120) | v16–v23 | IMPLEMENTED (proof-carrying, non-executing) |

### A.2 Mock inventory (must be swapped, never re-built)
Telephony provider · email/SMS (NovuMock) · handoff (ChatwootMock) · durable workflow (TemporalMock) · calendar · video · PDF renderer · invoice handoff · ASR/TTS · WebScout fetch · OCR engines · malware scanner. All self-labelled `is_mock=True` / `provider_is_mock` / `*Mock`, behind Protocol seams. **Swap in place; do not duplicate the owning module.**

### A.3 Scaffold inventory (declared placeholders)
Real write/commit runtime (arrives as TOOL-B9) · e-signature (raises `NotImplementedError`) · native WORM (capabilities all-false) · external CRM sync adapters · `certainty_core` LGGT (NullAdapter) · IAM adapter seams.

### A.4 Technical debt lock (address in Block P, not before B13)
`portal/app.py` (10,083 LOC), `portal/ui.py` (3,691 LOC) monoliths · TOOL-B kernel/test duplication (`ai_employee/tool_*.py`, `tests/_bN_kernel.py`) · test↔model implementation coupling · two role vocabularies (auth 5 vs rbac 9) · in-memory RBAC/governance state.

### A.5 Do-not-rebuild rules (summary — full list in dedicated doc)
1. Extend the owning module's engine/store; never fork it.
2. Add new providers behind the existing `*Provider`/`FetcherProtocol`/`OCREngineProtocol` seams.
3. New governance never widens B1→B8 authority; new layers narrow further.
4. Reuse `audit.py` hash chain, `evidence/transparency.py` Merkle, `admin/rbac.py`, `ai_employee/*` proof kernels.

---

## Block B — TOOL-B9: Controlled Internal Commit Runtime  *(status: NEXT)*

**SP: TOOL-B9** · **Purpose:** first layer permitted to perform a **real but strictly local, reversible** write, gated by full re-validation of the B8 envelope (as evidence only).
- **Existing modules reused:** `tool_commit_simulation.py` (B8 envelope + non-delegable seal + B9 negative-capability contract + B9 revalidation contract), `tool_write_intent.py` (escrow), `audit.py` (hash chain), `ai_employee/run_ledger.py`, `admin/rbac.py`, portal stores.
- **New scope:** effector-exclusive gate (single-writer local state); local reversible commit against real domain rows (behind a reversible journal); commit attestation record (hash-chained); emergency abort / kill-switch; deterministic rollback; enforce `LocalCommitAllowed` (all 10 factors recomputed, B8 artifacts rejected as authority).
- **Dependencies:** TOOL-B8 (DONE).
- **Not allowed:** external providers, MCP/LLM, tokens/credentials, payment/CRM-external/evidence-external mutation, message send, export; no endpoint that commits to anything but local reversible state; B8 envelope may not authorize anything.
- **Test requirements:** fault-injection harness proving no external effect escapes; rollback-restores-state proof; idempotency/duplicate-commit block; emergency-abort test; cross-tenant/RBAC; commit-attestation determinism; "B8 envelope is not authority" negative test.
- **Mobile / Slack/Teams:** none (governance core).
- **Production readiness impact:** unlocks the *local* commit primitive all later effect layers depend on. Classification: **new = MISSING→IMPLEMENTED (local); external commit = still MISSING by design.**

---

## Block C — TOOL-B10: Commit Recovery & Observability  *(status: PLANNED, dep B9)*

**SP: TOOL-B10** · **Purpose:** make local commits crash-safe and observable.
- **Reused:** B9 commit runtime, `run_ledger.py`, `audit.py`, `governance/runtime.py` (metrics seam), portal event ledgers.
- **New scope:** restart recovery (replay uncommitted/committing journal to a consistent state); duplicate-prevention across restarts (durable idempotency keys); stuck-commit detector (timeout + quarantine); commit metrics + rollback metrics (counts, latencies, abort rate) surfaced read-only.
- **Deps:** TOOL-B9.
- **Not allowed:** external effects; production metrics backends (local metrics only until INFRA-3).
- **Tests:** kill-mid-commit recovery; duplicate-suppression after restart; stuck-commit quarantine; metrics determinism.
- **Prod impact:** commit runtime becomes durable. **new = MISSING→IMPLEMENTED (local).**

---

## Block D — Employee Control Plane  *(status: PLANNED, dep B10)*

**SP: TOOL-B11 — Employee Work Inbox + Run Ledger 2.0**
- **Reused:** `ai_employee/tasks.py` (intake), `run_ledger.py` (A3), `approvals.py`, `dashboard.py`.
- **New scope:** a per-employee **Work Inbox** (assigned/queued/blocked/awaiting-approval work items over existing tasks) + **Run Ledger 2.0** (richer causal event views, no schema fork — extend the A3 ledger). Read + human actions only.
- **Deps:** B10. **Not allowed:** autonomous execution; second task store.
- **Tests:** inbox derivation from existing tasks; RBAC/tenant; no-execution.
- **Prod impact:** operator visibility. **new = MISSING→IMPLEMENTED.**

**SP: TOOL-B12 — Employee Work Graph + Outcome Contract Engine**
- **Reused:** `case_services.py` (Case Graph), `lifecycle/*`, artifacts.
- **New scope:** work graph linking employee→task→case→artifact→commit; **Outcome Contract Engine** (declare expected outcome + acceptance criteria per work item, verified against evidence — extends the Quote/CRM promise model, does not replace it).
- **Deps:** B11, Case Graph. **Not allowed:** rebuilding Case Graph.
- **Tests:** graph integrity; outcome-contract acceptance only on evidence; cross-tenant.
- **Prod impact:** measurable outcomes. **new = MISSING→IMPLEMENTED.**

**SP: TOOL-B13 — Autonomy Level Engine**
- **Reused:** `autonomy.py` (L1–L5 gate), `governance/runtime.py` (budgets/flags), `admin/rbac.py`.
- **New scope:** formalize `AllowedAutonomyLevel = min(...)` as a single authoritative engine consumed by B4–B12; per-tenant/segment/role/tool/evidence caps; historical-trust input.
- **Deps:** B12. **Not allowed:** raising autonomy above human-approval limit; second autonomy gate.
- **Tests:** min-of-limits proof; approval-limit dominance; downgrade-on-low-trust.
- **Prod impact:** governs every future effect layer. **new = MISSING→IMPLEMENTED.**

---

## Block E — Evaluation Lab  *(status: PLANNED, can start partial after B9)*

**SP: EVAL-1 — Finalis Evaluation Lab**
- **Reused:** all test infra (`tests/`, `_bN_kernel.py`), fault harnesses, red-team corpora already embedded in B4–B8.
- **New scope:** golden-task suite (business benchmarks per worker type); unsafe-action tests; prompt-injection corpus; **artifact-as-authority** tests; cross-tenant matrix; regression gate wired to CI. Consolidates existing negative tests into a labeled benchmark, not new product code.
- **Deps:** B9 (for commit-path evals); expands as later SPs land.
- **Not allowed:** weakening or deleting existing tests.
- **Tests:** the lab *is* tests; must be deterministic, no network.
- **Prod impact:** measurable safety/quality bar. **new = MISSING→IMPLEMENTED.**

---

## Block F — Governed Cloud Workbench  *(status: PLANNED, dep B10 + EVAL-1)*

**SP: WORKBENCH-1 — Governed Cloud Workbench (sandbox)**
- **Reused:** `governance/runtime.py` (AgentTrace, shadow mode, budgets), B6 read-only runtime, B9/B10 commit runtime, evidence access gates.
- **New scope:** an isolated sandbox where an employee's proposed actions are **recorded (action recorder)**, output is **reviewable** before any commit, and a **browser/web sandbox** runs read-only research (reusing WebScout seam). No secrets in sandbox; no uncontrolled external effects (all effects route through B4→B9 gates).
- **Deps:** B10, EVAL-1. **Not allowed:** real browser automation with credentials; external effect from sandbox.
- **Tests:** recorder completeness; no-secret-in-sandbox; effect-must-pass-gates; shadow-only default.
- **Mobile:** exposes reviewable output via mobile API (see Block G). **Prod impact:** safe human-in-the-loop surface. **new = MISSING→SCAFFOLDED→MOCKED (browser mock first).**

---

## Block G — Mobile iOS/Android  *(status: PLANNED, dep control plane)*

**SP: MOBILE-1 — Mobile API contracts + PWA shell**
- **Reused:** existing REST endpoints (`/cases`,`/ai-approvals`,`/dashboard`,`/crm`,`/evidence`), `auth.py`.
- **New scope:** stable versioned mobile API contract (read + approval actions); responsive PWA/mobile-web shell over existing APIs.
- **Deps:** TOOL-B11 (inbox). **Not allowed:** treating mobile cache as authoritative; push as approval.
- **Tests:** contract stability; RBAC/tenant on every mobile route; "cached data not authoritative" negative test.
- **Mobile requirements:** offline-read allowed, offline-authoritative-write forbidden.
- **Prod impact:** operator reach. **new = MISSING→SCAFFOLDED.**

**SP: MOBILE-2 — Native iOS/Android scaffold + push approval + evidence capture + offline draft**
- **Reused:** MOBILE-1 contracts, `evidence/*` upload gateway (Block I), approvals.
- **New scope:** native app scaffolds; push-approval flow (notification opens a **server-authoritative** approval screen — push itself is never approval); mobile evidence capture (photo→upload gateway); offline **draft** mode (drafts sync, never auto-commit).
- **Deps:** MOBILE-1, EVID-PROD-1, CHAT (optional). **Not allowed:** approving from the push payload; offline commit.
- **Tests:** push-is-not-approval; offline-draft-never-commits; evidence-capture chain-of-custody.
- **Mobile requirements:** all of the above. **Prod impact:** field workforce. **new = MISSING→SCAFFOLDED.**

---

## Block H — Case Completion Layer  *(status: PLANNED, dep B12 — EXTEND, do not rebuild)*

**SP: CASE-2 — Case Completion Engine 2.0**
- **Reused (EXTEND, NOT REBUILD):** `case_services.py` (CaseGraphService, MissingInfoService, PromiseTrackerService, NextBestActionService), `completion_loop.py`, `dashboard.py` (Owner Command Center).
- **New scope:** consolidate Case Graph; Completion Loop Engine 2.0 (durable scheduling via B10 recovery); Promise Tracker 2.0 (evidence-bound, CRM-linked); Missing-Information Hunter upgrades; NBA Engine with Autonomy Level Engine input; Owner Command Center 2.0 (richer dashboard). All as extensions of the existing services.
- **Deps:** TOOL-B12, TOOL-B13, TOOL-B10.
- **Not allowed:** a second Case Graph / second Completion Loop / second Dashboard.
- **Tests:** extend existing case/dashboard suites; completion invariants preserved; no-duplication assertions.
- **Prod impact:** the core "get the case done" loop. **existing = IMPLEMENTED → extended IMPLEMENTED.**

---

## Block I — Evidence Production Hardening  *(status: PLANNED — EXTEND evidence/)*

**SP: EVID-PROD-1 — Evidence Production Lifecycle**
- **Reused (EXTEND):** `evidence/*` (chain, Merkle transparency, reports, storage, immutability), `evidence_store.py`.
- **New scope:** production lifecycle states; **secure upload gateway** (streaming, size/type enforcement, quarantine before scan); AI-safe evidence access (extend dual-view + AI-access-decision); **KMS/signing/anchoring PREP** (interfaces + local signer, real KMS gated to ADAPTER/credential layer); document-intelligence router upgrades (extend `ocr_router.py`).
- **Deps:** ADAPTER-1 (for real KMS/AV), INFRA-2 (object store/WORM).
- **Not allowed:** claiming external anchoring before it is wired; second evidence store.
- **Tests:** upload-gateway hardening; signing-prep determinism; access-gate; retention/legal-hold preserved.
- **Prod impact:** evidence approaches audit-grade. **existing IMPLEMENTED + new SCAFFOLDED→(BLOCKED_PROVIDER for KMS/anchor).**

---

## Block J — External Adapter & Credential Layer  *(status: PLANNED — the HARD GATE before any real provider)*

**SP: ADAPTER-1 — Provider Boundary + Credential Capability Model**
- **Reused:** all existing `*Provider`/Protocol seams (telephony, calendar, video, PDF, sign, Novu, Chatwoot, OCR, ASR/TTS, scanner, CRM sync), `governance/runtime.py`.
- **New scope:** a single **provider boundary** through which every external call must pass; a **credential capability model** (scoped, least-privilege, per-tenant, never exposed to the agent); MCP/LLM/provider **simulation** harness (still no real calls); production-readiness hardening checklist per provider.
- **Deps:** TOOL-B9/B10 (commit + observability), TOOL-B13 (autonomy caps).
- **Not allowed:** any real external call yet; credentials in traces/artifacts/prompts; provider bypass of B4→B9 gates.
- **Tests:** every provider call routes through the boundary; credential never leaks to agent/artifact/trace; simulation parity.
- **Prod impact:** the switch that makes real providers *possible* — but still off. **new = MISSING→MOCKED (simulation).**

---

## Block K — Slack & Teams  *(status: PLANNED, dep ADAPTER-1)*

**SP: CHAT-1 — Conversation Contract + Slack app scaffold + approval cards**
- **Reused:** `actions/*` (channel router, composer, approval queue), approvals, control plane.
- **New scope:** a channel-agnostic **conversation contract**; Slack app scaffold (events, slash, interactivity); Slack **approval cards** (server-authoritative — the card click opens a verified approval, not an implicit grant).
- **Deps:** ADAPTER-1, TOOL-B11. **Not allowed:** treating a Slack action as approval without server re-check; Slack executing effects directly.
- **Tests:** conversation-contract; card-click-is-not-approval; tenant mapping; injection over Slack text.
- **Slack/Teams requirements:** Slack scaffold + cards. **Prod impact:** first chat surface. **new = MISSING→SCAFFOLDED.**

**SP: CHAT-2 — Teams app scaffold + adaptive approval cards**
- Mirror of CHAT-1 for Microsoft Teams (adaptive cards). Deps: CHAT-1. Same rules/tests. **new = MISSING→SCAFFOLDED.**

---

## Block L — Real Provider Pilots  *(status: BLOCKED_CREDENTIALS / BLOCKED_PROVIDER — DO_NOT_BUILD_YET until deps)*

**SP: PILOT-1 Slack · PILOT-2 Teams · PILOT-3 Email/Calendar · PILOT-4 Telephony/SMS/WhatsApp**
- **Reused:** ADAPTER-1 boundary, credential model, CHAT-1/2, `actions/*`, `telephony/*`, `scheduling/*`.
- **New scope:** wire ONE real provider at a time behind the boundary, gated by B4→B9 + autonomy caps + human approval; start in shadow, then limited live with kill-switch.
- **Deps:** ADAPTER-1, EVID-PROD-1, SAAS auth hardening, credential vault (INFRA), EVAL-1 green.
- **Not allowed:** more than one provider live at once before its pilot passes; bypassing approval/consent/anti-harassment gates; any provider before ADAPTER-1.
- **Tests:** shadow-parity vs mock; kill-switch; rate/consent/anti-harassment enforced live; abuse tests.
- **Prod impact:** first real external effects. **new = MOCKED→BLOCKED→(pilot) IMPLEMENTED per provider.**

---

## Block M — Voice Production Layer  *(status: PLANNED, dep ADAPTER-1 + B9)*

**SP: VOICE-PROD-1 — Voice Production Boundary**
- **Reused (EXTEND):** `voice/*` (engine, extractor, conversation_intelligence, routers), `telephony/*`.
- **New scope:** real ASR/TTS/telephony behind ADAPTER-1; voice-quality engine; **conversation-to-case commit** (a verified transcript commits case facts via TOOL-B9, evidence-gated).
- **Deps:** ADAPTER-1, TOOL-B9, EVID-PROD-1. **Not allowed:** committing uncertain facts (min-confidence rule preserved); second voice engine.
- **Tests:** ASR/TTS boundary parity; conversation-to-case commit is reversible + evidence-gated; low-confidence→human review.
- **Prod impact:** voice becomes a real intake channel. **existing IMPLEMENTED logic + new BLOCKED_PROVIDER→pilot.**

---

## Block N — Vertical Worker Packs  *(status: PLANNED, dep control plane + autonomy)*

**SP: PACK-1..7 — Worker Packs (EXTEND existing playbooks/quotes/webscout)**
- PACK-1 Home Services/HVAC/installers playbook (extend `lifecycle/playbooks.py`), PACK-2 Sales Worker, PACK-3 Support Worker, PACK-4 Operations Worker, PACK-5 Finance Worker, PACK-6 Evidence/Compliance Worker, PACK-7 WebScout Worker; Quote Builder extension + Offer Comparator (extend `quotes/*`).
- **Reused:** lifecycle playbooks, quotes engine, CRM, case graph, autonomy engine, evidence.
- **New scope:** per-vertical task templates, outcome contracts, autonomy caps, NBA tuning — as configuration/extension, not new engines.
- **Deps:** TOOL-B13, CASE-2. **Not allowed:** a second CPQ / second CRM / second playbook engine; hard-coding a vertical into the core.
- **Tests:** each pack's golden tasks in EVAL-1; autonomy caps per pack; no-duplication.
- **Prod impact:** sellable worker roles. **existing IMPLEMENTED + extension.**

---

## Block O — SaaS & Production Hardening  *(status: PLANNED, dep INFRA + ADAPTER)*

**SP: SAAS-1 — Production Auth/IAM + Tenancy + Billing + Onboarding + Compliance Center**
- **Reused (EXTEND):** `admin/rbac.py`, `portal/auth.py`, tenants/users tables, governance observability.
- **New scope:** production auth/IAM (JWT/OIDC/SSO/MFA, secret manager, login rate-limit, token revocation); seats/roles/plans; billing/usage metering; onboarding wizard; enterprise compliance center (audit export, DPA, retention config).
- **Deps:** INFRA-1 (Postgres), ADAPTER-1 (secret manager). **Not allowed:** a second RBAC engine; storing secrets in app config.
- **Tests:** SSO/MFA flows; tenant seat limits; billing metering; compliance export; unify auth(5)/rbac(9) role vocab.
- **Prod impact:** multi-tenant SaaS readiness. **existing IMPLEMENTED (dev) → IMPLEMENTED (prod).**

---

## Block P — Refactor & Technical Debt  *(status: PLANNED, dep B13 stabilized)*

**SP: REFACTOR-1 app.py modularization · REFACTOR-2 ui.py modularization · REFACTOR-3 domain-boundary + common kernel/test-helper cleanup**
- **Reused:** everything; behavior-preserving only.
- **New scope:** split `portal/app.py` (10,083 LOC) into per-domain routers; modularize `portal/ui.py` (3,691 LOC) per section; shared base for TOOL-B kernels + `tests/_bN_kernel.py`; unify role vocab.
- **Deps:** TOOL-B line stabilized (post-B13) so kernel shape is final. **Not allowed:** behavior change; test weakening; doing this mid-B-line.
- **Tests:** full suite must stay green (4601+); no route/behavior diff (route-topology diff = clean).
- **Prod impact:** maintainability. **existing → refactored, no functional change.**

---

## Block Q — Production Infrastructure  *(status: PLANNED, dep ADAPTER/credential)*

**SP: INFRA-1 PostgreSQL migration · INFRA-2 Object storage / WORM provider · INFRA-3 Observability stack · INFRA-4 Deployment runbook**
- **Reused:** existing stores (portable SQL already written), evidence storage seam, governance metrics seam.
- **New scope:** SQLite→Postgres (connection/driver swap per `db.py` docstring); local-FS→object store + S3 Object-Lock WORM (unblocks EVID-PROD anchoring); metrics/tracing/alerting; deploy/rollback/secrets runbook.
- **Deps:** ADAPTER-1 (credentials), REFACTOR (recommended). **Not allowed:** premature Postgres before schema/tests stable; two storage layers.
- **Tests:** migration parity (same tests green on Postgres); WORM enforcement; observability smoke.
- **Prod impact:** the persistence/immutability/observability floor. **MOCKED/local → IMPLEMENTED (prod).**

---

## Block R — Final Gates  *(status: PLANNED, terminal)*

**SP: GATE-1 Production Readiness Audit · GATE-2 Red-Team/Abuse · GATE-3 Limited Beta Gate · GATE-4 Production Candidate Gate**
- **Reused:** EVAL-1, AUDIT-REPORT format, all fault harnesses.
- **New scope:** full production-readiness audit vs this roadmap; adversarial red-team/abuse pass; limited-beta entry criteria; production-candidate sign-off.
- **Deps:** all prior blocks for the surfaces in scope. **Not allowed:** declaring production-ready without GATE-4 pass.
- **Tests:** the gates are test/audit gates. **Prod impact:** go/no-go. **terminal.**

---

## Execution ordering (critical path)

```
A (lock) → B9 → B10 → B11 → B12 → B13 ─┬─→ EVAL-1 ──→ WORKBENCH-1 ──→ MOBILE-1 → MOBILE-2
                                        ├─→ CASE-2
                                        └─→ ADAPTER-1 ─┬─→ EVID-PROD-1 → (KMS/anchor)
                                                       ├─→ CHAT-1 → CHAT-2 → PILOT-1..4
                                                       ├─→ VOICE-PROD-1
                                                       └─→ PACK-1..7
INFRA-1 → INFRA-2 (unblocks EVID-PROD anchoring/WORM) → INFRA-3 → INFRA-4
REFACTOR-1..3 (after B13, parallel-safe, behavior-preserving)
SAAS-1 (needs INFRA-1 + ADAPTER-1)
GATE-1..4 (terminal, per surface)
```

**Hard gates (do NOT cross early):**
- No real provider before **ADAPTER-1** + **B9** + autonomy caps (**B13**) + auth hardening (**SAAS-1**).
- No production deploy before **INFRA-1..4** + **REFACTOR** + **GATE-4**.
- No external evidence anchoring claim before **INFRA-2** + KMS credential.
- No second copy of any Block-A module, ever.

See `ROADMAP_LOCK_1_SP_SEQUENCE.json` (machine-readable), `ROADMAP_LOCK_1_DO_NOT_REBUILD.md`, `ROADMAP_LOCK_1_PRODUCTION_GAPS.md`, `ROADMAP_LOCK_1_NEXT_20_SP.md`.

---

## The path to a real AI employee in Slack / Teams / Workbench / Web / iOS-Android

The **same governed core** (CORE-A + TOOL-B1..B13) drives every surface; surfaces are thin, server-authoritative clients:

1. **Web / Workbench** (Block F): governed sandbox + reviewable output — first place a human watches the employee work. Reuses B6 read + B9 commit.
2. **Slack / Teams** (Blocks K, L): conversation contract + approval cards; the chat surface *proposes and notifies*, the server *decides and commits*. A card click is never an implicit grant.
3. **Web app**: existing portal UI (Block A) extended per Block P/O.
4. **iOS / Android** (Block G): PWA then native; push opens a server-authoritative approval; capture feeds the evidence gateway; offline is draft-only. Mobile cache is never authoritative.
5. **Voice / Telephony** (Block M): a real call becomes evidence-gated case facts committed via B9.

Across all five: **push ≠ approval, cache ≠ authority, artifact ≠ authority, B8 envelope ≠ B9 authority, document = facts not commands, score recommends / policy decides.** The employee is "real" when it can *do work end-to-end across these surfaces under human-governed, reversible, audited local commit* — which is exactly what B9→B13 + ADAPTER-1 + the surface SPs deliver, one gated step at a time.

# AUDIT-TRACE-1 — MASTER (complete, self-contained audit)

> **One document, everything in one place.** This master consolidates the whole
> AUDIT-TRACE-1 audit: repository truth, a **1:1 mapping of all 107 commits**,
> the SP status matrix, architecture, API/UI/data model, production gaps,
> do-not-rebuild, historical-claim verification, and the current true baseline.
> It is a **superset** of the eight companion files in `docs/audit/`; those
> remain as focused views, this is the exhaustive single source.
>
> **Audit-only.** No runtime, test, or product code was changed. The audit added
> only `docs/audit/*`. Every claim is anchored to a commit / file / migration /
> route / test. Repository is the sole source of truth; prior reports, prompts,
> and docs were treated as claims to verify, not as facts.

---

## 0. Repository truth (verified)

| Field | Value |
|---|---|
| Repository | `a1damek1125/openai-nextjs-starter` |
| Branch | `claude/finalis-ai-casewoker-blueprint-f1huse` |
| HEAD (this audit) | `4ea9f55` — *docs(audit): add AUDIT-TRACE-1 …* |
| HEAD (audited runtime) | `135de7b` — *EMP-A1 v1: resolve remaining name collisions with B7 write-intent block* |
| Remote sync | IN SYNC with `origin` |
| Working tree | CLEAN |
| Total commits | **107** (106 runtime + 1 audit commit) |
| Earliest commit | `c2e86a7` (2023-08-17, upstream Next.js starter — inert history) |
| First Finalis commit | `1a57c7f` (2026-07-07) |
| Python | 3.11.15 |
| Latest migration | **v27** (contiguous v1–v27); next = v28 |
| `CREATE TABLE` count | 108 |
| API routes | 402 (`@app.{get,post,put,delete,patch}` in one `create_app()`) |
| UI section registries | 23 (`*_SECTIONS` in `finalis/portal/ui.py`) |
| Test files collected | 398 (browser E2E excluded) |
| Tests collected | 5640 |
| Real outbound network primitives (non-test) | **0** |

**Test result on `135de7b`:** 5640 collected (verified via `--collect-only`);
last full execution on this exact HEAD was **exit 0 / 100% pass** (recorded
immediately before the audit; no code changed since — clean tree, HEAD
unchanged). A fresh re-run during the audit showed **zero failures** in the
completed portion before being stopped (large/slow suite). The exit-0 result is
attributed to the committed state of `135de7b`, not to anything this audit did.

---

## 1. The one-paragraph truth

FinalisAI / ViktorAI is **two products stacked on one Python/FastAPI/SQLite
codebase**: (1) a **fully-tested vertical SaaS** for case / voice / quote /
evidence / CRM work in which *every external effect is mocked and openly
labelled as such*, and (2) a **complete, deterministic, proof-carrying
governance kernel** (CORE-A1..A6 → TOOL-B1..B9.2 → EMP-A1) that deliberately
produces **no external effect** and instead emits verifiable proofs, narrowing
authority at every step. The system can **simulate, draft, prove, recover,
observe, and admit** a unit of work — it **cannot yet execute one against the
real world**. That boundary (EMP-A2 handoff consumer / TOOL-B10 external
adapter) is named in the roadmap and **NOT implemented**.

---

## 2. Complete 1:1 commit → SP mapping (all 107 commits, oldest → newest)

Legend for role: **[SP]** primary SP-bearing commit · **[HARDEN]** fix/hardening
of the SP above · **[TEST]** test suite for the SP above · **[DOC]**
documentation/report · **[BASE]** inert upstream base.

| # | Commit | Date | SP / group | Role | Subject (abridged) |
|---|---|---|---|---|---|
| 1 | `c2e86a7` | 2023-08-17 | (upstream Next.js) | BASE | Initial commit |
| 2 | `d9b6c0c` | 2023-08-17 | (upstream Next.js) | BASE | Update README |
| 3 | `7958a8d` | 2023-08-17 | (upstream Next.js) | BASE | Add files via upload |
| 4 | `5fb37de` | 2023-08-17 | (upstream Next.js) | BASE | Update README |
| 5 | `cb7bed4` | 2023-08-17 | (upstream Next.js) | BASE | Add files via upload |
| 6 | `0511200` | 2023-08-17 | (upstream Next.js) | BASE | Add files via upload |
| 7 | `e4f1ab5` | 2023-08-17 | (upstream Next.js) | BASE | Update README |
| 8 | `1a57c7f` | 2026-07-07 | DOCS-BLUEPRINT | DOC | Add Finalis AI blueprint (docs 1–20) |
| 9 | `873132a` | 2026-07-07 | DOCS-BLUEPRINT | DOC | SOTA technology review (doc 21) + exec summary |
| 10 | `3c6be47` | 2026-07-07 | DOCS-BLUEPRINT | DOC | 90-day sprint plan + acceptance criteria |
| 11 | `3491deb` | 2026-07-07 | DOCS-BLUEPRINT | DOC | API design + event model (doc 22) |
| 12 | `15a50c6` | 2026-07-07 | DOCS-BLUEPRINT | DOC | Red-team fixes (batch 1) |
| 13 | `d882484` | 2026-07-07 | DOCS-BLUEPRINT | DOC | Red-team fixes batch 2 |
| 14 | `b123913` | 2026-07-07 | DOCS-BLUEPRINT | DOC | Red-team fixes batch 3 |
| 15 | `87885b9` | 2026-07-07 | DOCS-BLUEPRINT | DOC | Red-team fixes cleanup |
| 16 | `c18163d` | 2026-07-07 | DOCS-BLUEPRINT | DOC | Red-team: MCP/OCR tech-stack updates |
| 17 | `6bde6c9` | 2026-07-07 | DOCS-BLUEPRINT | DOC | Red-team batch 4: autonomy ladder alignment |
| 18 | `5882999` | 2026-07-07 | DOCS-BLUEPRINT | DOC | Fix data-model cross-refs |
| 19 | `5f937b8` | 2026-07-07 | DOCS-BLUEPRINT | DOC | Production readiness audit (docs 26–36) + OpenAPI skeleton |
| 20 | `8071a54` | 2026-07-07 | **SCAFFOLD-1** | SP | Executable scaffold: state machine, 12 scoring, autonomy, audit chain, completion loop (102 tests) |
| 21 | `0e9d116` | 2026-07-07 | SCAFFOLD-1 | DOC | Readiness reports 41–44 |
| 22 | `2979cd6` | 2026-07-07 | SCAFFOLD-1 | DOC | Verification reports 38–40 |
| 23 | `44e128a` | 2026-07-07 | SCAFFOLD-1 | DOC | Enterprise readiness audit (doc 37, 45) |
| 24 | `a8e15a7` | 2026-07-07 | **VOICE-ENGINE** | SP | Voice Engine open core (26 tests); ASR/TTS = mock seams |
| 25 | `734d8a0` | 2026-07-07 | VOICE-ENGINE | DOC | Founder/CTO report |
| 26 | `7fce077` | 2026-07-07 | VOICE-ENGINE | DOC | Docs: architecture/stack/data-model/API |
| 27 | `1428037` | 2026-07-07 | (repo hygiene) | DOC | Add `.gitignore` |
| 28 | `59769b9` | 2026-07-07 | VOICE-ENGINE | DOC | Docs: README/architecture/stack decision |
| 29 | `94420b0` | 2026-07-07 | VOICE-ENGINE | DOC | Docs: eval harness/enterprise controls/backlog |
| 30 | `47cb24e` | 2026-07-07 | **CASE-GRAPH** | SP | Case Graph service layer + NBA + 4-outcome ActionGate + CompletionLoop (23-step E2E) |
| 31 | `8379db9` | 2026-07-07 | **CONVERSATION-INTELLIGENCE** | SP | Diarized evidence-bound analysis (11 tests) |
| 32 | `3f5e6d3` | 2026-07-07 | CASE-GRAPH | DOC | Founder/CTO report |
| 33 | `7233a6b` | 2026-07-07 | CONVERSATION-INTELLIGENCE | DOC | Engine doc |
| 34 | `cd5f0b3` | 2026-07-07 | CASE-GRAPH | DOC | Docs (landed batch) |
| 35 | `239a37e` | 2026-07-07 | CASE-GRAPH | DOC | Docs: core set + engines |
| 36 | `cea2937` | 2026-07-07 | CASE-GRAPH | DOC | Docs: API contracts + readiness (15/15) |
| 37 | `9b8cb1a` | 2026-07-07 | **ACTION-COMM-ENGINE** | SP | gate→consent→…→send→track pipeline (25 tests); NovuMock/ChatwootMock |
| 38 | `48d34ca` | 2026-07-07 | ACTION-COMM-ENGINE | DOC | Founder/CTO report |
| 39 | `9cb1c41` | 2026-07-07 | ACTION-COMM-ENGINE | DOC | Docs: module/README/TDR/architecture |
| 40 | `fc84a23` | 2026-07-07 | ACTION-COMM-ENGINE | DOC | Docs batch 3 (19/19) |
| 41 | `618a7a3` | 2026-07-07 | **COMMAND-CENTER** | SP | Dashboard service (13 sections) + HTML view (19 tests) |
| 42 | `1595725` | 2026-07-07 | COMMAND-CENTER | DOC | Founder/CTO report |
| 43 | `96707d0` | 2026-07-08 | **FULL-PRODUCT-E2E** | SP | voice→…→WON on one verified audit chain |
| 44 | `76fefa3` | 2026-07-08 | FULL-PRODUCT-E2E | HARDEN | Fix 3 bugs + 7 regression tests; dashboard doc set (7/7) |
| 45 | `61c0ea7` | 2026-07-08 | **PORTAL-CORE** | SP | SQLite+migrations (v1), FastAPI, auth+RBAC, UI, seed, browser E2E |
| 46 | `f869bf9` | 2026-07-08 | **UNIVERSAL-LIFECYCLE** | SP | LifecycleVector, completion rule, invariants, 8 scoring, evidence bundles (63 tests) |
| 47 | `7d017e5` | 2026-07-08 | **TELEPHONY** | SP | Call control, mock provider, 11 blockers, consent, retry; migration v2 (49 tests) |
| 48 | `6804d92` | 2026-07-08 | **ADMIN-RBAC** | SP | 9 roles, 45 permissions, deny-by-default, tenant isolation, hashed keys (21 tests) |
| 49 | `3a334de` | 2026-07-08 | **SCHEDULING** | SP | 12 appt types, availability, tokens, mock calendar/video (17 tests) |
| 50 | `a96c025` | 2026-07-08 | **AGENT-RUNTIME-GOV** | SP | AgentTrace redaction, PolicyEnforcementGate, budgets, shadow, flags (18 tests) |
| 51 | `9c6a951` | 2026-07-08 | **PORTAL-WIRING** | SP | WIP wiring: admin/RBAC/governance/scheduling + /confirm |
| 52 | `6acd65a` | 2026-07-08 | PORTAL-WIRING | TEST | W1B/W1C: 35 API tests + revealed bugs |
| 53 | `a301d6f` | 2026-07-08 | PORTAL-WIRING | SP | W2: UI sections for admin/scheduling/governance |
| 54 | `7f3a1be` | 2026-07-08 | PORTAL-WIRING | TEST | W3: browser E2E + provider honesty labels |
| 55 | `19d7019` | 2026-07-08 | **QUOTE-CPQ** | SP | Q-A: CPQ domain, Decimal pricing, gates (46 tests) |
| 56 | `1e97937` | 2026-07-08 | QUOTE-CPQ | SP | Q-B: migration v3, QuoteStore, 24 APIs, mock providers (25 tests) |
| 57 | `0487b91` | 2026-07-08 | QUOTE-CPQ | SP | Q-C: quotes UI + 5 honesty tests |
| 58 | `3a5c145` | 2026-07-08 | QUOTE-CPQ | TEST | Q-D: 4 browser E2E + calc-panel race fix |
| 59 | `4e663fc` | 2026-07-08 | SCHEDULING | SP | SCHED-V4: migration v4 persistence (tokens survive restart) |
| 60 | `0c8e4a7` | 2026-07-08 | **EVIDENCE-TRUST-FABRIC** | SP | V-A: core domain + causality + migration v5 (44 tests) |
| 61 | `8f9ef28` | 2026-07-08 | **RELATIONSHIP-CRM** | SP | CRM-A: own-IP case-first CRM domain (26 tests) |
| 62 | `d14cee8` | 2026-07-08 | EVIDENCE-TRUST-FABRIC | SP | V-B: zero-trust evidence API (27 tests) |
| 63 | `3c9345b` | 2026-07-08 | RELATIONSHIP-CRM | SP | CRM-B: migration v6, CrmStore, 24 APIs (19 tests) |
| 64 | `0bbbb92` | 2026-07-08 | EVIDENCE-TRUST-FABRIC | SP | V-C: Evidence Command Center UI (5 tests) |
| 65 | `f56dfc9` | 2026-07-08 | EVIDENCE-TRUST-FABRIC | TEST | V-D: 4 adversarial browser E2E |
| 66 | `e6fac68` | 2026-07-08 | EVIDENCE-TRUST-FABRIC | SP | V-E: hardening + transparency ledger (37 tests) |
| 67 | `65c67f5` | 2026-07-08 | **CONSOLIDATE-1** | SP | Integration baseline: merge Evidence+CRM, reconcile migrations (9 tests) |
| 68 | `efbba3a` | 2026-07-08 | RELATIONSHIP-CRM | SP | CRM-C/C1: Customer Panel UI (8 tests) |
| 69 | `c13d6bc` | 2026-07-08 | RELATIONSHIP-CRM | TEST | CRM-D: Customer Panel browser E2E + hardening |
| 70 | `dacc084` | 2026-07-08 | EVIDENCE-TRUST-FABRIC | SP | V-F: Evidence Proof Workbench UI + proof algebra |
| 71 | `be81c3f` | 2026-07-08 | QUOTE-CPQ | HARDEN | PRE-VF-QA-0: fix quote-approval browser flake |
| 72 | `64af164` | 2026-07-08 | EVIDENCE-TRUST-FABRIC | SP | EVIDENCE-MERKLE-C1: Transparency Log Core (migration v… evidence) |
| 73 | `fe142f9` | 2026-07-08 | EVIDENCE-TRUST-FABRIC | SP | EVIDENCE-REPORT-C2: Canonical Evidence Report + replay (migration v8) |
| 74 | `905a298` | 2026-07-08 | **CORE-A1** | SP | AI Employee identity + authority boundary (migration v9) |
| 75 | `bf10d9a` | 2026-07-08 | **CORE-A2** | SP | Secure Work Intake Registry + Canonical Task Contract (v10) |
| 76 | `e3ab54d` | 2026-07-08 | CORE-A2 | HARDEN | Hardening from swarm review |
| 77 | `00e0452` | 2026-07-08 | **CORE-A3** | SP | Causally Verifiable Run Ledger + Replay (v11) |
| 78 | `fb5c239` | 2026-07-08 | CORE-A3 | HARDEN | Hardening from swarm review |
| 79 | `0590e80` | 2026-07-08 | **CORE-A4** | SP | A4.1: Human Approval Gate Foundation (v12) |
| 80 | `af4d7fc` | 2026-07-08 | CORE-A4 | SP | A4.2: Approval decisions + non-transferable grants (v13) |
| 81 | `f613489` | 2026-07-08 | **CORE-A5** | SP | Deterministic Lifecycle Kernel + Completion Loop (v14) |
| 82 | `80ea4d0` | 2026-07-09 | **CORE-A6** | SP | Artifact System + Claim Graph + Materialization Firewall (v15) |
| 83 | `d08c07c` | 2026-07-09 | **TOOL-B1** | SP | Zero-Trust Tool Registry + Admission Firewall (v16) |
| 84 | `da02379` | 2026-07-09 | **TOOL-B2** | SP | Descriptor Assurance Graph + Planner Selection Boundary (v17) |
| 85 | `dd24cd8` | 2026-07-09 | **TOOL-B3** | SP | Protocol Contract Proof Kernel (v18); targets = `*_LIKE` shapes |
| 86 | `7d827ff` | 2026-07-09 | **TOOL-B4** | SP | Causal Pre-Action Reference Monitor + Denial Twin (v19) |
| 87 | `7d2c44a` | 2026-07-09 | **TOOL-B5** | SP | Four-Plane Proof-Carrying Null Broker (v20) |
| 88 | `48d15f7` | 2026-07-09 | **TOOL-B6** | SP | Read-Path Runtime Microkernel + Provenance Bisimulation (v21) |
| 89 | `d28b6f7` | 2026-07-10 | **TOOL-B7** | SP | Write-Intent Draft Runtime + Rollback-Attack Fence (v22) |
| 90 | `d95be03` | 2026-07-10 | **TOOL-B8** | SP | Pre-B9 Assurance Envelope + B9 firewall sealed (v23) |
| 91 | `4e39dd8` | 2026-07-10 | **AUDIT-REPORT-1** | DOC | Prior system-truth audit + SP inventory (`docs/audits/*`) |
| 92 | `19a3a0b` | 2026-07-10 | **ROADMAP-LOCK-1** | DOC | Roadmap lock after TOOL-B8 (`docs/roadmap/*`) |
| 93 | `5493e60` | 2026-07-10 | **TOOL-B9** | SP | Transaction Twin + Proof-of-Execution runtime (v24) |
| 94 | `b6db0f3` | 2026-07-10 | TOOL-B9 | TEST | Comprehensive Transaction Twin test suite |
| 95 | `c35d827` | 2026-07-10 | **TOOL-B9.1** | SP | Recovery Safety Case + Chaos Sentinel + Proof-of-Recovery (v25) |
| 96 | `d906a5e` | 2026-07-10 | TOOL-B9.1 | HARDEN | Tamper-quarantine ordering fix + scaffolding |
| 97 | `b7bb2f4` | 2026-07-10 | TOOL-B9.1 | TEST | Recovery test suite (230 tests, 12 files) |
| 98 | `c05681f` | 2026-07-10 | **TOOL-B9.2** | SP | Governed Work Lineage Observatory runtime (v26) |
| 99 | `7af76c2` | 2026-07-10 | TOOL-B9.2 | HARDEN | Fix `no_external_effect` key collision + scaffolding |
| 100 | `ca0b891` | 2026-07-10 | TOOL-B9.2 | TEST | Observatory test suite + deterministic rebuild |
| 101 | `cbf083a` | 2026-07-10 | TOOL-B9.2 | HARDEN | Refine B9.1 recovery-namespace guard for read-only view |
| 102 | `6e342e2` | 2026-07-11 | **EMP-A1** | SP | Employee Work Inbox — R-FSAFEQ Admission Fabric runtime (v27) |
| 103 | `1e2f3b7` | 2026-07-11 | EMP-A1 | TEST | Test scaffolding (kernel helper + 2 exemplars) |
| 104 | `8d05ff9` | 2026-07-11 | EMP-A1 | TEST | Comprehensive test suite (swarm) |
| 105 | `c95fd27` | 2026-07-11 | EMP-A1 | HARDEN | Fix module-alias collision shadowing write-intent |
| 106 | `135de7b` | 2026-07-11 | EMP-A1 | HARDEN | Resolve remaining name collisions with B7 block |
| 107 | `4ea9f55` | 2026-07-11 | AUDIT-TRACE-1 | DOC | This audit (`docs/audit/*`) |

**Coverage check:** 107/107 commits classified. 7 BASE (upstream), and every
Finalis-era commit is either a primary SP commit or a DOC/TEST/HARDEN satellite
of an SP already in the matrix. No SP-bearing feature commit is unaccounted for.

---

## 3. SP status matrix

Status ∈ {IMPLEMENTED_AND_TESTED, IMPLEMENTED_PARTIALLY, IMPLEMENTED_NOT_WIRED,
IMPLEMENTED_NOT_TESTED, SCAFFOLD_ONLY, MOCK_ONLY, DOC_ONLY, SUPERSEDED,
NOT_FOUND}. Production ∈ {PRODUCTION_READY, NOT_PRODUCTION_READY, UNKNOWN}.

> Shared reason every implemented SP is `NOT_PRODUCTION_READY`: **zero real
> external-effect surface**. `grep -rn 'import requests|import httpx|import
> smtplib|import boto3|urllib.request|http.client' finalis/` (non-test) = **0**.
> All providers are in-process mocks. By design for governance layers; a scoping
> decision for product layers. Not a bug — but the single largest production gap.

| SP | Status | Prod | Anchor |
|---|---|---|---|
| DOCS-BLUEPRINT (docs 1–45) | DOC_ONLY | UNKNOWN | `1a57c7f`..`44e128a`; `docs/finalis-ai/*` |
| SCAFFOLD-1 | IMPLEMENTED_AND_TESTED | NOT_READY | `8071a54`; 102 tests |
| VOICE-ENGINE | IMPLEMENTED_AND_TESTED | NOT_READY | `a8e15a7`; `finalis/voice/*` (1106 L); 26 tests; ASR/TTS mock |
| CASE-GRAPH | IMPLEMENTED_AND_TESTED | NOT_READY | `47cb24e` |
| CONVERSATION-INTELLIGENCE | IMPLEMENTED_AND_TESTED | NOT_READY | `8379db9`; 11 tests |
| ACTION-COMM-ENGINE | IMPLEMENTED_AND_TESTED | NOT_READY | `9b8cb1a`; NovuMock/ChatwootMock (MOCK boundary) |
| COMMAND-CENTER | IMPLEMENTED_AND_TESTED | NOT_READY | `618a7a3`; 19 tests |
| FULL-PRODUCT-E2E | IMPLEMENTED_AND_TESTED | NOT_READY | `96707d0` |
| PORTAL-CORE | IMPLEMENTED_AND_TESTED | NOT_READY | `61c0ea7`; migration v1; SQLite dev shell |
| UNIVERSAL-LIFECYCLE | IMPLEMENTED_AND_TESTED | NOT_READY | `f869bf9`; `finalis/lifecycle/*` (929 L); 63 tests |
| TELEPHONY | IMPLEMENTED_AND_TESTED | NOT_READY | `7d017e5`; v2; 49 tests; dial() mock |
| ADMIN-RBAC | IMPLEMENTED_AND_TESTED | NOT_READY | `6804d92`; `finalis/admin/*`; 21 tests; IAM seams |
| SCHEDULING | IMPLEMENTED_AND_TESTED | NOT_READY | `3a334de`/`4e663fc`; v4; 29 tests; calendar/video mock |
| AGENT-RUNTIME-GOV | IMPLEMENTED_AND_TESTED | NOT_READY | `a96c025`; `finalis/governance/*`; 18 tests |
| PORTAL-WIRING | IMPLEMENTED_AND_TESTED | NOT_READY | `9c6a951`..`7f3a1be`; honesty labels |
| QUOTE-CPQ | IMPLEMENTED_AND_TESTED | NOT_READY | `19d7019`..`3a5c145`; v3; 76 tests; payment/PDF/e-sign mock |
| EVIDENCE-TRUST-FABRIC | IMPLEMENTED_AND_TESTED | NOT_READY | `0c8e4a7`..`fe142f9`; v5/v6/v8; 269 tests |
| RELATIONSHIP-CRM | IMPLEMENTED_AND_TESTED | NOT_READY | `8f9ef28`..`c13d6bc`; v7; 63 tests; external sync mock |
| CONSOLIDATE-1 | IMPLEMENTED_AND_TESTED | NOT_READY | `65c67f5` |
| CORE-A1 | IMPLEMENTED_AND_TESTED | NOT_READY | `905a298`; v9; identity.py/authority.py |
| CORE-A2 | IMPLEMENTED_AND_TESTED | NOT_READY | `bf10d9a`; v10; tasks.py |
| CORE-A3 | IMPLEMENTED_AND_TESTED | NOT_READY | `00e0452`; v11; run_ledger.py |
| CORE-A4 | IMPLEMENTED_AND_TESTED | NOT_READY | `0590e80`/`af4d7fc`; v12–v13; approvals.py |
| CORE-A5 | IMPLEMENTED_AND_TESTED | NOT_READY | `f613489`; v14; lifecycle.py |
| CORE-A6 | IMPLEMENTED_AND_TESTED | NOT_READY | `80ea4d0`; v15; artifacts.py |
| TOOL-B1 | IMPLEMENTED_AND_TESTED | NOT_READY | `d08c07c`; v16; tool_registry.py (1215 L) |
| TOOL-B2 | IMPLEMENTED_AND_TESTED | NOT_READY | `da02379`; v17; tool_quality.py (1657 L) |
| TOOL-B3 | IMPLEMENTED_AND_TESTED | NOT_READY | `dd24cd8`; v18; tool_contracts.py (1715 L); `*_LIKE` targets |
| TOOL-B4 | IMPLEMENTED_AND_TESTED | NOT_READY | `7d827ff`; v19; tool_guardrails.py (1628 L) |
| TOOL-B5 | IMPLEMENTED_AND_TESTED | NOT_READY | `7d2c44a`; v20; tool_broker.py (1823 L) |
| TOOL-B6 | IMPLEMENTED_AND_TESTED | NOT_READY | `48d15f7`; v21; tool_runtime.py (2208 L) |
| TOOL-B7 | IMPLEMENTED_AND_TESTED | NOT_READY | `d28b6f7`; v22; tool_write_intent.py (2361 L); draft only |
| TOOL-B8 | IMPLEMENTED_AND_TESTED | NOT_READY | `d95be03`; v23; tool_commit_simulation.py (1814 L); B9 firewall sealed |
| TOOL-B9 | IMPLEMENTED_AND_TESTED | NOT_READY | `5493e60`; v24; tool_local_transaction.py (1627 L); inert outbox |
| TOOL-B9.1 | IMPLEMENTED_AND_TESTED | NOT_READY | `c35d827`; v25; tool_local_recovery.py (1746 L); ~230 tests |
| TOOL-B9.2 | IMPLEMENTED_AND_TESTED | NOT_READY | `c05681f`; v26; tool_work_observability.py (1658 L); read-only PoWO |
| **EMP-A1 (HEAD SP)** | IMPLEMENTED_AND_TESTED | NOT_READY | `6e342e2`..`135de7b`; v27; employee_work_inbox.py (1343 L); 14 test files |
| AUDIT-REPORT-1 | DOC_ONLY | UNKNOWN | `4e39dd8`; `docs/audits/*` |
| ROADMAP-LOCK-1 | DOC_ONLY | UNKNOWN | `19a3a0b`; `docs/roadmap/*`; next_coding_sp=EMP-A2 |
| EMP-A2 (handoff consumer) | NOT_FOUND | UNKNOWN | roadmap only; no module/route/migration/test |
| EMP-A3..A5 | NOT_FOUND | UNKNOWN | roadmap chain only |
| TOOL-B10 (external adapter) | NOT_FOUND | UNKNOWN | re-scoped in roadmap; no real outbound primitive |

**Counts:** 35 IMPLEMENTED_AND_TESTED · 3 DOC_ONLY · 4 NOT_FOUND · 0
SCAFFOLD/PARTIAL/NOT_TESTED · 7 SPs carry a MOCK_ONLY external boundary
(recorded in notes) · 2 *claims* SUPERSEDED (see §7).

---

## 4. Architecture inventory

The live product is one FastAPI app (`finalis/portal/app.py`, 11895 L) over one
SQLite DB (`finalis/portal/db.py`, 1716 L) with a server-rendered UI
(`finalis/portal/ui.py`, 4058 L). The repo root still contains the 2023 Next.js
starter — **not part of the running product**; no `finalis/` code imports it.

**Packages (`finalis/`):** voice (1106) · telephony (750) · crm (1025) ·
evidence (2801) · quotes (1154) · scheduling (325) · admin (427) · governance
(283) · actions (827) · lifecycle (929) · ai_employee (26017) · portal (17669).
Plus top-level scaffold (`state_machine.py`, `scoring*`, `completion_loop.py`).

**Governance kernel (`ai_employee/`)** — each SP = a **pure deterministic
kernel** (canonical-JSON + `_core_hash`, no I/O/clock/randomness) + a thin store:
identity(146)/authority(210) → tasks(382) → run_ledger(419) →
approvals(359)/approval_decisions(305) → lifecycle(774) → artifacts(775) →
tool_registry(1215) → tool_quality(1657) → tool_contracts(1715) →
tool_guardrails(1628) → tool_broker(1823) → tool_runtime(2208) →
tool_write_intent(2361) → tool_commit_simulation(1814) →
tool_local_transaction(1627) → tool_local_recovery(1746) →
tool_work_observability(1658) → employee_work_inbox(1343).

**The proof pattern (verified, common to all):** `canonical_json` (sort_keys,
`separators=(",",":")`, `allow_nan=False`) → `_sha`; `_core_hash(obj, self_key,
*extra)` excludes self + `_VOLATILE` (`created_at`, `updated_at`,
`honesty_labels`) so hashes reproduce across time/rebuild; each `build_*` returns
`<name>_hash` + `_signals`; orchestrator aggregates, strips `_signals`, and a
fail-closed dominance ladder selects the dominant signal. **Authority only
narrows down the ladder:** B8 cannot activate B9 (firewall SEALED); B9.1 recovery
creates no authority/effect; B9.2 observatory is read-only, PoWO authorizes
nothing; EMP-A1 admits + prepares a fenced handoff, executes nothing.

**Persistence:** `MIGRATIONS` = ordered `(version, sql)` tuples applied
idempotently; **27 contiguous migrations, 108 tables**; hash-chained `DbAuditLog`
(single-writer-per-DB dev assumption documented in-code).

---

## 5. API / UI / data map

**API — 402 routes** in one `create_app()`. Families: `/ai-tools/{tool_id}/*`
(46, B1–B3) · `/ai-tools/local-transactions/*` (31, B9/B9.1/B9.2, incl.
`/observability/*` & `/recovery/*`) · `/ai-employee/work-inbox/*` (30, EMP-A1) ·
`/evidence/*` (~40) · `/ai-artifacts/*` (17, A6) · quotes/price-books/pricing
(~26) · `/ai-tools/runtime/*` (15, B6) · `/crm/*` (~19) · `/cases/*` (14) ·
`/ai-tools/actions/*` (14, B4) · `/ai-tasks/*` (14, A2) · `/ai-tools/broker/*`
(11, B5) · `/ai-approvals/*` (10, A4) · write-intents (9, B7) · commit-simulations
(9, B8) · registry (8, B1) · `/ai-runs/*` (7, A3) · scheduling · `/ai-employees/*`
(3, A1).

> **Monolith hazard (recorded, not fixed):** `create_app()` is one ~11.9k-line
> function; endpoint blocks share the closure scope. This already produced a real
> regression — EMP-A1's `_wi` alias shadowed TOOL-B7's write-intent block (fixed
> `c95fd27`/`135de7b` by re-prefixing to `_ewi`). Only the **full** suite catches
> these; new blocks must use uniquely-prefixed aliases.

**UI — 23 sections** (`*_SECTIONS`): WIRING, QUOTES, EVIDENCE, CRM, WORKBENCH,
AIEMP, TASKS, RUNS, APPROVALS, LIFECYCLE, ARTIFACTS, TOOLS, QUALITY, CONTRACTS,
ACTIONS, BROKER, RUNTIME, WRITE_INTENT, COMMIT_SIM, LOCAL_TX, LOCAL_RECOVERY,
WORK_OBS, WORK_INBOX. Provider **honesty labels** (since `7f3a1be`) disclose
mocks; ~217 honesty/mock references in `app.py`.

**Data model — migration → tables:** v1 core product base (tenants, users,
parties, cases, missing_items, promises, transcripts, action_requests,
message_drafts, executions, documents, offers, audit_events) · v2 call_sessions ·
v3 quotes+CPQ (10 tables) · v4 scheduling · v5–v6 evidence (objects/chain/
contracts/holds/derivatives/merkle/policy) · v7 crm (13 tables incl.
external_sync) · v8 evidence_proof_reports · v9 ai_employees · v10 ai_tasks · v11
ai_runs · v12–v13 approvals+grants · v14 task_transitions · v15 artifacts · v16
tools · v17 tool_quality · v18 tool_contracts · v19 action_proposals/decisions ·
v20 broker · v21 runtime · v22 write_intent · v23 commit_simulation · v24
local_transactions · v25 recovery · v26 governed_work_runs+work_outcome_proofs ·
v27 EMP-A1 (8 work-admission tables). The migration ladder mirrors the SP ladder;
each governance SP adds a request/outcome/event triad (event-sourced).

**External-effect surface:** 0 real outbound primitives. Mocks: NovuMock,
ChatwootMock, telephony mock dial, mock calendar/video/payment/PDF/e-sign, ASR/TTS
seams, inert TOOL-B9+ outbox. TOOL-B3 contract targets are `*_LIKE` shapes with
an in-code disclaimer *"This is not OpenAI Apps SDK runtime integration."*

---

## 6. Production gaps (recorded, not fixed) — TOP 10

1. **No real external effect anywhere** (0 outbound primitives). Master gap; the
   rest specialize it.
2. **TOOL-B10 external adapter NOT implemented** — the first governed real effect
   named in the roadmap; no module/route/migration/test.
3. **EMP-A1 handoff has no consumer (EMP-A2 NOT_FOUND)** — admitted work
   terminates at the fence; nothing executes it.
4. **Delivery/notification MOCK_ONLY** (NovuMock/ChatwootMock).
5. **Telephony dial is a mock provider** (no PSTN/SIP).
6. **Scheduling calendar/video are mocks**.
7. **CPQ payment/PDF/e-sign are mocks**.
8. **CRM external sync is a mock**.
9. **Persistence + concurrency are dev-grade** (SQLite, single-writer assumption;
   11.9k-line portal monolith with collision hazard).
10. **Voice ASR/TTS are router seams** (no real speech vendor).

Not a correctness gap — the mock boundary is intentional for governance layers
(their theorems are precisely *"produces no external effect"*). The gap is that
*product* value eventually needs those effects real, under the same ladder.
Strength to preserve: honesty labelling already **discloses** mocks rather than
faking. Coverage note: 5640 tests prove governance + simulated E2E; **none**
exercise a real third-party call (there is none to exercise).

---

## 7. Historical-claim verification

| Claim | Verdict | Evidence |
|---|---|---|
| ROADMAP-LOCK-1 = `19a3a0b` | **TRUE** | commit subject matches |
| AUDIT-REPORT-1 = `4e39dd8` | **TRUE** | commit subject matches |
| TOOL-B8 = `d95be03` | **TRUE** | commit subject matches |
| TOOL-B9.1 = `b7bb2f4` | **PARTIALLY_TRUE** | `b7bb2f4` is the B9.1 **test** commit; runtime = `c35d827` |
| migration "v25" | **SUPERSEDED** | now **v27** (v26=B9.2, v27=EMP-A1) |
| "~5061 tests green" | **SUPERSEDED** | now **5640** collected / 398 files |
| "EMP-A1 in progress" | **FALSE** | EMP-A1 is **COMPLETE** and is the HEAD SP |

---

## 8. Do NOT rebuild

Do not re-implement, refactor, duplicate, or build an "alternative" of any of:
- The entire `finalis/ai_employee/*` governance ladder (CORE-A1..A6,
  TOOL-B1..B9.2, EMP-A1). Determinism + reproducible hashes are load-bearing — a
  rewrite that changed hashing, the `_VOLATILE` set, or the dominance ladder
  invalidates every downstream proof.
- Product engines: CRM, Evidence, Case Graph, Scheduling, Telephony, CPQ,
  governance core — all exist and are tested.
- Infrastructure: reuse (don't fork) the migration system (next = **v28**;
  never renumber applied migrations), canonical hashing, audit chain, the portal
  `create_app()` factory (extend with uniquely-prefixed blocks), and the conftest
  `Gate` helper (new helpers need domain-unique names — a bare `wi()` already
  collided between B7 and EMP-A1).

"Not rebuild" does **not** mean the external boundary is done: replacing a mock
with a real governed adapter at the proper ladder position (TOOL-B10 / EMP-A2) is
**new work**, not a rebuild.

---

## 9. Current true baseline & next direction

**What is real:** a fully-tested vertical product (voice → conversation intel →
case graph → completion loop → action pipeline → upload/evidence → dashboard →
quote → CRM) with RBAC, tenant isolation, and a hash-chained audit log — every
external effect mocked and disclosed — plus a **complete proof-carrying
governance kernel** (CORE-A1..A6, TOOL-B1..B9.2, EMP-A1).

**Where it ends:** `EMP-A1` is the frontier. It **admits** work and **prepares
exactly one fenced, single-use handoff** for EMP-A2 — and **executes nothing**.
`EMP-A2` and `TOOL-B10` are **NOT_FOUND**.

> The system can prove everything about a unit of work up to the moment of
> action, and then — by design — stops. Nothing crosses into a real external
> effect yet.

**CURRENT TRUE STARTING POINT for the next SP** (not a rewrite, not a re-audit):
implement the **first governed real effect** — the EMP-A2 handoff consumer and/or
the TOOL-B10 external adapter boundary — so an EMP-A1-admitted, fully-proven work
item can execute against a real provider under the *existing* consent / approval /
audit gates, replacing one mock at a time. Everything beneath that line already
exists and is tested; do not rebuild it.

---

## 10. Companion files in `docs/audit/`
This master is self-contained; these are focused views of the same evidence:
`AUDIT_TRACE_1_EXECUTIVE_SUMMARY.md`, `_FULL_IMPLEMENTATION_HISTORY.md`,
`_SP_STATUS_MATRIX.md`, `_ARCHITECTURE_INVENTORY.md`, `_API_UI_DATA_MAP.md`,
`_DO_NOT_REBUILD.md`, `_PRODUCTION_GAPS.md`, `_CURRENT_BASELINE.md`, and the
machine-readable `_SP_STATUS.json`.

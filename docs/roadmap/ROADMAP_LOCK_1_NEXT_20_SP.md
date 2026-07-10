# ROADMAP-LOCK-1 — Next 20 SP (ranked execution queue)

> The immediate, ordered build queue from code HEAD `d95be03` (TOOL-B8 v5). Ranked by **safety value → product value → production-readiness value → implementation risk**. Each item obeys the Do-Not-Rebuild rules and the core governance rules. **Coding starts at #1 (TOOL-B9).**

| # | SP | Why now (rank rationale) | Reuses (do not rebuild) | Deps | Not allowed | Classification |
|---|---|---|---|---|---|---|
| 1 | **TOOL-B9** — Controlled Internal Commit Runtime | Highest safety value: the first *real but local, reversible* commit; every later effect depends on it. Deps already satisfied (B8 done). | tool_commit_simulation, tool_write_intent, audit, run_ledger, rbac | B8 | external providers, tokens/creds, non-local writes, B8-as-authority | MISSING→IMPLEMENTED (local) |
| 2 | **TOOL-B10** — Commit Recovery & Observability | Makes B9 crash-safe + non-duplicating before anything builds on it. | B9, run_ledger, audit, governance | B9 | external effects, prod metrics backend | MISSING→IMPLEMENTED (local) |
| 3 | **TOOL-B11** — Employee Work Inbox + Run Ledger 2.0 | Operator visibility over existing tasks/ledger; enables mobile + workbench. | tasks, run_ledger, approvals, dashboard | B10 | autonomous execution, second task store | MISSING→IMPLEMENTED |
| 4 | **TOOL-B12** — Employee Work Graph + Outcome Contract | Ties work→case→artifact→commit; measurable outcomes. | case_services, lifecycle, artifacts | B11 | rebuilding Case Graph | MISSING→IMPLEMENTED |
| 5 | **TOOL-B13** — Autonomy Level Engine | Single authoritative `min(...)` cap that governs every future effect layer. Must exist before providers. | autonomy, governance, rbac | B12 | autonomy above approval limit, second gate | MISSING→IMPLEMENTED |
| 6 | **EVAL-1** — Evaluation Lab | Locks the safety/quality bar (golden, injection, artifact-as-authority, cross-tenant) before external surfaces. | tests, _bN_kernel, existing red-team corpora | B9 (grows after) | weaken/delete tests | MISSING→IMPLEMENTED |
| 7 | **ADAPTER-1** — Provider Boundary + Credential Model | The hard gate: nothing external is allowed before this. Credential least-privilege + provider simulation. | all *Provider seams, governance | B9,B10,B13 | any real external call, creds in traces/artifacts | MISSING→MOCKED (sim) |
| 8 | **WORKBENCH-1** — Governed Cloud Workbench | First human-watched work surface (sandbox, recorder, reviewable, read-only browser). | governance, B6 runtime, B9/B10, webscout | B10, EVAL-1 | secrets in sandbox, uncontrolled effect | MISSING→SCAFFOLDED/MOCKED |
| 9 | **CASE-2** — Case Completion Engine 2.0 (EXTEND) | Upgrades the core "get the case done" loop in place. | case_services, completion_loop, dashboard, scoring | B12,B13,B10 | second Case Graph/Loop/Dashboard | IMPLEMENTED→extended |
| 10 | **EVID-PROD-1** — Evidence Production Lifecycle (EXTEND) | Hardens evidence intake + prepares signing/anchoring interfaces. | evidence/*, evidence_store, ocr_router | ADAPTER-1, INFRA-2 | claim anchoring before wired, second store | IMPLEMENTED+SCAFFOLDED |
| 11 | **INFRA-1** — PostgreSQL migration | Production persistence floor; portable SQL already written. | portal/db + stores | ADAPTER-1 | premature before schema stable | local→IMPLEMENTED (prod) |
| 12 | **MOBILE-1** — Mobile API contracts + PWA shell | Reach for operators; read + approval only. | existing REST, auth | B11 | cache authoritative, push as approval | MISSING→SCAFFOLDED |
| 13 | **CHAT-1** — Conversation Contract + Slack scaffold + cards | First chat surface; server-authoritative approval cards. | actions, approvals, control plane | ADAPTER-1, B11 | Slack action as implicit approval | MISSING→SCAFFOLDED |
| 14 | **SAAS-1** — Production Auth/IAM + Tenancy + Billing | Removes dev-grade-auth blocker; prerequisite for any live pilot. | rbac, auth, tenants/users, governance | INFRA-1, ADAPTER-1 | second RBAC, secrets in config | IMPLEMENTED(dev)→IMPLEMENTED(prod) |
| 15 | **INFRA-2** — Object storage / WORM | Unblocks evidence anchoring + immutability. | evidence/storage seam | ADAPTER-1 | two storage layers | SCAFFOLDED→IMPLEMENTED |
| 16 | **CHAT-2** — Teams scaffold + adaptive cards | Second chat surface, mirror of CHAT-1. | CHAT-1, actions | CHAT-1 | Teams action as implicit approval | MISSING→SCAFFOLDED |
| 17 | **MOBILE-2** — Native iOS/Android + push approval + capture + offline draft | Field workforce; push opens server-authoritative approval; offline = draft only. | MOBILE-1, evidence gateway, approvals | MOBILE-1, EVID-PROD-1 | approve from push, offline commit | MISSING→SCAFFOLDED |
| 18 | **INFRA-3** — Observability stack | Metrics/tracing/alerting for commit + governance. | governance + B10 metrics seams | INFRA-1 | — | MISSING→IMPLEMENTED |
| 19 | **VOICE-PROD-1** — Voice Production Boundary (EXTEND) | Real voice intake → evidence-gated conversation-to-case commit via B9. | voice/*, telephony/* | ADAPTER-1, B9, EVID-PROD-1 | commit uncertain facts, second voice engine | IMPLEMENTED logic + BLOCKED_PROVIDER |
| 20 | **PILOT-1** — Real Slack pilot | First real external effect, shadow-first + kill-switch, all gates enforced. | ADAPTER-1, CHAT-1, actions | ADAPTER-1, CHAT-1, SAAS-1, EVAL-1 | bypass approval/consent, before ADAPTER-1 | MOCKED→pilot IMPLEMENTED |

---

## Beyond #20 (queued, not yet ranked in detail)
PACK-1..7 (vertical worker packs, extend playbooks/quotes/webscout) · PILOT-2/3/4 (Teams / email-calendar / telephony-SMS-WhatsApp) · REFACTOR-1..3 (app.py/ui.py/kernel dedup, post-B13, behavior-preserving) · INFRA-4 (deployment runbook) · GATE-1..4 (readiness audit, red-team, limited beta, production candidate).

## Ranking principles used
1. **Safety first:** the local commit gate (B9) + its recovery (B10) + autonomy cap (B13) + eval bar (EVAL-1) + provider boundary (ADAPTER-1) come before any external surface.
2. **Extend before integrate:** control plane (B11–B12) and case loop (CASE-2) upgrade existing modules before new surfaces are added.
3. **Boundary before providers:** ADAPTER-1 and SAAS-1 precede every real pilot.
4. **Infra where it unblocks:** INFRA-1/2 sequenced exactly where persistence/anchoring is needed.
5. **Lowest implementation risk first within a tier:** governance kernels (well-understood pattern) before surfaces (new client tech).

## Do-not-build-yet (reaffirmed)
- No real provider, MCP, or LLM call before **ADAPTER-1** (#7).
- No live pilot before **SAAS-1** (#14) + **EVAL-1** (#6) green.
- No production deploy before INFRA-1..4 + REFACTOR + GATE-4.
- No second copy of any existing module — ever.

**Coding resumes at #1: TOOL-B9.**

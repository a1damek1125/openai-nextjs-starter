# FinalisAI / ViktorAI Full System Truth Audit and Completed SP Inventory

> Audit ID: **AUDIT-REPORT-1** · Type: **AUDIT / REPORT / INVENTORY ONLY** (no product logic changed)
> Method: repository evidence only — `git`, migration SQL, route decorators, `pytest`, source reads, 4 parallel read-only inventory agents.

---

## 1. Executive Summary

| Field | Value (repository evidence) |
|---|---|
| Branch | `claude/finalis-ai-casewoker-blueprint-f1huse` |
| HEAD commit | **`d95be03`** (TOOL-B8 v5) |
| Mission-stated baseline | `d28b6f7` / 4157 tests — **now superseded** (see note) |
| Working tree | clean (all work committed) |
| Full non-browser test result | **4601 passed, 0 failed, 0 errors, 0 skipped** |
| Command | `python3 -m pytest tests/ --ignore=tests/test_browser_e2e.py -q` |
| Current migration version | **v23** (`EXPECTED_DB_VERSION = 23`) |
| Latest completed SP | **TOOL-B8 v5** (Machine-Checkable Pre-B9 Assurance Envelope) |
| Total source | ~47,400 LOC across ~120 `finalis/*.py` files |
| Total API routes | **340** `@app.*` routes + 23 dynamically-mounted sub-field routes |
| Total tests | **345** test files (344 non-browser + 1 browser E2E excluded) |
| Docs | 123 markdown files under `docs/` |
| Git history | 90 commits |
| Safe to continue? | **YES** — no emergency fix required |
| Production ready? | **NO** — local/SQLite, mock providers, no external runtime/credentials |

### IMPORTANT — this audit corrects two prior errors

1. **The mission brief (and a prior parallel audit) describe the state at `d28b6f7` / v22 / 4157 tests / "B8 not implemented".** That is **stale**. Since then, **TOOL-B8 v5 has been implemented, tested (444 new tests), committed (`d95be03`) and pushed**. Current truth: HEAD `d95be03`, migration **v23**, **4601** tests, **B8 EXISTS IN CODE**.
2. **A prior audit claimed "CRM is on another branch" and that only the CORE-A/TOOL-B line exists.** This is **false by repository evidence.** This branch physically contains the **entire product**: CRM, Evidence Trust Fabric, Quotes/CPQ, Scheduling, Telephony, Voice, Actions/Communication, Case Graph, Dashboard, Admin/RBAC, Governance — all present in `finalis/`, wired into `app.py`, migrated (v1–v8) and tested. They are ancestors of HEAD (`git log` confirms).

### Highest risks (detail in §17)
1. Single-node **SQLite + local filesystem** persistence — not production storage.
2. **All external effects are mocks** (telephony, email/SMS, calendar, video, PDF, e-signature, payment, AV scanner, OCR, ASR/TTS, web fetch) — no real provider is wired.
3. Evidence transparency log is cryptographically real but **local-only, externally unanchored** — not third-party "immutable audit" grade.
4. Auth is **dev-grade** (HMAC-signed local tokens, static default secret `dev-secret-change-me`, no SSO/MFA/login-rate-limit).
5. `app.py` (10,083 LOC) and `ui.py` (3,691 LOC) are **very large** — maintainability risk as B9+ lands.

### Next recommended SP
**TOOL-B9 — Controlled Internal Commit Runtime for Local Reversible State** (effector-exclusive gate, commit attestation, emergency abort, local-only write scope, no external providers). B8 v5 is already done, so B8 is *not* next.

---

## 2. Current State

- **Branch:** `claude/finalis-ai-casewoker-blueprint-f1huse`; **HEAD:** `d95be03`; tree clean; `local == origin`.
- **Commands run:** `git status / branch / rev-parse / log / diff --stat / ls-files`; migration-header grep on `db.py`; route grep on `app.py`; forbidden-route scan; per-module `pytest`; full-suite `pytest`; collect-only counts.
- **Modules inspected:** `finalis/ai_employee/` (CORE-A + TOOL-B), `finalis/{crm,evidence,quotes,scheduling,telephony,voice,actions,governance,admin,lifecycle}/`, top-level `finalis/*.py` (dashboard, case_services, completion_loop, scoring, state_machine, certainty_core, autonomy, audit, webscout, documents, ocr_router), `finalis/portal/{app,db,ui,auth,seed,*_store}.py`, `tests/`, `docs/`.

---

## 3. Chronological Completed SP Inventory

The **migration ledger `v1..v23`** in `finalis/portal/db.py` is the authoritative build log (each migration carries a header comment naming its SP). Cross-referenced with `git log`.

| Order | SP | Version | Status | Commit / Migration | Tests (approx, evidence) | Main scope |
|---|---|---|---|---|---|---|
| 1 | Working Portal + Case Command Center | — | COMPLETED_AND_TESTED | `61c0ea7`,`618a7a3` / mig v1 | portal 51 | SQLite+FastAPI+auth+RBAC+UI, cases/tenants/users |
| 2 | Universal Lifecycle Logic | — | COMPLETED_AND_TESTED | `f869bf9` / mig v2 | 167 | LifecycleVector (7-dim), state machine (16 states), completion loop, scoring |
| 3 | Quote Builder / CPQ | Q-A..Q-D | COMPLETED_AND_TESTED (+mock output) | `19d7019`,`1e97937`,`0487b91`,`3a5c145` / mig v3 | 76 | CPQ lifecycle, Decimal money, gates, versioning; mock PDF/sign/invoice |
| 4 | Calendar & Scheduling | SCHED-V4 | MOCKED_AND_TESTED | `3a334de`,`4e663fc` / mig v4 | 29 | 12 appt types, availability/slots, hashed confirm tokens; mock calendar/video |
| 5 | Evidence Trust Fabric | V-A..V-F | COMPLETED_AND_TESTED (+mock scanner) | `0c8e4a7`..`e6fac68`,`dacc084` / mig v5,v6 | (part of 269) | SHA-256 custody chain, Merkle tree, dual-view, retention/legal-hold |
| 6 | Evidence Merkle Transparency | MERKLE-C1 | COMPLETED_AND_TESTED | `64af164` / mig v6 | (part of 269) | RFC 6962/9162 consistency proofs, server-verified |
| 7 | Evidence Report Package | REPORT-C2 | COMPLETED_AND_TESTED | `fe142f9` / mig v8 | (part of 269) | content-addressed report hash, D1–D15 proof algebra, verification replay |
| 8 | Relationship Core CRM | CRM-A..CRM-D | COMPLETED_AND_TESTED | `8f9ef28`,`3c9345b`,`efbba3a`,`c13d6bc` / mig v7 | 63 | own-IP CRM, consent (non-overrideable), memory, dedupe/merge, opt-in sync |
| 9 | CONSOLIDATE-1 integration baseline | — | COMPLETED_AND_TESTED | `65c67f5` | integration tests | merged Evidence + CRM, reconciled migrations (v6/v7 renumber) |
| 10 | Telephony & Call Control | — | MOCKED_AND_TESTED | `7d017e5` | 49 | permission gate (11 blockers), anti-harassment, consent, dispositions; mock provider |
| 11 | Voice + Conversation Intelligence | — | IMPLEMENTED (+mock ASR/TTS) | `8379db9`,`3f5e6d3` | 37 | dialogue policy, evidence-gated facts; mock ASR/TTS |
| 12 | Action & Communication Engine | — | MOCKED_AND_TESTED | `9b8cb1a` | 25 | gate→consent→ratelimit→route→compose→approve→send; mock Novu/Chatwoot/Temporal |
| 13 | Case Graph / Completion Loop | — | COMPLETED_AND_TESTED | `239a37e`,`cea2937` | (in 87) | NBA, missing-info, promises, action-gate, hash-chained audit |
| 14 | Admin / Tenant / RBAC | — | COMPLETED_AND_TESTED | `6804d92` | 21 | 9 roles, 45 perms, deny-by-default, last-owner/escalation guards, hashed keys |
| 15 | Agent Runtime Governance | — | COMPLETED_AND_TESTED | `a96c025` | 18 | AgentTrace (secret redaction), policy gate, autonomy budgets, shadow mode, flags |
| 16 | Portal Wiring W1–W3 | — | COMPLETED_AND_TESTED | `9c6a951`,`6acd65a`,`a301d6f`,`7f3a1be` | (in portal) | admin/scheduling/governance UI + APIs |
| 17 | **CORE-A1** AI Employee Identity | — | COMPLETED_AND_TESTED | `905a298` / mig v9 | 91 | identity, authority lattice, forbidden actions, no self-approval |
| 18 | **CORE-A2** Secure Work Intake | — | COMPLETED_AND_TESTED | `bf10d9a`,`e3ab54d` / mig v10 | (in ai_task 250) | canonical envelope, hashes, idempotency, purpose/scope, tenant isolation |
| 19 | **CORE-A3** Run Ledger + Replay | — | COMPLETED_AND_TESTED | `00e0452`,`fb5c239` / mig v11 | 103 | causal run ledger, event-sourced replay, tamper handling |
| 20 | **CORE-A4.1/4.2** Human Approval Gate | — | COMPLETED_AND_TESTED | `0590e80`,`af4d7fc` / mig v12,v13 | 169 | policy capsule, challenge, decisions, non-transferable grants, dual control |
| 21 | **CORE-A5** Lifecycle Kernel | — | COMPLETED_AND_TESTED | `f613489` / mig v14 | (in ai_task 250) | append-only task state machine, transition ledger, side-effect firewall |
| 22 | **CORE-A6** Artifact System | — | COMPLETED_AND_TESTED | `80ea4d0` / mig v15 | 175 | versioned artifacts, ABOM, provenance/claim graph, materialization firewall |
| 23 | **TOOL-B1** Tool Capability Registry | — | COMPLETED_AND_TESTED | `d08c07c` / mig v16 | 379 | zero-trust descriptors, risk capsules, negative capabilities, admission firewall |
| 24 | **TOOL-B2** Descriptor Assurance Graph | v5 | COMPLETED_AND_TESTED | `da02379` / mig v17 | 383 | quality gate, descriptor IR, mutation harness, selection boundary |
| 25 | **TOOL-B3** Protocol Contract Proof Kernel | v5 | COMPLETED_AND_TESTED | `dd24cd8` / mig v18 | 445 | proof bundle, projection firewall, scope calculus, non-interference |
| 26 | **TOOL-B4** Pre-Action Reference Monitor | v4 | COMPLETED_AND_TESTED | `7d827ff` / mig v19 | (ai_action_*) | causal action graph, temporal policy automaton, counterfactual denial twin, no-execution proof |
| 27 | **TOOL-B5** Null Broker | v5 | COMPLETED_AND_TESTED | `7d2c44a` / mig v20 | 210 | four-plane proof-carrying null broker, safety lattice, fault injection, release gate |
| 28 | **TOOL-B6** Read-Path Runtime | v5 | COMPLETED_AND_TESTED | `48d15f7` / mig v21 | 319 | snapshot-bound read-only runtime, output provenance bisimulation, canary non-leakage |
| 29 | **TOOL-B7** Write-Intent Escrow Runtime | v4 | COMPLETED_AND_TESTED | `d28b6f7` / mig v22 | 491 | write-intent draft, transaction escrow, rollback-attack fence, conflict graph |
| 30 | **TOOL-B8** Pre-B9 Assurance / Commit Sim | v5 | COMPLETED_AND_TESTED | `d95be03` / mig v23 | 444 | machine-checkable assurance envelope, evidence closure net, non-delegable seal |

**Statuses used:** COMPLETED_AND_TESTED, MOCKED_AND_TESTED, PARTIALLY_IMPLEMENTED, PROMPTED_BUT_NOT_IMPLEMENTED, PLANNED_NEXT, UNKNOWN_NEEDS_CONFIRMATION.

**Partially implemented:** none found — every module with source has passing tests.
**Prompted / planned but NOT implemented (no source in this branch):** TOOL-B9, B10, B11, B12, B13, B14.
**UNKNOWN_NEEDS_CONFIRMATION:** none — CRM/CONSOLIDATE-1/Evidence are all confirmed present here.

See `AUDIT_REPORT_1_COMPLETED_SP_INVENTORY.md` for the per-SP detail template.

---

## 4. Detailed SP Scope

Per-SP detail (files, endpoints, migration, models, tests, guarantees, mocks, scaffolds, missing, production classification) is maintained in **`AUDIT_REPORT_1_COMPLETED_SP_INVENTORY.md`** to keep this file navigable. Headlines:

- **CORE-A1..A6 + TOOL-B1..B8** live in `finalis/ai_employee/` (identity.py, authority.py, tasks.py, run_ledger.py, approvals.py/approval_decisions.py, lifecycle.py, artifacts.py, tool_registry.py, tool_quality.py, tool_contracts.py, tool_guardrails.py, tool_broker.py, tool_runtime.py, tool_write_intent.py, tool_commit_simulation.py) + matching `*_store.py` + migrations v9–v23. Governance line is **local, deterministic, proof-carrying, non-executing** by construction; the most permissive outcomes are read-only / draft / simulation (`RUNTIME_READ_ONLY_COMPLETED`, `TRANSACTION_ESCROW_DRAFT_CREATED`, `B8_V5_ACCEPTED`) — never a real effect.
- **Product line** (`finalis/{lifecycle,quotes,scheduling,evidence,crm,telephony,voice,actions}` + top-level services) implements the real HVAC-case CRM/CPQ/scheduling/evidence/voice/telephony product with **mock external providers** behind Protocol seams.

---

## 5. Current Implemented Surface

| Capability | Where | Status |
|---|---|---|
| Identity / authority lattice / no-self-approval | ai_employee/identity.py, authority.py | Implemented+tested |
| Secure intake / canonical envelope / idempotency | ai_employee/tasks.py + mig v10 | Implemented+tested |
| Human approval / grants / dual control | ai_employee/approvals.py, approval_decisions.py | Implemented+tested |
| Task lifecycle / state machine / transition ledger | ai_employee/lifecycle.py, state_machine.py | Implemented+tested |
| Artifact system / ABOM / claim graph / quarantine | ai_employee/artifacts.py | Implemented+tested |
| Tool registry / quality / contract proof | ai_employee/tool_{registry,quality,contracts}.py | Implemented+tested |
| Pre-action monitor / null broker | ai_employee/tool_guardrails.py, tool_broker.py | Implemented+tested |
| Read-only runtime | ai_employee/tool_runtime.py | Implemented+tested |
| Write-intent escrow (draft-only) | ai_employee/tool_write_intent.py | Implemented+tested |
| Pre-B9 assurance / commit simulation | ai_employee/tool_commit_simulation.py | Implemented+tested |
| CRM (parties/consent/memory/dedupe) | crm/ | Implemented+tested |
| Evidence trust fabric (hash chain, Merkle, reports) | evidence/ | Implemented+tested (crypto real, local-only) |
| Quotes / CPQ | quotes/ | Implemented+tested (mock output providers) |
| Scheduling | scheduling/ | Implemented+tested (mock calendar/video) |
| Telephony / Voice / Actions | telephony/, voice/, actions/ | Mocked+tested (no real transport) |
| Case graph / completion loop / dashboard | case_services.py, completion_loop.py, dashboard.py | Implemented+tested |
| Admin / RBAC / governance | admin/rbac.py, governance/runtime.py | Implemented+tested |
| Portal (auth/tenant isolation/UI) | portal/{app,auth,ui,db}.py | Implemented+tested (dev-grade auth) |

---

## 6. Planned / Prompted But Not Implemented Surface

No source or tests exist in this branch for: **TOOL-B9, B10, B11, B12, B13, B14.** Prompt text or roadmap mentions are **not** implementation. B8's own report and this audit recommend TOOL-B9 next. `certainty_core.py` (LGGT) is an **honest Phase-1 seam** (NullAdapter heuristic) — the runtime is deliberately not built.

---

## 7. Code Quality Audit

| Dimension | Rating | Note |
|---|---|---|
| Architecture coherence | GREEN | Consistent kernel→store→endpoints→UI pattern across all 8 TOOL-B and product modules; strict B1→B8 authority-narrowing layering. |
| Determinism / hashing | GREEN | Uniform `_core_hash`/`canonical_json` (`sort_keys`, `allow_nan=False`), self-hash + actor/time exclusions, tested for determinism. |
| Reason-code / dominance stability | GREEN | Every module has an explicit fail-closed dominance ladder with stable reason codes, unit-tested. |
| Test strength | GREEN | 4601 passing; heavy negative/fault-injection/malicious-payload coverage. |
| File size | **RED** | `portal/app.py` = **10,083 LOC**, `ui.py` = **3,691 LOC**; several kernels >1,800 LOC. Maintainability risk. |
| Duplicated model/test patterns | **YELLOW** | Each TOOL-B kernel repeats the build_*/dominance/proof-bundle shape; test helpers (`_bN_kernel.py`) are near-copies. Intentional but growing. |
| Store consistency | GREEN | All `*_store.py` follow the same tenant-scoped shape. |
| UI JS complexity | **YELLOW** | `ui.py` is one monolithic server-rendered HTML/JS string builder; per-section `loadX/openX` fns; growing but sectioned. |
| Error handling | GREEN | Explicit `HTTPException(404/403)`; fail-closed defaults. |
| Naming consistency | GREEN | Consistent SP/versioned naming. |

**Every RED/YELLOW explained:** `app.py`/`ui.py` size (RED) — split into routers/blueprints after B9 boundary stabilizes; do not refactor mid-B-line. Duplication (YELLOW) — acceptable until the proof-kernel shape is final; consider a shared base after B9.

Scorecard: see §18.

---

## 8. Test Quality Audit

- **Full non-browser:** 4601 passed, 0 failed/errors/skipped. Browser E2E (`tests/test_browser_e2e.py`) **excluded** (known Chromium/SIGKILL env flake) — not a code failure.
- **By area (evidence):** governance/AI-employee ≈ 3,150+ (B1 379, B2 383, B3 445, B5 210, B6 319, B7 491, B8 444, CORE-A ≈ 800+); product ≈ 1,100 (Evidence 269, Lifecycle 167, Quotes 76, CRM 63, Telephony 49, Voice/CI 37, Scheduling 29, Actions 25, Admin 21, Governance 18, Portal 51, Case/Dashboard 87). Detail in `AUDIT_REPORT_1_TEST_AUDIT.md`.
- **Strengths:** route 404/405 tests, RBAC tests, cross-tenant tests, hash-determinism tests, no-execution invariant tests, fault-injection harnesses with fail-closed release gates.
- **Risks:** tests are often **implementation-coupled** to exact local model field shapes (YELLOW) — will need updates when models change; a minority are label/shape assertions rather than behavioral (acceptable given the proof-object domain).
- **No skipped/xfail** tests observed.

---

## 9. Route / API Audit

340 routes. Groups (by 2nd path segment): `/ai-tools` 120, `/evidence` 40, `/crm` 25, `/ai-tasks` 22, `/ai-artifacts` 22, `/quotes` 20, `/cases` 17, `/ai-approvals` 14, `/ai-runs` 11, `/ai-employees` 6, `/scheduling` 5, `/admin` 5, `/price-books` 4, `/telephony` 3, `/actions` 3, `/upload-links` 3, `/pricing-rules` 3, `/auth` 3, `/governance` 2, `/dashboard` 2, `/completion-loop` 2, others 1. **Forbidden execution route scan: NONE found** (`/commit`, `/execute`, `/release-effects`, `/activate-commitment`, `/activate-b9`, `/grant-authority`, `/provider/call`, `/mcp/call`, `/payment/execute`, `/crm/mutate`, `/evidence/mutate`, `/message/send`, `/export` — the only POST containing "commit" is `/ai-tools/commit-simulations`, the safe B8 creator). Full classification in `AUDIT_REPORT_1_ROUTE_AUDIT.md`.

---

## 10. UI Audit

`ui.py` renders a single server-authoritative portal. Each governance section (broker, runtime, write-intent, commit-sim) carries **honesty labels** (`READ_ONLY_INTERNAL_RUNTIME_ONLY`, `WRITE_INTENT_DRAFT_ONLY`, `LOCAL_COMMIT_SIMULATION_ONLY`, `B9_REVALIDATION_REQUIRED`, `commit executable now: false`). Telephony/scheduling responses surface `provider_is_mock: true`. Dashboard grants the AI-worker role an **empty permission set** ("AI never approves via the UI"). No UI control triggers a real external effect; all mutating actions are domain-local or draft/simulation. **No UI dishonestly implies real execution.**

---

## 11. Database / Migration Audit

- **Monotonic v1→v23**, no gaps, no duplicates (`test_integration_baseline.py::test_1_2_3_order_version_and_no_duplicates` passes; `EXPECTED_DB_VERSION = 23`; idempotency test passes).
- One **honest historical renumber**: CRM moved v6→v7 at CONSOLIDATE-1 so Evidence V-E could own v6 (documented in the SQL comment).
- **All tables tenant-scoped** (`tenant_id` + indexes). Money stored as **TEXT-encoded Decimal** to avoid SQLite float drift. Confirmation tokens stored as **SHA-256 hash + expiry only** (raw never persisted).
- **Storage class: SQLite (single file) + local filesystem vault** — explicitly non-production (db.py docstring says Postgres is a "connection/driver swap … marked Scaffolded until exercised").

---

## 12. Security Audit

- **Fail-closed everywhere:** deny-by-default RBAC (tenant check first), hard-fail dominance ladders, unknown action/flag = off.
- **Tenant isolation:** enforced server-side on every query (`tenant_id=?` scoping; `require_permission` used ~305×; cross-tenant → 404/DENY). Covered by tests.
- **RBAC:** 9 roles / 45 perms, last-owner guard, escalation guard, `ai.approve_own_action` structurally absent.
- **No implicit authority transfer / no approval-as-execution / no proof-bundle override:** verified in B4–B8 kernels (approval binds *future* action only; proof bundles carry `proof_bundle_overrides_blocker=false`, `authorizes_b9=false`; certificates carry `is_authority=false`).
- **No credential/token exposure:** API keys hashed (sha256), passwords PBKDF2-100k, governance trace redacts secrets, safe outputs negative-tested against token/credential-like leakage.
- **No hidden write/export/external-call path:** forbidden-route scan clean; all external effects mocked.
- **Weaknesses (non-emergency):** dev-grade auth (HMAC local token, static default secret, no MFA/SSO/login-rate-limit); regex-based secret redaction (best-effort); evidence transparency log not externally anchored.

---

## 13. Hash / Proof Audit

- Deterministic canonical JSON (`sort_keys=True`, `separators=(",",":")`, `allow_nan=False` → **NaN/Infinity rejected**).
- `_core_hash` excludes the self-hash field + `created_at`/`updated_at`/`honesty_labels`; decision hashes additionally exclude actor id/type and request id → **actor/time/id-independent** (tested across B5–B8).
- Proof bundles enumerate component hashes, exclude their own hash, and each layer's proof extension participates in the parent bundle (B7 escrow extension, B8 v5 extension verified).
- **Proof bundle cannot override a blocker** (explicit field + tests); **tamper → recompute mismatch → TAMPERED** (verify endpoints tested); replay-consistency and metamorphic checks present in B6/B8.
- Evidence fabric adds real SHA-256 custody chains, Merkle inclusion + RFC 6962/9162 consistency proofs (server-verified). Caveat: **`STRICT_RFC8785_JCS_STATUS = NOT_IMPLEMENTED`** — canonicalization is a project-local profile, honestly labeled.

---

## 14. Architecture Audit

- **B1→B8 layering is monotonic authority-narrowing:** registry(B1)→quality(B2)→contract(B3)→pre-action(B4)→null-broker(B5)→read-only(B6)→write-intent-draft(B7)→commit-simulation(B8). Each layer consumes the prior's proof and **cannot expand** its authority (e.g., B7 consumes B6 read-only output but never writes; B8 consumes B7 escrow but never commits).
- **Readiness ≠ execution:** `commit_executable_now` is always false; B7 `ready_for_future_commit_only` and B8 `B8_V5_ACCEPTED` are evidence-only and both demand downstream revalidation.
- **B8/B9 boundary declared:** B8 emits a Non-Delegable Artifact Seal + B9 Negative-Capability contract + B9 Revalidation contract stating B9 must recompute every factor and must reject B8 artifacts as authority. B9 does not yet exist.
- All modules remain **local-only**; consistent with ViktorAI-style proof-carrying governance.

---

## 15. Production Readiness Audit

See `AUDIT_REPORT_1_PRODUCTION_READINESS.md` for the full category breakdown. Summary: **NOT_PRODUCTION_READY.** Real local logic + tests exist for the entire domain and governance model, but every external effect is a mock, persistence is SQLite/local FS, auth is dev-grade, evidence is unanchored, and there is no deployment/secrets/monitoring/rollback infra.

---

## 16. Gap Matrix

Machine-readable: `AUDIT_REPORT_1_GAP_MATRIX.json`. Top gaps: production persistence, real provider adapters (telephony/email/calendar/payment/AV/OCR/ASR), external evidence anchoring/signing, production auth/SSO/secrets, `app.py`/`ui.py` decomposition, observability/deployment.

---

## 17. Risk Register (25)

| ID | Title | Sev | Likelihood | Modules | Evidence | Mitigation | SP |
|---|---|---|---|---|---|---|---|
| R1 | SQLite/local-FS not production persistence | HIGH | certain | all stores | db.py docstring | Postgres+object store migration | post-B9 infra SP |
| R2 | All external providers are mocks | HIGH | certain | telephony/actions/quotes/scheduling/voice/evidence-scanner | `is_mock=True` grep | real adapters behind existing Protocols | provider-integration SP |
| R3 | Evidence transparency log not externally anchored | HIGH | certain | evidence/transparency.py | header comment | RFC3161/Sigstore/Rekor anchoring | evidence-anchor SP |
| R4 | Dev-grade auth (static secret, no MFA/SSO/rate-limit) | HIGH | high | portal/auth.py | default `dev-secret-change-me` | JWT/OIDC/SSO + secret mgr + login throttle | auth-hardening SP |
| R5 | `app.py` 10,083 LOC monolith | MED | high | portal/app.py | wc -l | split into routers after B9 | refactor SP |
| R6 | `ui.py` 3,691 LOC monolith | MED | high | portal/ui.py | wc -l | modularize UI after B9 | refactor SP |
| R7 | Test↔model implementation coupling | MED | high | tests/ | shape asserts | shared fixtures/base | ongoing |
| R8 | Kernel/test duplication growth | MED | high | ai_employee/tool_*.py | pattern repeat | shared base kernel post-B9 | refactor SP |
| R9 | RBAC engine keeps membership in memory | MED | med | admin/rbac.py | agent report | persist memberships | auth-hardening SP |
| R10 | Two role vocabularies (auth 5 vs rbac 9) | LOW | med | auth.py vs rbac.py | agent report | unify role catalog | auth-hardening SP |
| R11 | Regex-based secret redaction (best-effort) | MED | med | governance/runtime.py | 5 patterns | structured redaction + allowlist | governance-hardening |
| R12 | No native WORM/object-lock | MED | certain | evidence/immutability.py | capabilities all-false | S3 Object Lock | evidence-anchor SP |
| R13 | Mock AV scanner cannot certify safety | MED | certain | evidence/scanners.py | `certifies_production_safety=False` | ClamAV/YARA/CDR | provider SP |
| R14 | No login rate-limit/lockout | MED | med | portal/auth.py | agent report | throttle + lockout | auth-hardening SP |
| R15 | Stateless logout (no revocation) | LOW | med | portal/auth.py | agent report | token blocklist/short TTL | auth-hardening SP |
| R16 | Browser E2E unverified (env flake) | LOW | certain | tests/test_browser_e2e.py | excluded | fix Chromium env, re-enable | test-infra SP |
| R17 | LGGT/certainty-core is a heuristic seam | LOW | certain | certainty_core.py | NullAdapter | build later intentionally | future SP |
| R18 | B8 assurance artifacts must not become B9 authority | HIGH | med (if B9 built wrong) | commit_simulation.py | non-delegable seal | B9 must recompute + reject B8 artifacts | TOOL-B9 |
| R19 | Route-shadowing risk from literal-vs-param routes | MED | low | app.py hoisting | route hoist logic | keep hoist ordering + tests | ongoing |
| R20 | Migration drift if two sessions edit db.py | MED | med | db.py | prior 0284d20 orphan | single-writer discipline | process |
| R21 | No production observability/monitoring | HIGH | certain | — | absent | metrics/tracing/alerting | infra SP |
| R22 | No deployment/secrets/rollback infra | HIGH | certain | — | absent | CI/CD + secrets + rollback | infra SP |
| R23 | Local-only tenant model unproven at scale | MED | med | all | single-node | multi-node + row-level security | infra SP |
| R24 | No distributed idempotency/txn manager | MED | med | ai_employee | local ledgers | durable queue + idempotency store | post-B9 |
| R25 | Prior audit staleness/misclassification | LOW | occurred | docs | this report | keep audits versioned to HEAD | process |

---

## 18. Quality Scorecard (0–10)

| Dimension | Score | Explanation |
|---|---|---|
| Architecture coherence | 9 | Uniform, monotonic B1→B8 layering; clean kernel/store/endpoint/UI pattern. |
| Code maintainability | 6 | Excellent locally, but `app.py`/`ui.py` monoliths + kernel duplication pull it down. |
| Test strength | 9 | 4601 green, deep negative/fault/malicious coverage. |
| Negative testing | 9 | Fault-injection harnesses + fail-closed release gates in every TOOL-B. |
| Security posture (as local system) | 8 | Strong fail-closed/RBAC/tenant/no-execution; dev-grade auth caps it. |
| Tenant isolation | 9 | Server-side scoping on every query, cross-tenant tested. |
| Proof integrity | 9 | Deterministic hashing, self/actor exclusions, non-override blockers, tamper detection. |
| UI honesty | 9 | Consistent honesty labels; no false execution affordances. |
| Production readiness | 2 | Local/SQLite, mock providers, dev auth, no infra — by design, honestly labeled. |
| External integration readiness | 2 | Only Protocol seams + mocks; no real adapter wired. |

---

## 19. Top 20 Recommended Tasks

1. **TOOL-B9** — Controlled Internal Commit Runtime (local reversible, effector-exclusive gate, commit attestation, emergency abort, no external providers).
2. Make B9 **reject B8 artifacts as authority** and recompute all 10 B9 factors (per B8's negative-capability contract).
3. Keep B9 **local-only + reversible**; no external provider yet.
4. Add **B9 fault-injection + release gate** proving no external effect escapes.
5. Auth hardening SP: JWT/OIDC/SSO, MFA, secret manager, login rate-limit/lockout, token revocation.
6. Persistence SP: SQLite→Postgres + local FS→object store (behind existing seams).
7. Evidence anchoring SP: RFC 3161 timestamps / Sigstore-Rekor / SCITT; report signing (KMS).
8. Native WORM (S3 Object Lock) for evidence immutability.
9. Real provider adapters (telephony, email/SMS, calendar, video, PDF, e-signature, payment) — one at a time, behind existing Protocols, gated by B4–B8.
10. Real AV/CDR scanner (ClamAV/YARA) replacing the mock.
11. Decompose `app.py` into per-domain routers after B9 stabilizes.
12. Modularize `ui.py` per section.
13. Shared base for TOOL-B kernels + test helpers to cut duplication.
14. Unify the two role vocabularies (auth 5 vs rbac 9); persist RBAC memberships.
15. Structured (non-regex) secret redaction in governance runtime.
16. Fix Chromium env and re-enable browser E2E in isolation.
17. Production observability (metrics/tracing/alerting) + audit export.
18. CI/CD + secrets + rollback infrastructure.
19. Distributed idempotency + durable transaction manager (post-B9).
20. Keep audit reports versioned to HEAD; single-writer discipline on `db.py`/`app.py`.

---

## 20. Recommended Next SP

**TOOL-B9 — Controlled Internal Commit Runtime for Local Reversible State**, with Effector-Exclusive Gate, Commit Attestation, Emergency Abort, Local-Only Write Scope, and No External Providers.

Rationale (repository evidence): **TOOL-B8 v5 already exists in code and is tested** (`d95be03`, mig v23, 444 tests) — so B8 is *not* next. The B1→B8 governance ladder now ends at simulation-only pre-B9 assurance; the declared next boundary is B9's controlled local commit, which B8's non-delegable seal and B9 negative-capability contract already scaffold the requirements for. **Do NOT** build real external providers, real payment/CRM/evidence mutation, MCP/LLM runtime, or production infra before B9's local reversible commit gate exists.

---

## 21. Final Truth Statement

- **What is already real (local, tested):** the full HVAC-case product domain (CRM, CPQ/quotes, scheduling, evidence trust fabric with real SHA-256/Merkle/RFC-6962-9162 crypto, case graph, completion loop, dashboard, voice/conversation-intelligence logic, telephony call-control logic, admin/RBAC, agent-runtime governance) **and** the entire CORE-A1..A6 + TOOL-B1..B8 proof-carrying governance ladder — 4601 passing non-browser tests.
- **What is local/synthetic:** all persistence (SQLite + local filesystem), all external providers (telephony, email/SMS, calendar, video, PDF, e-signature, payment, AV scanner, OCR, ASR/TTS, web fetch) are deterministic mocks; the evidence transparency log is cryptographically real but **not externally anchored**; auth is dev-grade.
- **What is only proof/governance (not execution):** TOOL-B4..B8 produce decisions, proofs, drafts, escrow, and simulations — **never a real effect**. `commit_executable_now` is always false; B7 escrow and B8 assurance are evidence that still require future B9 revalidation.
- **What is NOT execution:** there is no real commit, no effect release, no B9 activation, no provider/MCP/LLM call, no token/credential issuance, no payment, no CRM/evidence mutation, no message send, no export anywhere in the governance line — forbidden-route scan confirms.
- **What is still missing:** real external runtime + providers, production persistence, external evidence anchoring/signing, production auth/SSO/secrets, observability, deployment, and TOOL-B9+ commit runtime.
- **Why this is NOT production-ready:** it is a **local, deterministic, proof-carrying simulation of a governed AI caseworker** with honest mocks at every external boundary. No external effect is real; no production infrastructure exists. The code says so at the point of every mock/scaffold. It is an excellent, safe, well-tested foundation — and explicitly not a deployed product.

*Generated as documentation only. No product logic, tests, or runtime behavior was modified by this audit.*

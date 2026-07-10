# AUDIT-REPORT-1 — Completed SP Inventory (per-SP detail)

Branch `claude/finalis-ai-casewoker-blueprint-f1huse` · HEAD `d95be03` · migration `v23`.
Statuses: **COMPLETED_AND_TESTED**, **MOCKED_AND_TESTED**, PARTIALLY_IMPLEMENTED, PROMPTED_BUT_NOT_IMPLEMENTED, PLANNED_NEXT, UNKNOWN_NEEDS_CONFIRMATION.

> Note on baseline: the mission brief targets `d28b6f7` (B7 / v22 / 4157). Actual HEAD is `d95be03` (B8 / v23 / 4601). This inventory reflects the real current state.

---

## Product / domain SPs (built first, migrations v1–v8)

### Working Portal + Case Command Center — COMPLETED_AND_TESTED
- Commit/mig: `61c0ea7`,`618a7a3` / v1. Files: `portal/{app,db,ui,auth,seed,store}.py`. Endpoints: `/auth/*`, `/cases/*`, `/dashboard/*`. Migration: base schema (tenants, users, parties, cases, audit_events). Features: FastAPI + SQLite + PBKDF2 auth + RBAC gating + server-rendered UI + hash-chained audit. Mocked: none core. Missing: production deploy. Prod class: NOT_PRODUCTION_READY (SQLite, dev auth).

### Universal Lifecycle — COMPLETED_AND_TESTED
- Commit/mig: `f869bf9` / v2. Files: `lifecycle/*.py` (~1,538 LOC), `state_machine.py`, `scoring.py`, `completion_loop.py`, `certainty_core.py`. Endpoints: `/cases/{id}/transition|lifecycle/*`, `/completion-loop/*`. Migration: `cases.lifecycle_json` + `call_sessions`. Features: LifecycleVector (7-dim), 16-state machine w/ final-state locking, completion-loop invariants (every active case has next action + due time), 11 clamped scoring fns. Tests: **167**. Scaffolded: `certainty_core` LGGT NullAdapter (honest seam). Prod class: NOT_PRODUCTION_READY.

### Quote Builder / CPQ (Q-A..Q-D) — COMPLETED_AND_TESTED (+mock output)
- Commit/mig: `19d7019`,`1e97937`,`0487b91`,`3a5c145` / v3. Files: `quotes/*.py` (~1,154), `portal/quote_store.py`. Endpoints: 24 (`/quotes/*`, `/price-books/*`, `/pricing-rules/*`, `/pricing/*`). Migration: quotes, line items, price books, approvals, change orders, acceptance evidence, payment reqs, pdf docs. Features: full CPQ lifecycle, Decimal money (TEXT), immutability-after-SENT, versioning, AI-no-self-approve, acceptance requires evidence, `case_completed=False` invariant. Tests: **76**. Mocked: PDF, invoice handoff. Scaffolded: e-signature (raises `NotImplementedError`). Prod class: NOT_PRODUCTION_READY.

### Calendar & Scheduling (SCHED-V4) — MOCKED_AND_TESTED
- Commit/mig: `3a334de`,`4e663fc` / v4. Files: `scheduling/engine.py` (316), `portal/scheduling_store.py`. Endpoints: `/scheduling/*`, `/confirm/{token}`. Migration: appointments + events; `provider_is_mock` default 1; SHA-256 confirm-token hash (raw never stored). Features: 12 appt types, availability/slots w/ buffers, double-booking guard, reschedule/cancel/no-show, lifecycle FulfillmentState handoff. Tests: **29**. Mocked: calendar, video. Prod class: NOT_PRODUCTION_READY.

### Evidence Trust Fabric (V-A..V-F, MERKLE-C1, REPORT-C2) — COMPLETED_AND_TESTED (+mock scanner)
- Commit/mig: `0c8e4a7`..`e6fac68`,`64af164`,`fe142f9` / v5,v6,v8. Files: `evidence/*.py` (2,801), `portal/evidence_store.py`. Endpoints: 40 (`/evidence/*` incl. merkle-roots, proof-reports). Migration: evidence_objects, chain_events, access_events, decision_contracts, legal_holds, derivatives, retention_policies, merkle_roots, policy_versions, proof_reports. Features: SHA-256 custody chain, Merkle tree + inclusion proofs, **RFC 6962/9162 consistency proofs (server-verified)**, content-addressed proof reports + D1–D15 algebra + verification replay, retention/legal-hold/WORM domain algebra, facts-not-commands extraction, dual human/agent view. Tests: **269**. Mocked: malware scanner (`certifies_production_safety=False`). Scaffolded: native WORM (capabilities all-false). Missing/blocked: external anchoring, RFC 3161 timestamps, report signing, strict RFC 8785 JCS (`NOT_IMPLEMENTED`). Prod class: NOT_PRODUCTION_READY (local-only unanchored; self-declares production_readiness=false).

### Relationship Core CRM (CRM-A..CRM-D) + CONSOLIDATE-1 — COMPLETED_AND_TESTED
- Commit/mig: `8f9ef28`,`3c9345b`,`efbba3a`,`c13d6bc`,`65c67f5` / v7. Files: `crm/*.py` (1,025), `portal/crm_store.py`. Endpoints: 25 (`/crm/*`). Migration: 13 tenant-scoped tables (parties, contacts, consents, relationship edges, activities, promises, preferences, facts, memory, merge decisions, external refs/sync). Features: own-IP case-first CRM, consent as **non-overrideable** gate, structured memory (human-verified, never raw LLM), relationship graph, scored dedupe/merge (human-decided), opt-in external sync (dry-run default, export off). CONSOLIDATE-1 renumbered CRM v6→v7 to avoid Evidence collision. Tests: **63**. Scaffolded: external CRM adapters. Prod class: NOT_PRODUCTION_READY.

### Telephony / Voice / Actions / Case Graph / Admin / Governance
- **Telephony** `7d017e5`: MOCKED_AND_TESTED, **49** tests — call-control engine, 11-blocker permission gate, anti-harassment guard, consent, dispositions, mock provider (`provider_is_mock`).
- **Voice + Conversation Intelligence** `8379db9`: IMPLEMENTED_AND_TESTED, **37** — dialogue policy, evidence-gated fact acceptance, mock ASR/TTS.
- **Action & Communication** `9b8cb1a`: MOCKED_AND_TESTED, **25** — gate→consent→ratelimit→route→compose→approve→send, mock Novu/Chatwoot/Temporal.
- **Case Graph / Completion Loop / Dashboard** `239a37e`,`618a7a3`: COMPLETED_AND_TESTED, **87** — NBA, missing-info, promises, hash-chained audit, dashboard (AI-worker empty perms), mock WebScout/OCR.
- **Admin / RBAC** `6804d92`: COMPLETED_AND_TESTED, **21** — 9 roles/45 perms, deny-by-default, last-owner/escalation/AI-no-self-approve guards, hashed API keys.
- **Agent Runtime Governance** `a96c025`: COMPLETED_AND_TESTED, **18** — AgentTrace + redaction, policy gate, autonomy budgets, shadow mode, risky-off flags.
- **Portal Wiring W1–W3** `9c6a951`..`7f3a1be`: admin/scheduling/governance UI+APIs (in portal 51 tests).

---

## Governance ladder SPs (migrations v9–v23) — all in `finalis/ai_employee/`

### CORE-A1 Identity — COMPLETED_AND_TESTED
`905a298` / v9. `identity.py`, `authority.py`. Endpoints `/ai-employees/*`. Identity, authority lattice, forbidden actions, human-review gates, no self-approval. Tests: **91**. Guarantees: non-autonomous, tenant-scoped identity.

### CORE-A2 Secure Intake — COMPLETED_AND_TESTED
`bf10d9a`,`e3ab54d` / v10. `tasks.py`, `task_store.py`. Endpoints `/ai-tasks/*`. Canonical envelope, hashes, idempotency, source abstraction, purpose/scope, capability snapshot, tenant isolation. Tests: within `ai_task` 250.

### CORE-A3 Run Ledger + Replay — COMPLETED_AND_TESTED
`00e0452`,`fb5c239` / v11. `run_ledger.py`, `run_store.py`. Endpoints `/ai-runs/*`. Causally verifiable run ledger, event-sourced replay, cancellation/tamper handling. Tests: **103**.

### CORE-A4.1/4.2 Human Approval Gate — COMPLETED_AND_TESTED
`0590e80`,`af4d7fc` / v12,v13. `approvals.py`, `approval_decisions.py`, `approval_store.py`. Endpoints `/ai-approvals/*`. Policy capsule, package, challenge, decisions, non-transferable grants, dual control, no self-approval, consume-check. Tests: **169**. Guarantee: **approval binds a future action; it never executes.**

### CORE-A5 Lifecycle Kernel — COMPLETED_AND_TESTED
`f613489` / v14. `lifecycle.py`, `lifecycle_store.py`. Append-only task state machine, transition ledger, graph verifier, side-effect firewall. Tests: within `ai_task` 250.

### CORE-A6 Artifact System — COMPLETED_AND_TESTED
`80ea4d0` / v15. `artifacts.py`, `artifact_store.py`. Endpoints `/ai-artifacts/*`. Versioned artifacts, ABOM, provenance/claim graph, quarantine, materialization firewall. Tests: **175**.

### TOOL-B1 Tool Capability Registry — COMPLETED_AND_TESTED
`d08c07c` / v16. `tool_registry.py`. Zero-trust descriptors, capability contracts, schema/effect declarations, risk capsules, descriptor-poisoning detection, negative capabilities, admission package/firewall. Tests: **379** (registry 72 + descriptor family 307).

### TOOL-B2 Descriptor Assurance Graph — COMPLETED_AND_TESTED (v5)
`da02379` / v17. `tool_quality.py`. Quality gate, descriptor IR, semantic checks, mutation harness, contradiction checks, non-regression proof, selection boundary. Tests: **383**.

### TOOL-B3 Protocol Contract Proof Kernel — COMPLETED_AND_TESTED (v5)
`dd24cd8` / v18. `tool_contracts.py`. Proof bundle, projection firewall, scope calculus, protocol method firewall, non-interference, effect-trace semantics, broker-readiness certificate. Tests: **445**.

### TOOL-B4 Pre-Action Reference Monitor — COMPLETED_AND_TESTED (v4)
`7d827ff` / v19. `tool_guardrails.py`. Causal action graph, temporal policy automaton, counterfactual denial twin, bypass-attack simulator, no-execution proof, circuit breaker. Tests: `ai_action_*` (~40).

### TOOL-B5 Null Broker — COMPLETED_AND_TESTED (v5)
`7d2c44a` / v20. `tool_broker.py`. Four-plane proof-carrying null broker (NULL_EFFECT_ONLY), safety lattice, multi-request effect + cumulative-risk conservation, null-output non-exfiltration, safe-output projection, fault injection, release gate. Tests: **210**.

### TOOL-B6 Read-Path Runtime — COMPLETED_AND_TESTED (v5)
`48d15f7` / v21. `tool_runtime.py`. Snapshot-bound read-only runtime, read-set attestation, output-provenance bisimulation, canary non-leakage, information budget, read-amplification guard, side-channel budget seal, deterministic replay, no-external/no-write invariant. Tests: **319**.

### TOOL-B7 Write-Intent Escrow Runtime — COMPLETED_AND_TESTED (v4)
`d28b6f7` / v22. `tool_write_intent.py`. Write-intent draft, semantic transaction draft, transaction escrow, escrowed commit-readiness, future-commit-gate placeholder, commit-gate non-existence proof, revalidation debt, semantic rollback-attack fence, action-replay guard, authority-resurrection guard, rollback-replay equivalence, concurrent draft conflict graph, transaction conflict oracle, state-witness quorum, effect-outbox quarantine, readiness non-execution, escrow proof extension. Tests: **491**. Guarantee: **draft-only; `commit_executable_now` always false.**

### TOOL-B8 Pre-B9 Assurance / Commit Simulator — COMPLETED_AND_TESTED (v5)
`d95be03` / v23. `tool_commit_simulation.py`. Machine-checkable pre-B9 assurance envelope, evidence closure net, non-delegable artifact seal, B9 input-contract negative capability, cross-artifact consistency proof, route-topology diff guard, trace-completeness witness, proof-obligation discharge matrix, production-claim poisoning scanner, final CI release evidence gate, v5 proof extension; plus v1–v4 base (B7 consumption gate, state-witness revalidation, shadow dry-run, staged-effect release simulation, semantic rollback fence, differential replay, metamorphic oracle, compliance predicate, no-commit theorem, B9 firewall, artifact quarantine vault, safety case, non-production seal). Tests: **444**. Guarantee: **simulation-only; B8_V5_ACCEPTED is evidence that still requires B9 revalidation; never commits.**

---

## Planned / prompted but NOT implemented (no source in this branch)
- **TOOL-B9** (PLANNED_NEXT — recommended), TOOL-B10..B14 (PROMPTED_BUT_NOT_IMPLEMENTED).
- LGGT certainty-core runtime (intentional Phase-1 seam).
- No CRM/Evidence/etc are "on another branch" — they are all present here (corrects a prior audit error).

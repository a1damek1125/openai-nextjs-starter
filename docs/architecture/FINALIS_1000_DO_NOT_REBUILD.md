# FINALIS 1000 — DO NOT REBUILD

**SP0000 · docs-only.** Baseline HEAD `5c30c60`, migration v27. This is the canonical DO-NOT-REBUILD list for the Finalis 1000 program. It supersedes nothing in `docs/roadmap/ROADMAP_LOCK_1_DO_NOT_REBUILD.md` and `docs/audit/AUDIT_TRACE_1_DO_NOT_REBUILD.md` — it consolidates and re-confirms them against current repository truth.

> **Rule:** these assets EXIST and are TESTED. Do not re-implement, refactor for its own sake, duplicate, or replace with an "alternative". A parallel implementation forks the proof chain / system-of-record and is a P0 violation. Extending via a stable contract or a composition pack is allowed; forking is not.

## A. Governance kernel — never fork any link

`finalis/ai_employee/*` proof-carrying ladder. Determinism + reproducible hashes are load-bearing; a rewrite that changes hashing, the `_VOLATILE` set (`created_at`/`updated_at`/`honesty_labels`), or the fail-closed dominance ladder invalidates every downstream proof.

| Link | Module(s) | Migration |
|---|---|---|
| CORE-A1 identity/authority | `identity.py`, `authority.py` | v9 |
| CORE-A2 task contract | `tasks.py` | v10 |
| CORE-A3 run ledger | `run_ledger.py` | v11 |
| CORE-A4 approvals/grants | `approvals.py`, `approval_decisions.py` | v12–v13 |
| CORE-A5 lifecycle kernel | `lifecycle.py` | v14 |
| CORE-A6 artifacts/claim graph | `artifacts.py` | v15 |
| TOOL-B1 registry+firewall | `tool_registry.py` | v16 |
| TOOL-B2 descriptor assurance | `tool_quality.py` | v17 |
| TOOL-B3 contract proof | `tool_contracts.py` | v18 |
| TOOL-B4 reference monitor | `tool_guardrails.py` | v19 |
| TOOL-B5 null broker | `tool_broker.py` | v20 |
| TOOL-B6 read runtime | `tool_runtime.py` | v21 |
| TOOL-B7 write-intent draft | `tool_write_intent.py` | v22 |
| TOOL-B8 pre-B9 assurance | `tool_commit_simulation.py` | v23 |
| TOOL-B9 transaction twin | `tool_local_transaction.py` | v24 |
| TOOL-B9.1 recovery | `tool_local_recovery.py` | v25 |
| TOOL-B9.2 observatory | `tool_work_observability.py` | v26 |
| EMP-A1 admission fabric | `employee_work_inbox.py` | v27 |

## B. Product engines — never create an alternative

The mission forbids creating an alternative CRM / Evidence / Case Graph / Scheduling / Telephony / CPQ / governance core. All exist and are tested.

| Domain | Canonical implementation | Forbidden duplicate |
|---|---|---|
| CRM | `finalis/crm/*` + `crm_*` (v7) | `CRM2` |
| Evidence | `finalis/evidence/*` + `evidence_*` (v5/v6/v8) | `NewEvidenceCore` |
| Case Graph | `47cb24e` service layer | `AlternativeCaseGraph` |
| Universal Lifecycle | `finalis/lifecycle/*` (v14) | second lifecycle |
| CPQ / Quotes | `finalis/quotes/*` (v3) | second CPQ |
| Scheduling | `finalis/scheduling/*` (v4) | second scheduler |
| Telephony | `finalis/telephony/*` (v2) | second call engine |
| Voice | `finalis/voice/*` | second voice engine |
| Conversation Intelligence | `8379db9` | second CI engine |
| Action & Communication | `finalis/actions/*` | second send pipeline |
| RBAC / Admin | `finalis/admin/*` | `SecondApprovalKernel` (see A) |
| Tenant Isolation | portal + stores | second isolation model |
| Audit Chain | `DbAuditLog` | second audit chain |

Also explicitly forbidden: `SecondRunLedger`, `AlternativeCommitRuntime`, `AlternativeRecoverySystem`.

## C. Infrastructure — reuse, never fork

- **Migration system** (`db.py` `MIGRATIONS` list + `migrate()`): append the next `(version, sql)` tuple; next = **v28**. Never renumber or rewrite an applied migration.
- **Canonical hashing / audit chain** (`_core_hash`, `canonical_json`, `DbAuditLog`): reuse as-is.
- **Portal `create_app()` factory**: extend with a **uniquely-prefixed** endpoint block (the shared closure has already caused a real collision: EMP-A1 `_wi`→`_ewi`, fixed `c95fd27`/`135de7b`). Do not restructure it under SP0000.
- **conftest `Gate` helper**: reuse; new helpers need domain-unique names (a bare `wi()` collided B7↔EMP-A1).

## D. Portal replacement rule (D-0000-15)

The future Employee OS portal is a **presentation modernization above existing/future APIs**. It must NOT silently recreate CRM, Evidence, Case Graph, CPQ, Scheduling, or Governance. Migration is **strangler-style with parity gates** — the old portal keeps serving until replacement parity is proven.

## E. What "do not rebuild" does NOT mean

- Replacing a **mock provider** with a real, governed adapter at Layer 8 (TOOL-B10 / EMP-A2 handoff consumer) is **new work**, not a rebuild.
- Adding a **composition pack** (role/vertical/country/language/company) on top of an unchanged core is allowed (D-0000-14).
- Hardening the substrate (SQLite → PostgreSQL, Layer 10) is a **substrate swap behind stable contracts**, not a domain rewrite.

## F. Duplication scan (this execution)

`ls finalis/ai_employee/ | grep -iE 'crm2|alt|_v2|second|new_'` → **none**. No unacknowledged second implementation of a major domain was found at HEAD `5c30c60`. (If a future audit finds real duplication, it is recorded, not resolved under SP0000.)

# AUDIT-TRACE-1 — DO NOT REBUILD

These assets **exist, are tested, and must not be re-implemented, refactored,
duplicated, or replaced by an "alternative"**. Building a parallel version of any
of them would fork the governance ladder and break the proof chain. (This mirrors
the standing constraint in `docs/roadmap/ROADMAP_LOCK_1_DO_NOT_REBUILD.md`;
AUDIT-TRACE-1 re-confirms it against the current tree.)

## Governance kernel — the crown jewels
The `finalis/ai_employee/*` proof-carrying ladder is a single, coherent,
authority-narrowing chain. Do **not** rebuild any link:

- CORE-A1..A6 — identity/authority, task contract, run ledger, approval gate,
  lifecycle kernel, artifact/claim graph. (migrations v9–v15)
- TOOL-B1..B8 — tool registry & admission firewall, descriptor assurance,
  contract proof kernel, reference monitor, null broker, read-path microkernel,
  write-intent draft runtime, pre-B9 assurance envelope. (v16–v23)
- TOOL-B9 / B9.1 / B9.2 — Transaction Twin + Proof-of-Execution, Recovery Safety
  Case, Work Lineage Observatory. (v24–v26)
- EMP-A1 — Governed Work Admission Fabric. (v27)

Each ships as a **pure deterministic kernel** (`canonical_json` + `_core_hash`,
no I/O/clock/randomness) plus a thin store. The determinism and the reproducible
hashes are load-bearing — a rewrite that changed hashing, the `_VOLATILE` set, or
the dominance ladder would invalidate every downstream proof.

## Product engines — do not create alternatives
The mission forbids creating an **alternative CRM / Evidence / Case Graph /
Scheduling / Telephony / CPQ / governance core**. All already exist and are
tested:

| Domain | Canonical implementation | Do not build a second one |
|---|---|---|
| CRM | `finalis/crm/*` + `crm_*` tables (v7) | ✗ |
| Evidence | `finalis/evidence/*` + `evidence_*` tables (v5/v6/v8) | ✗ |
| Case Graph | `47cb24e` service layer | ✗ |
| Scheduling | `finalis/scheduling/*` + `scheduling_*` (v4) | ✗ |
| Telephony | `finalis/telephony/*` + `call_sessions` (v2) | ✗ |
| CPQ / Quotes | `finalis/quotes/*` + quote tables (v3) | ✗ |
| Governance core | `finalis/ai_employee/*` ladder | ✗ |

## Infrastructure — reuse, don't fork
- **Migration system** (`db.py` `MIGRATIONS` list + `migrate()`): append the
  next `(version, sql)` tuple; never renumber or rewrite an applied migration.
  Current max = **v27**. The next migration is **v28**.
- **Canonical hashing / audit chain** (`_core_hash`, `DbAuditLog`): reuse as-is.
- **Portal `create_app()` factory**: extend with a **uniquely-prefixed** endpoint
  block; do not restructure it (collision hazard — see API map).
- **conftest `Gate` helper class + shared fixtures**: reuse; new helpers need a
  domain-unique name (a bare `wi()` already collided between B7 and EMP-A1).

## What "not rebuild" does **not** mean
It does not mean the external-effect boundary is done. The mocks are *seams*, not
finished integrations. Replacing a mock with a real, governed adapter at the
proper ladder position (TOOL-B10 / EMP-A2) is **new work**, not a rebuild — and
is the correct next direction (see Production Gaps).

# AUDIT-TRACE-1 — Architecture Inventory

Derived by direct inspection of the tree at `HEAD = 135de7b`. Line counts from
`wc -l`.

## Top-level shape
The live product is a single Python package `finalis/` served by one FastAPI app
(`finalis/portal/app.py`) over one SQLite database (`finalis/portal/db.py`) with
a server-rendered UI (`finalis/portal/ui.py`). The repo root also still contains
an upstream **Next.js starter** (from the 2023 initial commits); it is **not
part of the running product** and no `finalis/` code imports it.

## Package map (`finalis/`)
| Package | Lines | Role |
|---|---|---|
| `voice/` | 1106 | Voice Engine: gateway, ASR/TTS routers (mock seams), understanding, dialogue policy |
| `telephony/` | 750 | Call control: mock dial provider, permission gate, consent, dispositions, retry |
| `crm/` | 1025 | Relationship Core CRM (own-IP, case-first) + mock external sync |
| `evidence/` | 2801 | Evidence Trust Fabric: objects, chain, contracts, holds, merkle transparency log, proof reports |
| `quotes/` | 1154 | CPQ: Decimal pricing, approvals, change orders, mock payment/PDF/e-sign |
| `scheduling/` | 325 | Appointments, availability, confirmation tokens, mock calendar/video |
| `admin/` | 427 | Tenant/user/RBAC control plane (9 roles, 45 permissions, deny-by-default) |
| `governance/` | 283 | Agent runtime governance: trace redaction, policy gate, budgets, flags |
| `actions/` | 827 | Action & communication pipeline + NovuMock/ChatwootMock adapters |
| `lifecycle/` | 929 | Universal lifecycle vector, completion rule, outcome invariants |
| `ai_employee/` | 26017 | The proof-carrying governance kernel (CORE-A*, TOOL-B*, EMP-A1) + per-domain stores |
| `portal/` | 17669 | FastAPI app (11895), UI (4058), DB/migrations (1716) |

Plus top-level modules: `state_machine.py`, `scoring*`, `completion_loop.py`,
`autonomy*` (Phase-1 scaffold).

## `ai_employee/` kernel modules (governance ladder)
Every `tool_*`/`employee_*` module is a **pure deterministic reference kernel**
(canonical-JSON hashing, `_core_hash`, no I/O/clock/randomness in the evaluator)
paired with a thin `*_store.py` persistence adapter.

| Module | Lines | SP |
|---|---|---|
| `identity.py` / `authority.py` | 146 / 210 | CORE-A1 |
| `tasks.py` (+ `task_store`) | 382 | CORE-A2 |
| `run_ledger.py` (+ `run_store`) | 419 | CORE-A3 |
| `approvals.py` / `approval_decisions.py` | 359 / 305 | CORE-A4 |
| `lifecycle.py` (+ `lifecycle_store`) | 774 | CORE-A5 |
| `artifacts.py` (+ `artifact_store`) | 775 | CORE-A6 |
| `tool_registry.py` | 1215 | TOOL-B1 |
| `tool_quality.py` | 1657 | TOOL-B2 |
| `tool_contracts.py` | 1715 | TOOL-B3 |
| `tool_guardrails.py` | 1628 | TOOL-B4 |
| `tool_broker.py` | 1823 | TOOL-B5 |
| `tool_runtime.py` | 2208 | TOOL-B6 |
| `tool_write_intent.py` | 2361 | TOOL-B7 |
| `tool_commit_simulation.py` | 1814 | TOOL-B8 |
| `tool_local_transaction.py` | 1627 | TOOL-B9 |
| `tool_local_recovery.py` | 1746 | TOOL-B9.1 |
| `tool_work_observability.py` | 1658 | TOOL-B9.2 |
| `employee_work_inbox.py` (+ store 249) | 1343 | EMP-A1 |

## The proof-carrying pattern (verified, common to all kernels)
- `canonical_json` (sort_keys, `separators=(",",":")`, `allow_nan=False`) → `_sha`.
- `_core_hash(obj, self_key, *extra)` excludes the self hash + `_VOLATILE`
  (`created_at`, `updated_at`, `honesty_labels`) so hashes are reproducible
  across time and rebuild. (Defined in `tool_contracts.py`, reused throughout.)
- Each component `build_*` returns a dict carrying its own `<name>_hash` +
  `_signals`; the orchestrator aggregates signals, strips `_signals`, and a
  fail-closed dominance ladder selects the dominant signal.
- Authority only ever narrows down the ladder: B8 cannot activate B9 (firewall
  proven SEALED); B9.1 recovery cannot create authority or external effect; B9.2
  observatory is read-only and its Proof-of-Work-Outcome authorizes nothing;
  EMP-A1 admits work and prepares a fenced handoff but executes nothing.

## Persistence
- SQLite via `finalis/portal/db.py`; `MIGRATIONS` is an ordered list of
  `(version, sql)` tuples, applied idempotently by `Database.migrate()`.
- **27 contiguous migrations**, **108 `CREATE TABLE` statements**.
- Audit chain persisted via `DbAuditLog` (hash-chained events, reloaded from DB
  head on startup; single-writer-per-DB dev assumption documented in-code).

## External-effect surface
- Real outbound network primitives in non-test code: **0**
  (`requests`/`httpx`/`smtplib`/`boto3`/`urllib.request`/`http.client`).
- Every provider is a Mock/`*_LIKE` seam: `NovuMock`, `ChatwootMock`, telephony
  mock `dial()`, mock calendar/video, mock payment/PDF/e-sign, ASR/TTS routers,
  and the deliberately **inert outbox** in the TOOL-B9+ runtime.
- Contract targets in TOOL-B3 (`MCP_DRAFT_LIKE_READ_ONLY`,
  `OPENAI_APPS_SDK_LIKE_DESCRIPTOR`, `OPENAPI_3_1_LIKE`, …) are *shapes*, with an
  explicit in-code disclaimer: *"This is not OpenAI Apps SDK runtime integration."*

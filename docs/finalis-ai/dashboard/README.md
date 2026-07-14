# Finalis Case Command Center — Documentation Set

**Mission:** answer the owner's one morning question — **"What should I do today to close
more cases and lose fewer clients?"** — from real domain data, in business language, with
one-tap actions. This directory documents the implemented Command Center module
(`finalis/dashboard.py` + `finalis/dashboard_html.py`) that realizes screen 1 of the UX
spec (`../11-ux-dashboards.md`).

## The 7-doc set

| # | Doc | Contents |
|---|---|---|
| 1 | [README.md](README.md) (this file) | Index, mission, honest implementation status, test command, upstream integration seams |
| 2 | [architecture.md](architecture.md) | DashboardService as a projection layer; per-section computation logic as coded; `explain()`; HTML renderer; production plan |
| 3 | [data-contract.md](data-contract.md) | The five contract objects with field tables + HVAC example JSON; RBAC role-permission matrix; PII-safe display |
| 4 | [api-contracts.md](api-contracts.md) | The 15 REST endpoints (Designed) mapped to implemented service methods and response shapes |
| 5 | [ux-spec.md](ux-spec.md) | Layout, the 11 components and their behaviors, badges/one-click approve, filters (Designed), the every-recommendation rule, empty/loading/error states |
| 6 | [test-plan.md](test-plan.md) | The 13 mandated scenarios mapped to passing tests, the E2E approve flow, the `explain()` language test, next test stages |
| 7 | [../11-ux-dashboards.md](../11-ux-dashboards.md) | The original UX & Dashboards spec — this module implements a slice of its screen 1 (Home Dashboard — Case Command Center) |

## Honest status

| Layer | Status |
|---|---|
| **Service layer** (`finalis/dashboard.py`, `DashboardService`) — all 13 dashboard sections/operations computed from real domain objects (`Case`, `MissingItem`, `Promise`, approval drafts, `AuditLog`) | **Implemented and tested** |
| **Server-rendered HTML view** (`finalis/dashboard_html.py`, `render_dashboard`) — one self-contained page with all 11 components; doubles as print/email digest | **Implemented and tested** |
| **Tests** — 19 tests in `tests/test_dashboard.py` covering the 13 mandated scenarios, RBAC/tenant isolation, and an E2E approve flow | **Passing** |
| **Data feed** — in-memory registration API (`register_case`, `register_approval`) fed by fixtures | **Implemented** (production DB queries replace it — see below) |
| **Next.js UI** (real browser dashboard) | **Designed** (see `architecture.md` §Production plan and `ux-spec.md`) |
| **REST endpoints** (HTTP server over the service) | **Designed** (see `api-contracts.md`) |

There is no HTTP server and no React code in this module today. What exists is the full
computation layer with a working, tested server-rendered HTML view over it. Every number and
recommendation on the page is derived from real domain objects — no fake aggregates.

## Test command and result

```bash
python3 -m pytest tests/test_dashboard.py -q   # 19 passed
python3 -m pytest tests/ -q                    # 204 passed (repo-wide)
```

## How it consumes Case Graph / Completion Loop / ACE

`DashboardService` is a read-side **projection**: it owns no domain state of its own and
persists nothing. It receives domain objects through two registration seams:

- **`register_case(case, *, title, client_name, offer_sent_at=None)`** — the Case Graph
  (`finalis/models.py` `Case`, with its `MissingItem`s and `Promise`s attached, state from
  `finalis/state_machine.py`, `next_best_action` / `next_action_due_at` from the Completion
  Loop's NBA output) is handed to the dashboard here. `offer_sent_at` feeds the Offer
  Follow-Up Board.
- **`register_approval(*, tenant_id, case_id, action_type, draft_message, reason,
  risk_level, created_at, expires_at=None)`** — drafts produced by the Action &
  Communication Engine (ACE) that require human approval land in the Approval Queue here.

In the tests these seams are fed by an HVAC fixture (`tests/test_dashboard.py::hvac_fixture`).
**In production the same seams are replaced by tenant-scoped database queries** — the section
methods (`summary`, `action_queue`, `approval_queue`, …) keep the exact same signatures and
return the exact same contract objects, so the view layer (HTML today, Next.js later) does
not change. Decisions flow back the other way: `decide()` writes
`HUMAN_APPROVAL_GRANTED`/`HUMAN_APPROVAL_REJECTED` to the shared hash-chained `AuditLog`
(`finalis/audit.py`), which is what unblocks the ACE action.

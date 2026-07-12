# SP0008 — Canonical Contract Surface Inventory: Swarm Review

This is the honest build-and-review record for SP0008. It documents how the
inventory was built, what independent swarm agents found, every confirmed
false-negative escape and its fix, and the limitations that remain openly
recorded rather than hidden.

## 1. What was built

A deterministic, evidence-grounded, machine-queryable inventory of the contract
surfaces **actually implemented** in the repository — real repository records,
not schemas or mocks — under `tools/contracts_inventory/` (21 modules) with a
24-subcommand CLI, plus materialized artifacts under `docs/contracts_inventory/`.

Materialized from the real tree (deterministic, byte-reproducible):

| Surface kind | Count |
|---|---|
| HTTP_ROUTE | 423 |
| DB_TABLE | 107 |
| DB_MIGRATION | 27 (frontier v27) |
| AUDIT_EVENT | 174 |
| RUN_LEDGER_EVENT | 35 |
| PROOF_ARTIFACT | 429 |
| STATE_MACHINE / STATE_TRANSITION | 8 / 82 |
| CONFIG_KEY | 10 |
| **Total surfaces** | **1295** |

1296 raw detector observations → 1295 canonical surfaces; 610 MATCHED_EXISTING
under 5 SP0007 parent descriptors, 675 NEW_SURFACE, 10 DUPLICATE_CANDIDATE;
3616 grounded evidence claims; 149 grounded behavioral witnesses. Findings after
hardening: **P0 = 0, P1 = 0, P2 = 4890** (all advisory — honest UNKNOWNs, dark
consumers, unresolved criticality, residual caveat). All four bounded model
checks HOLD.

## 2. Swarm process

- **SWARM-A (repository archaeology).** Mapped the 11 real code-pattern areas so
  detectors parse actual surfaces, not assumptions. Key corrections it supplied:
  `HTTPException` is positional not keyword; 30 routes register via
  `add_api_route` with string-concatenated paths; stacked decorators = multiple
  routes; state tables are built dynamically; two event conventions
  (UPPER_SNAKE + dotted) coexist. These directly shaped the detectors and the
  declared blind-spot registry.
- **SWARM-DOCS.** Wrote the constitution, roadmap-identity report, research
  register, and README — each verified against the code and the materialized
  artifact (it independently caught that CONFIG_KEY is 10 deduped surfaces, not
  11 observations).
- **SWARM-REDTEAM.** Adversarial false-negative hunt across all modules. Found
  **10 real escapes** (2 P0, 4 P1, 4 P2). Every one was fixed and regression-
  locked. See §3.

## 3. Confirmed false-negative escapes and fixes

Each is pinned shut by a test in `tests/test_contracts_inventory_mutation.py`.

| # | Sev | Escape | Fix | Lock |
|---|---|---|---|---|
| E1 | P0 | `closure.check_no_external_effect` was a **denylist** of call names — `subprocess.run`, `requests.get`, `os.execv`, etc. slipped through and reported the boundary clean. | Replaced with a fail-closed **import allowlist** (only stdlib-safe modules) plus a forbidden-`os.*` set. | M21 |
| E2 | P0 | `check_frontier_unchanged` used a regex `(\d+, """` that only matched triple-double-quoted migrations — a `(28, '''…''')` product migration was invisible, so "frontier v27" reported satisfied while v28 existed. | Read migration versions from the **AST** `MIGRATIONS` list. | M22 |
| E3 | P1 | The Merkle genome sealed only kind/name/fingerprints — a **table's DDL and a migration's SQL were never fingerprinted**, so dropping `tenant_id` from a table did not move the genome root (violates AC-0008-220). | The DB detector now hashes the normalized CREATE-TABLE column body (`ddl_material`) and the migration SQL (`sql_material`) into the surface shape. | M23 |
| E4 | P1 | Handler **function rename** (cosmetic) moved the material fingerprint → spurious genome drift. | `handler` added to `VOLATILE_KEYS` (stripped from material). | M7 |
| E5 | P1 | Envelope `content_digest` check was guarded by truthiness — an envelope with **no** digest validated as sealed. | Require presence; a missing digest is an unsealed envelope, P0. | M24 |
| E6 | P1 | Reachability tagged `EXACT` when **≥1** edge resolved — a resolved table edge masked an unresolved external hop (f-string event, `httpx.post`). | `derive_edges` tracks unresolved effectful references; exactness is `EXACT` only when nothing was left unresolved, else `UNKNOWN`. | M25 |
| E7 | P1 | The parallel-registry guard was **never called** by the pipeline and its predicate (`startswith("CT-")`) could never match a minted `CS-` id. | Wired `parallel_registry_findings` into `build_inventory`; predicate now also flags any `parent_contract_id` not present in the loaded SP0007 descriptor set. | M16, M26 |
| E8 | P2 | `_resolve_parent` used bidirectional `startswith`, so `finalis/portal/app` would match `approvals.py` and an empty descriptor path matched everything → false MATCHED_EXISTING. | Path-component-boundary matching; empty descriptor paths rejected. | M17 |
| E9 | P2 | Detectors are file-scoped (routes only from `app.py`/`ui.py`, etc.) but this was **not a declared blind spot** — a silent omission. | Added explicit BLIND_SPOTS entries for file-scoping and non-literal migration SQL. | (registry) |
| E10 | P2 | A wildcard path-convention owner (`CORE-*`) was reported as a resolved owner. | `OWNERSHIP_UNRESOLVED` now fires whenever ownership is not resolved to a specific capability. | (analysis) |

**Classes with no escape found** (independently confirmed by red-team): truthy-
string bool coercion (all strict `is True` / `== YES`), non-determinism (every
aggregation sorts before emitting; no time/random), and spurious *completeness*
claims (residual is gated and labeled advisory).

## 4. Honest limitations (recorded, not hidden)

- **Effect reachability is mostly UNKNOWN** (358 of 423 routes). The portal
  defines handlers as closures inside `create_app` with heavy indirection;
  static edge derivation resolves only literal table writes and literal event
  emissions. This is reported as `exactness: UNKNOWN`, never as "no effect."
- **Residual unseen-surface count is NOT ESTIMABLE.** The detector fleet is
  kind-partitioned, so effective recapture is ~0.08% — far below the threshold
  where Chao1 has controlled variance. The tool refuses to emit a number and
  says the residual is UNKNOWN; completeness is argued from the declared-
  universe floor + the blind-spot registry instead.
- **Dynamic surfaces are declared blind spots**, not silent gaps:
  string-concatenated route paths, runtime-synthesized state transitions,
  f-string event names, and indirect config reads.
- **Criticality is largely UNKNOWN per surface** and reported as ELEVATED
  (fail-closed) rather than assumed safe; each unknown becomes a ranked probe in
  the Value-of-Information plan.

## 5. Change boundary — verified clean

Zero product-runtime change, zero product migration (frontier stays v27, checked
via AST), zero external effect (fail-closed import allowlist over the package),
never imported by product code (`finalis/`). `closure.check_boundary` returns
empty on the shipped tree, and the tooling passes its own hardened check.

## 6. Test status

`tests/test_contracts_inventory_core.py` (core invariants),
`tests/test_contracts_inventory_analysis.py` (per-module behavior), and
`tests/test_contracts_inventory_mutation.py` (26 red-team regression locks) all
pass. The inventory is deterministic across rebuilds and re-validates against a
fresh build.

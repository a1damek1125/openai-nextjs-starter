# SP0008 — Roadmap Identity Report

Mandatory roadmap-identity preflight for **SP0008 — FINALIS Canonical Contract
Surface Inventory, Repository Intelligence & Dependency Truth Constitution**,
executed before any tracked-file modification, per the SP-AUTHOR roadmap-identity
rule.

## 1. Baseline (verified at execution time)

| Field | Value |
|---|---|
| EXECUTION_DATE | 2026-07-12 |
| BRANCH | `claude/finalis-ai-casewoker-blueprint-f1huse` |
| STARTING_HEAD | `4eda536` (SP0007 pushed) |
| PREDECESSOR CHAIN | SP0000–SP0007 complete (SP0007 `4eda536`, SP0006 `d6ac046`, SP0005 `610e1e3`, SP0004 `34ebb4e`/`e82ca87`) |
| LATEST_MIGRATION | v27 (unchanged; SP0008 adds none) |
| PRODUCT RUNTIME | untouched (`finalis/` unmodified by this mission) |
| IMPLEMENTATION SURFACE | `tools/contracts_inventory/` + `docs/contracts_inventory/` |
| REGISTRY POPULATED | SP0007 `docs/compatibility/FINALIS_CONTRACT_DESCRIPTORS.json` (10 descriptors) |

## 2. Canonical identity

| Field | Value |
|---|---|
| Canonical SP id | **SP0008** |
| Canonical roadmap title | **"Existing API/UI/Data Contract Inventory"** (Program Twin, `docs/program/FINALIS_1000_PROGRAM_REGISTRY.json`; block `PROGRAM`, node `SP0008`) |
| V2 mission title | *FINALIS Canonical Contract Surface Inventory, Repository Intelligence & Dependency Truth Constitution* |
| Canonical mission class | PROGRAM-layer constitution (governance tooling + docs) |
| Expected change boundary | zero product-runtime change · zero product migration (frontier stays v27) · zero external effect · never imported by product code |
| Expected artifacts | `tools/contracts_inventory/`, `docs/contracts_inventory/*` |

## 3. Detected conflicts with this V2

**None material.** The repository's canonical SP0008 scope — *"Existing API/UI/Data
Contract Inventory"* — is **semantically equivalent** to this V2. The V2 is the
same mission with stronger explicit requirements: real-record (not schema/mock)
discovery, multi-detector union with declared blind spots, identity resolution
against the SP0007 registry, bitemporal + W3C PROV evidence with contradiction
preservation, an eight-dimension criticality vector with conjunctive hard flags,
effect reachability / dominators / minimal cut sets, ownership with
producer/consumer certainty typing, source-grounded behavioral witnesses,
capture-recapture residual estimation reported honestly, Value-of-Information
probe planning, advisory agent-readiness, and a Merkle Contract Genome.

Per the roadmap-identity rule: **use the repository title, retain the compatible
stronger V2 requirements, continue.** `BLOCKED_BY_SP0008_SCOPE_MISMATCH` does
**NOT** apply.

## 4. No parallel registry

SP0008 **populates the SP0007 Contract Registry**; it does not stand up a
competing one. Every discovered surface is resolved against
`FINALIS_CONTRACT_DESCRIPTORS.json`: those whose contract-kind and evidence path
fall within a descriptor's declared `source_paths` are `MATCHED_EXISTING` under
that descriptor's `CT-*` id; the rest are honestly `NEW_SURFACE`. In the
materialized run, 610 of 1295 surfaces matched existing descriptors under 5
registry parents (`CT-HTTP-CASES`, `CT-DB-SCHEMA`, `CT-EVENT-RUN-LEDGER`,
`CT-WF-CASE-FSM`, `CT-PROOF-RUN-EVENT`), 675 are new, and 10 are duplicate
candidates. Any surface minting its own `CT-*` id would trip
`PARALLEL_REGISTRY_DETECTED` — the no-parallel-registry rule is a machine check,
not a promise (`normalize.parallel_registry_paths`).

## 5. Compatibility decision

**PROCEED** under the canonical repository identity. The V2's stronger
requirements are additive hardening of the same scope; nothing in the V2
contradicts the Program Twin, the SP0000–SP0007 constitution chain, or the
SP0007 registry it populates.

## 6. Resolution taken

Implementation proceeds as a deterministic, stdlib-only `tools/contracts_inventory/`
kernel plus `docs/contracts_inventory/` artifacts, referencing (never rebuilding)
SP0000–SP0007 and the product's real contract surfaces — routes, tables,
migrations v1–v27, run-ledger and audit events, state machines, and proof
artifacts. **No product file changes; no migration v28; no external effect; the
tooling is never imported by `finalis/`.** These boundary invariants are checked
on every build (`closure.check_boundary`, P0 `BOUNDARY_VIOLATION`), and the
materialized run reports zero boundary violations, zero P0, and zero P1 findings.

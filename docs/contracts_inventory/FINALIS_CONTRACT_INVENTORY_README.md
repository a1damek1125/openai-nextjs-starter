# FINALIS Contract Surface Inventory — CLI README (SP0008)

A machine-queryable command-line interface over the Canonical Contract Surface
Inventory. Every subcommand answers one governance question deterministically and
prints canonical JSON (diffable, pipe-friendly). The inventory is built once from
source per invocation, or loaded from a committed artifact with `--from`.
**Nothing here executes anything against the running product.**

## Running

```
python -m tools.contracts_inventory [--root PATH] [--json] <command> [args]
```

- `--root PATH` — repository root (default `.`). Run from the repo root, or pass
  the repo path explicitly.
- `--json` — emit compact canonical JSON (byte-diffable). Without it, output is
  pretty-printed, sorted JSON.

Building the full inventory is deterministic: two runs on an unchanged tree
produce byte-identical output. The committed artifact lives at
`docs/contracts_inventory/FINALIS_CONTRACT_INVENTORY.json`; pass it via `--from`
to query it without rebuilding.

## Commands

Below, `<id>` is a surface id (`CS-…`) **or** a canonical name (e.g.
`"GET /cases"`).

### Orientation

```bash
# Mission identity, registry it populates, and the change boundary
python -m tools.contracts_inventory roadmap_identity

# The detector fleet: names, capability matrix, and declared blind spots
python -m tools.contracts_inventory detectors

# Raw grounded observations (before reconciliation)
python -m tools.contracts_inventory discover
```

### The inventory

```bash
# Full inventory object (large)
python -m tools.contracts_inventory inventory

# Just the headline: version, counts, genome roots, readiness, model checks
python -m tools.contracts_inventory inventory --summary

# Query a committed artifact instead of rebuilding
python -m tools.contracts_inventory inventory --summary \
    --from docs/contracts_inventory/FINALIS_CONTRACT_INVENTORY.json
```

### A single surface

```bash
# Full canonical record for one surface
python -m tools.contracts_inventory surface "GET /cases"

# Why is this surface's criticality / reachability / consumers UNKNOWN?
python -m tools.contracts_inventory why_unknown "GET /cases"

# Consumers of a surface, with certainty typing (UNKNOWN, never zero)
python -m tools.contracts_inventory consumers "case.created"

# Grounded behavioral witnesses attached to a surface
python -m tools.contracts_inventory witnesses "POST /cases"
```

### Ownership and identity

```bash
# Surface counts grouped by owning capability tag (None-owned last)
python -m tools.contracts_inventory owners

# Preserved detector/evidence contradictions (never averaged away)
python -m tools.contracts_inventory contradictions
```

### Dependency truth: reachability, dominators, cut sets

```bash
# Effect reachability for a surface (EXACT vs UNKNOWN — fail-closed)
python -m tools.contracts_inventory trace "POST /cases"

# What effect sinks + criticality a surface reaches
python -m tools.contracts_inventory impact "POST /cases"

# Dominators: surfaces that gate all paths from this surface
python -m tools.contracts_inventory dominators <id>

# Minimal cut sets from this source to effect sinks
# (tagged EXACT / BOUNDED / LIMIT_REACHED)
python -m tools.contracts_inventory cut_sets <id>
```

### Completeness and next steps

```bash
# Negative-space check: declared floor vs detector materialization
python -m tools.contracts_inventory negative_space

# Residual estimate — reports NOT ESTIMABLE for the kind-partitioned fleet
python -m tools.contracts_inventory residual

# Top-ranked Value-of-Information probes (plan only; never executed)
python -m tools.contracts_inventory next_probe -n 10
```

### Readiness (advisory; grants no authority)

```bash
# Whole-inventory readiness summary
python -m tools.contracts_inventory agent_readiness

# Readiness diagnostic for one surface (NO_KNOWN_BLOCKER vs NOT_READY)
python -m tools.contracts_inventory agent_readiness "POST /cases"
```

### Genome, boundary, attestation, validation

```bash
# The Merkle Contract Genome: per-class roots + global root
python -m tools.contracts_inventory genome

# Change-boundary invariants (no product import, no external effect, v27 frontier)
python -m tools.contracts_inventory boundaries       # alias: closure

# Proof envelope + inventory digest (non-authoritative attestation)
python -m tools.contracts_inventory attest

# Re-derive from source and validate; exit 0 iff no P0/P1 findings
python -m tools.contracts_inventory validate

# Diff two committed inventories (genome move, added/removed/changed surfaces)
python -m tools.contracts_inventory diff \
    --old OLD_INVENTORY.json --new NEW_INVENTORY.json
```

## Notes on behavior

- **`validate` exit code** — 0 when the report is valid (no P0/P1), 1 otherwise.
  Honest UNKNOWNs are P2 and do not fail validation; a stale or non-deterministic
  build, a genome mismatch, an envelope mismatch, or a boundary violation does.
- **`--from` availability** — most read-only query commands accept `--from` to
  load a committed inventory. `discover`, `detectors`, `roadmap_identity`,
  `boundaries`/`closure`, `dominators`, `cut_sets`, and `diff` build/read from
  source directly (they take `--root` and/or explicit paths).
- **Determinism** — all output is canonical JSON with sorted keys, so command
  output can be committed and diffed across runs.

## What the numbers look like (committed run)

`inventory --summary` over the committed artifact reports 1295 canonical surfaces
from 1296 observations, 3616 evidence claims, 149 grounded witnesses, findings
P0 = 0 / P1 = 0 / P2 = 4890, and a residual estimate of **NOT ESTIMABLE**
(kind-partitioned detector fleet, effective recapture ≈ 0.08%). The global genome
root is
`7269f08cd7d53679cae6ce3b134a00d6dd6146fde0c60e712a065a711be377b1`.

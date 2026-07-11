# FINALIS 1000 — Architecture Drift Observatory (SP0001)

Green tests are necessary but **not sufficient** — 2026 research (SlopCodeBench,
AI-Generated Smells) shows structural erosion is a *trajectory* property invisible
at any single green checkpoint. The Drift Observatory records longitudinal
architecture snapshots so slow decay becomes visible (D-0001-10).

## Snapshot vector (per commit)

`python -m tools.architecture drift --json` emits:

| Metric | Meaning |
|---|---|
| `capabilities` | declared capability count |
| `capability_edges` | cross-capability dependency edges |
| `sccs` / `cyclic_sccs` | strongly-connected components / non-trivial cycles |
| `unowned_nodes` | modules with no canonical owner |
| `active_waivers` | waivers in force |
| `routes` / `tables` / `migrations` | observed counts |
| `effect_observations` | outbound/dynamic-import observations |
| `p2_findings` | advisory findings this commit |

## Drift is not failure (D-0001-09, §12.3, INV-0001-14)

A metric delta is **advisory**. Architecture may intentionally evolve; the
question the immune system asks is *declared? allowed? reviewed?* — answered by
the Change Intent + conformance gate, not by a metric threshold. The observatory
**never** silently becomes an uncalibrated hard blocker:

- Hard violations (P0/P1) live in the conformance gate and stay Boolean.
- Drift metrics establish observation first; **no production-blocking threshold
  is set before calibration** (D-0001-10). After enough history, an EWMA-based
  advisory change signal may be enabled — still advisory.

## Longitudinal use

`tools/architecture/drift.py` provides `snapshot_vector`, `delta(prev, cur)`,
`append_history`, and `ewma`. A CI job appends one vector per merged commit to a
history artifact; reviewers watch `capability_edges`, `cyclic_sccs`,
`unowned_nodes`, and `effect_observations` trends. A rising `cyclic_sccs` or a
new `effect_observations` entry is an early erosion / effect-gate signal to
investigate — before it becomes a hard violation.

## Baseline (HEAD `e1b6b5c`)

32 capabilities · 80 cross-capability edges · 1 known baseline SCC (the monolith
`app.py` composition root + shared `models`/`db`, declared in the twin's
`dependency_baseline`, refactor is a non-goal) · 0 unowned nodes · 0 active
waivers · 366 routes · 106 tables · 27 migrations · 2 effect observations (both
dynamic imports in `evidence_store`, advisory) · 0 network effects.

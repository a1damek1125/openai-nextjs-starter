# FINALIS — Semantic Drift Observatory (SP0002)

Longitudinal, **advisory** metrics over Canonical Concept Registry snapshots.
Hard semantic validity stays Boolean (`ValidSemanticEpoch ⟺ P0=0 ∧ P1=0`,
INV-0002-04); drift metrics **never silently become an uncalibrated hard
blocker** (D-0002-25 / AC-0002-74).

## Snapshot vector (`python -m tools.semantics drift --json`)

| Metric | Meaning |
|---|---|
| `concepts` | canonical concept count |
| `active_revisions` | concepts with status ACTIVE |
| `aliases` / `forbidden_aliases` | alias surface / declared forbidden terms |
| `ambiguities` | surface terms resolving to >1 concept |
| `quarantine_count` | items held in semantic quarantine |
| `epistemic_violations` | invalid transitions + LLM-admission attempts |
| `unmapped_projections` | projection targets not recognized |
| `translation_conflicts` | one label denoting >1 concept in a language |
| `lggt_conflicts` | two concepts claiming one predicate family |
| `breaking_changes` | breaking meaning changes this epoch |
| `p2_findings` | advisory findings this snapshot |

## Drift is not failure (D-0002 §12.3)

A metric delta is advisory. Meaning may evolve — the question the constitution
asks is *declared? compatible? shadow-tested? replayed?* — answered by the
Semantic Change Intent + Semantic Transaction gate, not by a metric threshold.
No production-blocking threshold is set before calibration; after enough history
an advisory change signal may be enabled — still advisory. Hard violations
(P0/P1) live in the validator and stay Boolean.

## Baseline (genesis epoch `epoch-0001-genesis`, HEAD 19413f2 era)

33 concepts · all ACTIVE (2 PROPOSED: `skill.skill`, `memory.experience`) ·
0 ambiguities · 0 quarantine · 0 epistemic violations · 0 translation conflicts ·
0 LGGT conflicts · registry validates P0=0/P1=0/P2=0.

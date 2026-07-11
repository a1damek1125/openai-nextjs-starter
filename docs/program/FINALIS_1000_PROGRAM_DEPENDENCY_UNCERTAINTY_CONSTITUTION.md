# FINALIS 1000 — Program Dependency & Uncertainty Constitution (SP0003)

**Position in program:** after SP0000 (Master Architecture Lock), SP0001
(Architecture Immune System), SP0002 (Semantic Operating Constitution).
**Mission type:** program architecture, dependency formalization, uncertainty-aware
planning. **Runtime business feature:** none. **Product behavior change:** none.
**DB migration added:** none (migration frontier remains v27).

This constitution turns the Finalis 1000 roadmap from a numbered list into a
formally validated, uncertainty-aware, evidence-backed **program control model** —
the third Finalis twin (the **Program Digital Twin**), distinct from the
Architecture Digital Twin (SP0001, *where capability lives*) and the Semantic
Domain Twin (SP0002, *what a concept means*).

## Core principles

1. **NO HARD DEPENDENCY WITHOUT EVIDENCE** — an ACTIVE hard prerequisite must
   carry rationale, a failure-if-bypassed statement and evidence refs, else it is
   `UNPROVEN_HARD_DEPENDENCY` (INV-0003-02).
2. **NO PARALLELISM ASSUMED FROM THE ABSENCE OF A HARD EDGE** — resource
   conflicts and temporal constraints are applied at scheduling (INV-0003-05).
3. **NO PROBABILISTIC MODEL MAY OVERRIDE A HARD SAFETY GATE** — gates are Boolean;
   P2 advisory signals never override P0/P1 (INV-0003-12).
4. **UNKNOWN IS NOT FALSE, AND UNCERTAIN IS NOT PROVEN** — UNKNOWN durations are
   never fabricated (D-0003-11); uncertain dependencies never block canonical
   readiness but surface uncertainty warnings (D-0003-34).

## Seven distinct structures (never collapsed into one graph)

| Structure | Purpose | Cycles? |
|---|---|---|
| `H_P` Prerequisite Hypergraph | typed AND/OR/threshold prerequisites | must be acyclic (active backbone) |
| `G_G` Gate Graph | Boolean hard gates, scenario-invariant globals | n/a |
| `G_C` Resource / Conflict Graph | exclusive resources / capacities | n/a |
| `G_F` Rework / Feedback Graph | MAY_INVALIDATE / REVERIFY / … | **cycles allowed** (feedback) |
| `G_R` Risk Correlation Graph | shared risk assumptions (advisory) | n/a |
| `G_E` Completion Evidence Graph | evidence-derived completion | n/a |
| `T` Temporal Constraint Network | difference constraints x_j − x_i ≤ c | negative cycle ⇒ inconsistent |

## Prerequisite logic (D-0003-01/02/03)

A prerequisite hyperedge `e = (T_e, h_e)` is satisfied by its own logic:
`ALL_OF` (conjunction), `ANY_OF` (disjunction), `AT_LEAST_K_OF_N` (threshold).
Multiple hyperedges sharing a head are **alternative** prerequisite paths
(disjunction), so `(A ∧ B) ∨ (C ∧ D)` is two `ALL_OF` hyperedges `{A,B}→X` and
`{C,D}→X`. A joint prerequisite is **never** collapsed into ambiguous independent
pairwise edges (INV-0003-03). SP numbering creates **no** dependency (INV-0003-04);
every edge here is grounded in an explicit roadmap `deps` entry.

## Hard validity

```
ValidScenarioProgram  ⇔  HardBackboneAcyclic ∧ HardGatesValid ∧ NoUnprovenActiveHardDependency
```

A partial program update can never be declared valid (INV-0003-19): the validator
is valid only when zero P0 and zero P1 remain.

## Three criticality modes (never silently substituted, D-0003-18)

- **Structural** — unit weights; dependency depth / serialization.
- **Estimated** — CPM (ES/EF/LS/LF/slack) over explicit estimates only.
- **Empirical / Bayesian / Monte-Carlo** — advisory, reproducible from a declared
  seed; a forecast never creates or removes a hard dependency (INV-0003-13).

## Uncertainty, Value-of-Information & resilience

Dependency uncertainty has its own lifecycle (`PROPOSED → UNDER_RESEARCH →
VERIFIED → ACTIVE`); only `ACTIVE` blocks readiness. VOI is computed only where a
grounded probability, loss and cost model exist — otherwise `VOI_NOT_CALIBRATED`,
never fabricated (D-0003-35). VOI may never bypass mandatory safety, authority,
tenant-isolation, human-oversight, regulatory or architecture work (INV-0003-18).
Program dominators (single unavoidable nodes) and bounded minimum cut-sets
(alternative-blocker sets) are computed on the **compiled AND/OR scenario graph**;
for an uncompiled scenario the honest answer is `CUT_ANALYSIS_REQUIRES_SCENARIO`
(D-0003-30). The resilience index is descriptive, never a production gate
(D-0003-31).

## Proof-Carrying Program Plan Envelope

Every validated program state emits a deterministic envelope over the canonical
structure and the derived analyses that were validated together. It is
**evidence, not execution authority** (INV-0003-20): it proves *which* program
model + analyses were validated together, not that the future will occur as
forecast.

## Twin separation & non-goals

The Program Digital Twin is for **development-program planning only** and is never
reused as runtime business state. SP0003 implements no product feature, no runtime
scheduler, no Employee/Worker orchestration, no Temporal, no mandatory OR-Tools,
and no autonomous roadmap rewriting (§7). The solver is a replaceable
`ScheduleSolverAdapter`; SP0003 ships only a deterministic, stdlib-only greedy
advisory reference solver that never claims optimality.

## LLM authority boundary (§17.5)

LLMs may *propose* missing dependencies, scenario candidates, possible rework
edges and research questions. They may never alone activate a hard dependency,
pass a gate, mark completion, admit Bayesian evidence, compute a critical path or
cut-set, or approve a program proof envelope.

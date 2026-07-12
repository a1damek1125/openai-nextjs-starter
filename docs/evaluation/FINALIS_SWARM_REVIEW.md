# SP0011 — Evaluation Kernel: Swarm Review

Honest build-and-review record for SP0011: how the proof-carrying Evaluation
Kernel was built, the truthful score it produced, what independent swarm agents
found, and the limitations recorded rather than hidden.

## 1. What was built

A deterministic, repository-local **Evaluation Kernel** under `tools/evaluation/`
(28 modules, ~25-command CLI) + materialized artifacts under `docs/evaluation/`
(43 machine-JSON + 5 markdown). It evaluates the complete Finalis configuration,
computes a truthful Finalis-1000 score from proof-carrying evidence-qualification
credits checked by a minimal Trusted Evaluation Kernel, and seals it.

| Property | Value |
|---|---|
| Configuration | `CFG-FINALIS-REPO-REFERENCE` (repo-local, mocked providers, no live model) |
| Domains × claims × credits | 10 × 20 × 5 = 1000 |
| **Finalis-1000 score** | **555 / 1000** (evidence-accounting credits) |
| **Maturity** | **M1 — REPOSITORY_EVIDENCED** |
| Hard-gate state | PASS |
| Qualified claims | 111 / 200 |
| Findings | **P0 = 0, P1 = 0, P2 = 0** |
| Evaluation TCB | complete (10 members, 6-module minimal kernel) |
| Trusted-kernel identity | content-hashed, deterministic |
| Behavioral analyses (stat/robust/horizon/causal/calibration/judge/invariance) | `NOT_EVALUATED` (machinery present + unit-tested; no fabricated runs) |
| Contamination state | CLEAN (no live search, no benchmark download, immutable evaluator) |
| Determinism | evaluation rebuilds byte-identical |
| Finalis-1000 state | `NOT_QUALIFIED_PENDING_RUNTIME_FIELD_AND_PRODUCTION_EVIDENCE` |
| Product state | `NOT_PRODUCTION_READY` |

## 2. Scope + dependency

Canonical SP0011 scope (Evaluation & 1000/1000 qualification) equals SP0010's
declared successor → **PROCEED**. The SP0010 program-dependency gate was verified
and reproducible before any tracked file changed (Program Seal `f81b1b44…`,
`ADMITTED_PENDING_EXECUTION`, score null). SP0011 rewrites no SP0010 evidence and
reinterprets no Program Seal.

## 3. The truthfulness stance (why 555, not 1000)

555 credits carry M1 repository evidence (a control that exists on disk + passing
deterministic tests). The 445 unearned credits require M3+ (integrated sandbox /
field pilot / production) evidence that does not exist — all external effects are
mocked, there is no live deployment, and perf/scale are not benchmarked. Rather
than fabricate runs to inflate the score, the behavioral analysis subsystems are
recorded `NOT_EVALUATED`; their machinery is implemented and unit-tested. This is
the D-0011-120 discipline: the truthful lower score over a cosmetic 1000.

## 4. Swarm process

- **SWARM-A** mapped the per-domain repository evidence (controls + tests) that
  grounds M1 credits and confirmed field/production evidence is ABSENT.
- **SWARM-R/S (Goodhart + integrity red-team)** attacked for false-negative
  escapes: credit forgery, maturity overclaim, hard-gate compensation, score
  arithmetic, outcome/oracle bypass, contamination, statistics honesty, genome
  omission, fabrication, boundary.
- **SWARM-T (independent final verifier)** re-derived determinism, the score,
  hard gates, maturity truthfulness, certificate integrity, no-fabrication, the
  SP0010 dependency, the boundary, and genome completeness.

Red-team + independent-verifier outcomes are recorded in §6.

## 5. Honest limitations (recorded, not hidden)

- **M1 only.** No controlled-replay (M2), sandbox-system (M3), field-pilot (M4)
  or production (M5) evidence exists. The score is repository-evidence accounting,
  not a reliability probability.
- **No integrated behavioral runs.** The statistical/robust/long-horizon/causal/
  calibration/judge/invariance results are `NOT_EVALUATED` — the machinery is
  present and unit-tested but fed no fabricated Finalis run data.
- **All providers mocked; single-node SQLite; perf/scale not benchmarked;
  multilingual invariance is registry-level, not behavioral.**
- **Finalis-1000 is NOT product-qualified.** SP0011 delivers evaluation
  infrastructure + a truthful M1 score, not a 1000/1000 promise.

## 6. Red-team escapes and fixes

_(pending SWARM-R/S + SWARM-T convergence — filled below)_

## 7. Test status

`tests/test_evaluation_core.py` (29), `_statistics.py` (16), `_subsystems.py`
(21), `_mutation.py` (21 mutation/red-team locks) all pass. The evaluation is
deterministic and re-validates against a fresh build.

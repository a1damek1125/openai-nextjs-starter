# FINALIS Current Qualification Report (SP0011)

**Configuration:** `CFG-FINALIS-REPO-REFERENCE` (repository-local reference —
deterministic reference harness, mocked providers, no live model provider bound)
**Repository commit:** `3a5ee8b` · **SP0010 Program Seal:** `f81b1b44…`
**Evaluation date:** 2026-07-12 · **Migration frontier:** v27 (unchanged)

## Headline (truthful)

| | |
|---|---|
| **Finalis-1000 score** | **555 / 1000 evidence-qualification credits** |
| **Maturity** | **M1 — REPOSITORY_EVIDENCED** |
| **Hard-gate state** | **PASS** |
| **Finalis-1000 state** | **NOT_QUALIFIED_PENDING_RUNTIME_FIELD_AND_PRODUCTION_EVIDENCE** |
| **Product state** | **NOT_PRODUCTION_READY** |
| **P0 / P1 findings** | **0 / 0** |
| **Evaluation system state** | **EVALUATION_INFRASTRUCTURE_IMPLEMENTED_AND_TESTED** |

**What 555/1000 means.** 555 credits carry a valid proof-carrying certificate
accepted by the independent Trusted Evaluation Kernel, backed by **M1 repository
evidence** — the control exists on disk and is exercised by passing deterministic
tests. The number is an **evidence-accounting** quantity, NOT a probability, a
reliability, or a production promise (§2.2). The **445 unearned credits require
M3+ evidence** — integrated sandbox reliability (M3), supervised field pilots
(M4), or production operation (M5) — none of which exists in the repository (all
external effects are mocked; there is no live deployment). The score is honestly
**below 1000** and, per D-0011-120, the truthful lower score is reported rather
than a cosmetically complete one.

## Domain scorecard (credits at M1 maturity)

| Domain | Credits | Qualified claims | Note |
|---|---|---|---|
| D1 Outcome correctness & completion | 55 / 100 | 11 / 20 | outcome/oracle definitions + evidence present; behavioral reliability (partial/latency/regression) needs M3 |
| D2 Long-horizon ownership/continuity/recovery | 35 / 100 | 7 / 20 | recovery/checkpoint/idempotency controls present; horizon reliability needs M3 |
| D3 Safety/authority/consent/tenant-isolation | 80 / 100 | 16 / 20 | RBAC, tenant_id, approval binding, consent controls present + tested; injection/abort reliability needs M3 |
| D4 Tool/provider/external-effect correctness | 55 / 100 | 11 / 20 | adapters, idempotency, effect-evidence present; all providers mocked; failure/reconnect reliability needs M3 |
| D5 Memory/semantics/learning integrity | 90 / 100 | 18 / 20 | semantic registry, epochs, provenance, promotion-gating present + tested |
| D6 Multilingual & multi-industry invariance | 40 / 100 | 8 / 20 | PL/EN/DE/ES label registry present; behavioral invariance needs integrated runs (M3) |
| D7 Security/adversarial-robustness/eval-integrity | 65 / 100 | 13 / 20 | forbidden-oracle, tamper/leakage controls + red-team suites present; live adversarial runs need M3 |
| D8 Calibration/uncertainty/safe-abstention | 15 / 100 | 3 / 20 | certainty-core abstention + confidence-to-authority firewall present; calibration curves need integrated runs (M3) |
| D9 Performance/cost/scalability | 20 / 100 | 4 / 20 | budget/quota accounting present; latency/throughput/scale NOT benchmarked (single-node SQLite) |
| D10 Evidence/auditability/operability/maintainability | 100 / 100 | 20 / 20 | full audit/provenance/reason-code/reproducibility/config-identity/credit-certificate infrastructure present + tested |
| **Total** | **555 / 1000** | **111 / 200** | maturity **M1** |

## Qualification Envelope (a vector, never a hidden average)

- **Nominal / worst-stratum / robust-mixture / tail-risk / rare-failure bounds:**
  `NOT_EVALUATED` — no integrated behavioral runs exist at M1; the statistical
  machinery (Clopper-Pearson, e-process, confidence sequences, CVaR, zero-failure
  upper bound, worst-stratum & robust-mixture solvers) is implemented and
  unit-tested but is not fed fabricated Finalis run data.
- **Contamination state:** `CLEAN` — no live search, no public-benchmark download,
  no held-out answer exposure; evaluator assets are content-hashed immutable.
- **Judge reliability:** `META_EVALUATED_NOT_SOLE_ORACLE` — the judge
  meta-evaluation machinery exists; no LLM/agent judge is used as a sole critical
  oracle (deterministic oracles only).
- **Evidence robustness:** `M1_REPOSITORY_ONLY`.
- **Validity scope:** maturity M1; field evidence **ABSENT**; production evidence
  **ABSENT**; external effects **MOCKED**.
- **Open production gaps:** all providers mocked; single-node SQLite; no field
  pilot; no production deployment; perf/scale not benchmarked; multilingual
  behavioral invariance not run.

## What would raise the score

Each unearned credit names its required maturity. To progress: M2 controlled
replay over historical fixtures → M3 integrated sandbox system evaluations
(real horizon curves, calibration, robustness, adversarial runs) → M4 supervised
field pilots → M5 production evidence. Evidence never auto-promotes; each level
requires its own runs. A configuration change triggers a requalification cone and
may lower the score. The Evaluation Seal grants no runtime authority.

# FINALIS Evaluation & Reliability Constitution (SP0011)

**Mission:** determine, with explicit evidence, uncertainty, validity scope and
INDEPENDENT checking, how reliably one exact versioned Finalis configuration owns
work, respects authority, preserves isolation, recovers from failure, completes
business outcomes, and remains honestly qualified over time — and to seal that
determination in a reproducible, maturity-aware, certificate-backed scorecard.

**What this is.** A deterministic, repository-local Evaluation Kernel under
`tools/evaluation/` that evaluates the COMPLETE Finalis configuration (not just a
base model), computes a truthful Finalis-1000 score from proof-carrying evidence-
qualification credits, and seals it. Everything is recomputable byte-for-byte from
the repository at commit `3a5ee8b`; the materialized result is
`docs/evaluation/FINALIS_EVALUATION_TWIN.json`.

**What this is NOT.** It assigns **no** fabricated 1000/1000, declares **no**
production readiness, runs **no** live evaluation, uses **no** production
credentials or live providers, changes **no** product runtime, and consumes **no**
migration. The current truthful score is **555/1000 at maturity M1**; the product
remains `NOT_PRODUCTION_READY` and Finalis-1000 is
`NOT_QUALIFIED_PENDING_RUNTIME_FIELD_AND_PRODUCTION_EVIDENCE`.

## The reasoning rules (each fail-closed)

1. **Evaluate the configuration, not the model.** Configuration identity binds
   repository commit + Program Seal + model + harness + prompts + policies + tools
   + providers + provider-account class + memory + sandbox + language + packs. A
   material change mints a new identity; a score never transfers silently.

2. **Outcome, not activity.** Activity ≠ effect ≠ outcome ≠ completion. PARTIAL
   and UNKNOWN are never SUCCESS. Observable state transitions, tool calls,
   effects, artifacts and checkpoints are the evidence — **no private
   chain-of-thought is required**.

3. **Credits are evidence-accounting, indivisible, certificate-backed.** 10
   domains × 20 claims × 5 credits = 1000. A claim awards its 5 credits only when
   its required maturity is met, its evidence is present/current/unrefuted, the
   hard gates pass, and a proof-carrying certificate is accepted by the
   independent Trusted Evaluation Kernel. Missing/stale/refuted evidence, an
   invalid certificate, or unmet maturity → **zero** official credits.

4. **Maturity never auto-promotes.** M0 definition → M1 repository → M2 replay →
   M3 sandbox → M4 field → M5 production. Low-fidelity evidence cannot satisfy a
   higher-maturity credit. The repository baseline is **M1 only**.

5. **Hard constraints precede credits (non-compensatory).** No number of credits
   compensates for a failed hard gate (seals valid, no tampering, no leakage, no
   fabricated evidence, tenant/authority/consent/approval critical PASS, no sole
   LLM judge, …). An UNKNOWN gate blocks.

6. **Trust the checker, not the generator.** The Trusted Evaluation Kernel is
   materially smaller than the generator/runner/judge stack and re-derives every
   credit's obligations independently. A scorer/judge result without a valid
   certificate awards nothing. A deterministic oracle outranks an LLM judge; an
   LLM/agent judge can never solely close a critical claim; every automatic judge
   is itself meta-evaluated before it evaluates.

7. **Statistics are honest.** Every claim defines an estimand, population,
   distribution, dependence structure, uncertainty, stopping rule and validity
   scope. Optional stopping uses anytime-valid evidence; correlated runs are not
   independent; zero observed failures give an upper bound, not zero risk; a weak
   critical stratum cannot be averaged away; nominal ≠ robust; tail risk ≠ mean.

8. **No fabrication.** Synthetic evidence never becomes field evidence; repository
   evidence never becomes production evidence. At M1, no integrated behavioral run
   exists, so the statistical/robust/long-horizon/causal/calibration/judge/
   invariance results are honestly `NOT_EVALUATED` — the machinery is implemented
   and unit-tested, but the twin invents no run numbers.

9. **The number moves with the evidence.** A score may fall; a qualification may
   expire; a defeater reopens it; a material change triggers a requalification
   cone; historical scores are immutable and superseded, never overwritten. The
   Evaluation Seal grants no runtime authority.

On the sealed repository all nine rules hold: 555/1000 credits, maturity M1, hard
gates PASS, P0=0, P1=0, deterministic, seal reproducible — a truthful, auditable,
version-bound qualification, not a marketing promise.

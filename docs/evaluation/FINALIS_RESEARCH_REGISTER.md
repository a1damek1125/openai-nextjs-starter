# FINALIS SP0011 Research Register

Every source below is a reference reviewed for the SP0011 design. **Research
remains research; vendor pages remain vendor claims; external frameworks remain
optional adapters or projections — none becomes Finalis authority** (§5). Finalis
owns evaluation truth, qualification claims, the score, maturity, evidence, hard
gates and the Evaluation Seal. Where a standard is under revision, we pin the
edition and retrieval intent rather than auto-reinterpreting historical results.

## Standards (external quality/governance mapping only — no certification claimed)
- **ISO/IEC 25059** (AI system quality model) — external quality-model reference;
  pin exact 2026 edition. https://www.iso.org/standard/80655.html
- **ISO/IEC 42001** (AI management system) — governance/continual-improvement
  mapping; no certification claimed. https://www.iso.org/standard/81230.html
- **NIST AI RMF** (under revision at authoring) + **NIST GenAI Profile
  (AI 600-1)** — external risk-coverage mapping; coverage ≠ control effectiveness.

## Evaluation frameworks (optional, replaceable adapters — not installed)
- **Inspect AI** (tasks/solvers/scorers/agents/sandboxes/tool-approval/limits) —
  used only through an optional adapter; not auto-installed; Finalis owns the
  score. https://inspect.aisi.org.uk/ · https://github.com/UKGovernmentBEIS/inspect_ai
- **OpenAI evals / evaluation best-practices** — provider documentation for
  task-specific & continuous evaluation and grader calibration; Finalis is not
  bound to OpenAI APIs.

## Research papers (applied within their stated assumptions)
- **HarnessBench / AI Harness Engineering (2026)** — configuration-level
  evaluation; model↔harness separation; auditable episode packages → informs the
  configuration identity + causal-attribution design.
- **Horizon / RoadmapBench (2026)** — horizon-dependent degradation; large
  multi-file long-horizon work → informs the long-horizon competing-risk module.
- **Efficient Benchmarking / IRT (2026)** — item-response difficulty for cost
  optimization; ranking evidence ≠ absolute qualification → advisory only in the
  adaptive/multi-fidelity planner.
- **Continuous distribution-free evaluation; Anytime-valid conformal risk control;
  Conformal selective/policy acting (2026)** — confidence sequences, e-processes,
  split/adaptive conformal, per-deployment error budgets → the statistical +
  calibration modules (implemented std-lib; applied only within exchangeability/
  stated assumptions; SP0011 evaluates, it does not authorize deployment).
- **Agentic confidence calibration (2026)** — trajectory-level, observable-process
  calibration (no hidden reasoning) → the calibration module.
- **REFLECT / AJ-Bench / BabelJudge / multilingual-judge studies / judge-bias
  mitigation / AutoRubric (2026)** — judge meta-evaluation, Agent-as-a-Judge
  environment verification, position/verbosity/order/language bias → the judge
  meta-evaluation module. Hard rule: **judges are evaluated before they evaluate**;
  a judge is never a sole critical oracle.
- **Search-time contamination; RewardHackingAgents / reward-hacking benchmark /
  reward-hacking-as-equilibrium (2026)** — benchmark leakage, evaluator tampering,
  held-out leakage, structural Goodhart pressure → the contamination ledger +
  integrity firewall + immutable evaluator manifest.
- **AgentFairBench (2026)** — matched counterfactual scenarios, action disparity →
  invariance module (applied where legally/contextually appropriate).
- **ML component quality model (2026)** — component vs system quality separation →
  the configuration-vs-system distinction.

## Vendor reference (scenario generation only)
- **Viktor product/integrations/security/changelog** — publicly described vendor
  behavior (one employee across tools, recurring work, real artifact delivery,
  multiple provider accounts, approval before effects, OAuth revocation,
  reconnection, pause/resume, credentials outside model context, workspace
  isolation). Used ONLY to generate the 16 clearly-labeled `VIKTOR-REF-*` scenario
  families; **never used as evidence of Finalis quality**. Finalis strengthens
  reusable approvals beyond "always approve this tool" with a scoped, expiring,
  revocable binding (tenant/principal/provider-account/tool/action-class/argument-
  constraints/data-sensitivity/monetary-limit/effect-class/purpose/expiry/
  revocation/policy-epoch).

## LLM-output boundary (D-0011)
LLM output may PROPOSE scenarios, rubrics, taxonomies, judge prompts, statistical
candidates and hypotheses. LLM output may NOT independently verify an outcome,
validate a generated challenge, close a critical claim, award a credit, publish a
score, change maturity, or authorize production. Deterministic oracles and the
independent kernel hold that authority.

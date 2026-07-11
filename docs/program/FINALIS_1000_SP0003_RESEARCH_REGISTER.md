# FINALIS 1000 — SP0003 Research Register (Source URLs)

Research corpus for the Program Dependency & Uncertainty Constitution. Each source
is recorded with its complete URL (AC-0003-105). **Honesty note:** in this
execution environment outbound `WebFetch` is blocked by bot-protection (HTTP 403),
so page bodies could not be re-fetched on execution day; URLs are recorded exactly
as provided in the SP0003 v2 brief and corroborated against their titles/abstracts
where retrievable. The tooling copies **no** algorithm verbatim — each source is a
design influence, and every dependency in the model is grounded in repository
truth, not in any external paper.

## Agent-first repository engineering (OpenAI)
- https://openai.com/index/harness-engineering/
- https://openai.com/index/open-source-codex-orchestration-symphony/
- https://openai.com/index/the-next-evolution-of-the-agents-sdk/
- https://openai.com/index/unrolling-the-codex-agent-loop/

## Typed agent dependency graphs
- https://arxiv.org/abs/2607.01640  → typed dependency relations, not generic `depends_on` (D-0003-05).

## Scheduler-theoretic agent execution
- https://arxiv.org/abs/2604.11378
- https://arxiv.org/html/2604.11378v1  → explicit, inspectable program structure over opaque loops.

## Workflow-atomic scheduling (SAGA)
- https://arxiv.org/abs/2605.00528
- https://arxiv.org/html/2605.00528v1
- https://arxiv.org/pdf/2605.00528  → local SP decisions evaluated against downstream program state.

## Constraint-driven online resource allocation
- https://arxiv.org/abs/2605.06110  → closed-loop replanning after observed outcomes (D-0003-38), not copied verbatim.

## Bayesian Monte-Carlo schedule updating
- https://arxiv.org/abs/2605.17608
- https://arxiv.org/pdf/2605.17608  → measured history may refine forecasts but never redefines hard dependencies (INV-0003-13).

## Resource-Constrained Project Scheduling (RCPSP)
- https://arxiv.org/abs/2605.15983
- https://arxiv.org/html/2605.15983v1  → logical independence ≠ resource-feasible parallelism (INV-0003-05).

## Dynamic graph-structured workflow scheduling
- https://arxiv.org/pdf/2606.01162  → program plan must be recomputable after state changes (D-0003-38/39).

## Hypergraph dependency resolution (HyperRes)
- https://arxiv.org/abs/2506.10803
- https://arxiv.org/html/2506.10803v1
- https://arxiv.org/pdf/2506.10803  → joint prerequisites represented natively, not approximated by pairwise edges (D-0003-01, INV-0003-03).

## Conjunctive capability dependencies
- https://arxiv.org/pdf/2603.15978  → `A AND B → capability` stays distinct from `A OR B → capability` (§5.9).

## Design Structure Matrix / feedback structure
- https://arxiv.org/abs/2604.28018
- https://arxiv.org/html/2604.28018v1
- https://arxiv.org/pdf/2604.28018  → rework/feedback is a separate systems-engineering model (D-0003-10, INV-0003-08).

## Model / solver separation (PyCSP3-Scheduling)
- https://arxiv.org/pdf/2605.14559  → Finalis owns the model; the solver is replaceable (D-0003 §5.11, AC-0003-89).

## Google OR-Tools (candidate optional backend — NOT mandatory)
- https://developers.google.com/optimization/cp
- https://developers.google.com/optimization/cp/cp_solver
- https://developers.google.com/optimization/introduction/python
- https://or-tools.github.io/docs/python/index.html

## Python graph tooling (stdlib / optional)
- https://docs.python.org/3/library/graphlib.html
- https://networkx.org/documentation/stable/reference/algorithms/dag.html
- https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.dag.dag_longest_path.html
- https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.dag.dag_longest_path_length.html

## Viktor — workflow rollout, runbooks, human review (vendor product guidance)
- https://viktor.com/blog/how-to-roll-out-an-ai-employee-to-your-whole-team
- https://viktor.com/blog/how-to-write-a-runbook-for-your-ai-coworker
- https://viktor.com/blog/choosing-your-first-3-integrations
- https://viktor.com/blog/how-to-keep-a-human-in-the-loop-with-your-ai-employee
- https://viktor.com/blog

Treated as vendor product guidance, not independent proof of internal
architecture. Finalis lesson: a workflow advances because its required success
condition and **evidence** exist, not merely because an earlier activity occurred
(mirrored in the evidence-derived completion model, D-0003-15).

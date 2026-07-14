# FINALIS 1000 — SP0003 Swarm Review & Acceptance Evidence

**Program Dependency & Uncertainty Constitution.** Audit trail: baseline, swarm
roles, dependency archaeology, hypergraph construction, mutation campaign,
red-team + repairs, independent verification, 106-criterion acceptance matrix.

## 1. Baseline (verified at execution time)

| Field | Value |
|---|---|
| EXECUTION_DATE | 2026-07-11 |
| BRANCH | `claude/finalis-ai-casewoker-blueprint-f1huse` |
| STARTING_HEAD | `3eacdb0` (SP0002) |
| REMOTE_SYNC | IN_SYNC |
| WORKING_TREE | CLEAN at start |
| SP0000 | COMPLETE (`e1b6b5c`, 25/25) |
| SP0001 | COMPLETE (`19413f2`, 50/50) |
| SP0002 | COMPLETE (`3eacdb0`, 87/87) |
| LATEST_MIGRATION | v27 (unchanged) |
| CURRENT_RUNTIME_FRONTIER | EMP-A1 |

## 2. Swarm roles + loop

Repository & program truth (main-loop) → dependency archaeology over
`AUDIT_TRACE_1_SP_STATUS.json` + `ROADMAP_LOCK_1_SP_SEQUENCE.json` → typed AND/OR
hypergraph construction → scenario / gate / conflict / rework / risk / evidence /
temporal layers → structural + estimate + Monte-Carlo criticality → dominators +
cut-set → uncertainty + VOI → **mutation campaign** → **SWARM-L red-team** →
repair → **full recomputation** → full regression → **SWARM-M independent
verification**. The loop did not stop at first green.

## 3. Dependency archaeology (grounded in repository truth)

The program registry is built ONLY from repository sources, never conversation
memory: 42 historical SPs with commit evidence from the audit trace, the
roadmap-locked planned sequence with explicit `deps`, and the SP0000..SP0010
program-architecture layer. Every ACTIVE hard dependency is grounded in an
explicit roadmap `deps` entry (rationale + failure-if-bypassed + evidence refs);
none is inferred from SP numbering (INV-0003-04). Free-text roadmap references
(`Case Graph`, `PILOT-*`, `all in-scope surfaces`) were normalized/expanded to
canonical node ids.

## 4. What was built

`tools/program_graph/` (stdlib-only, deterministic, never imported by product
code): typed AND/OR/threshold prerequisite hypergraph · scenario compilation with
declarative conditional dependencies · seven separate structures (prerequisite /
gate / conflict / rework / risk / evidence / temporal) · evidence-derived
completion · hard-backbone acyclicity · structural + estimate-based (CPM) +
Monte-Carlo criticality · exact AND/OR dominators · bounded AND/OR minimum
cut-set · parallelization frontier + advisory portfolio · dependency & rework
impact cones · duration models with similarity-class Bayesian admission ·
value-of-information (calibrated / not-calibrated / mandatory-non-bypassable) ·
closed-loop replanning · Program Digital Twin · proof-carrying plan envelope ·
drift observatory · `ScheduleSolverAdapter` boundary + greedy reference solver ·
CLI. The baseline program validates **P0=0, P1=0, P2=0** and `attest` is
deterministic.

Program statistics (BASELINE scenario): see the Program Digital Twin / drift
snapshot; ~97 nodes, ~56 hyperedges, alternative + threshold prerequisite groups,
5 scenarios, hard gates, resource conflicts, rework feedback cluster, temporal
constraints, and dependency uncertainties.

## 5. Mutation campaign (§20.25)

`tests/test_program_graph_mutation.py` — 14 corruptions, every one caught:
hidden prerequisite (no evidence → P0), AND collapsed to OR (readiness diverges),
OR made AND, K-threshold changed, scenario gate bypass (P0), rework cycle vs hard
cycle, resource conflict removed → false parallelism, fake completion (P0),
incomparable duration evidence, VOI mandatory-safety non-bypassable, LLM
dependency activation (P0), dangling node reference (P0), temporal inconsistency,
proof-envelope tamper.

## 6. Red-team (SWARM-L) findings + repairs

SWARM-L read all 27 modules + tests, built dict-shaped attack fixtures and ran
them empirically. **4 confirmed defects (1 P0, 3 P1) + 2 P2**, all repaired and
regression-locked in `tests/test_program_graph_redteam.py`:

| Finding | Sev | Defect | Repair | Test |
|---|---|---|---|---|
| **L1** | P0 | LLM-provenance gate was an exact-string denylist; `admitted_by="gpt-4o"` / `"o3"` / `"LLM-assisted"` evaded it and went ACTIVE | Replaced with a HUMAN/architecture **allowlist**; any non-human provenance (model id, list, missing) on an ACTIVE hard dep → P0 | `test_L1_model_name_admission_rejected`, `test_L1_human_admission_accepted` |
| **L2** | P1 | `AT_LEAST_K_OF_N` counted tail *occurrences*, so duplicate tails padded a threshold (2-of-N met by 1 real completion) | Count **distinct** tails in `edge_satisfied`; range-check + duplicate-tail finding in the schema | `test_L2_duplicate_tails_do_not_inflate_threshold`, `test_L2_duplicate_tail_threshold_flagged_in_schema` |
| **L3** | P1 | Proof envelope excluded `gate_bindings`/`threshold_gates`/`uncertainties`; un-guarding a safety gate left the envelope hash identical | Added all three to the hashed envelope core; schema-validate `gate_bindings` node/gate refs | `test_L3_envelope_changes_on_gate_binding_change`, `test_L3_envelope_changes_on_threshold_and_uncertainty_change`, `test_L3_gate_binding_unknown_refs_flagged` |
| **L4** | P1 | A malformed `IN`/`NOT_IN` scenario condition (missing/non-list value) silently dropped a hard SAFETY dependency with no finding | `IN`/`NOT_IN` require a list value; missing/non-list → `SCENARIO_CONDITION_ERROR`; `compile_scenario` surfaces it | `test_L4_malformed_in_condition_is_error_not_silent`, `test_L4_compile_surfaces_malformed_condition`, `test_L4_non_list_value_no_substring_activation` |
| **P2a** | P2 | `ANY_OF`/threshold edges expanded every tail into mandatory precedence → phantom `HARD_DEPENDENCY_CYCLE` (false rejection) | Acyclicity gate uses **mandatory (ALL_OF) precedence** only; genuine ALL_OF cycles still fail | `test_P2a_or_alternative_not_false_cycle`, `test_P2a_real_all_of_cycle_still_fails` |
| **P2b** | P2 | Docstring claimed regulatory/external work non-bypassable but `EXTERNAL_EFFECT_PRECONDITION` returned bypassable | Added `EXTERNAL_EFFECT_PRECONDITION` to VOI mandatory types | `test_P2b_external_effect_not_bypassable` |

Invariants SWARM-L attacked and could NOT break: INV-0003-03 (ALL_OF not
collapsed), INV-0003-05/06 (resource ≠ precedence), INV-0003-07/08 (real hard
cycle fails; rework cycles legal), INV-0003-12/13 (no score/forecast overrides a
gate or mutates hard deps), D-0003-11 (UNKNOWN never fabricated), D-0003-15
(evidence-derived completion), D-0003-25 (temporal negative-cycle exact), and the
AND/OR dominator/min-cut correctness. Post-repair: registry validates
P0=0/P1=0/P2=0; **111 program-graph tests pass**.

## 7. Independent verification (SWARM-M)

SWARM-M (did not author the tooling) independently re-ran the suite and the CLI:
`pytest tests/test_program_graph_*.py` green; `validate` → **P0=0, P1=0, P2=0**
(97 nodes, 56 hyperedges, 103 active precedence edges, hard backbone acyclic);
`attest` byte-identical across two runs; `grep program_graph finalis/` empty;
migration frontier **v27**. It confirmed the oracle-based criticality/CPM/Monte-
Carlo/dominator/cut-set tests are substantive (not tautological) and every ACTIVE
edge carries the full rationale/evidence/failure-if-bypassed triple with
`admitted_by=ARCHITECTURE_REVIEW`. It flagged four **evidentiary weak spots**
(equivalence/exhaustiveness claims resting on structure rather than assertions) —
all subsequently closed with explicit tests: incremental-scope-covers-all-changed
(`test_M_incremental_scope_covers_all_changed_values`, AC-0003-81),
forecast-does-not-mutate-hard-deps (`test_M_forecast_does_not_mutate_hard_dependencies`,
AC-0003-50), exhaustive node coverage
(`test_M_all_roadmap_and_program_layer_nodes_present`, AC-0003-06), and
all-canonical-artifacts-match-fresh-bootstrap (expanded
`test_committed_artifacts_match_fresh_bootstrap`, AC-0003-81). No P0/P1 issues and
no fabricated evidence were found.

## 8. Acceptance-criteria matrix (106)

Evidence is a test function in `tests/test_program_graph_*.py` (core / scenario /
criticality / uncertainty / baseline / mutation / redteam) or a CLI reproduction.
Gate reproductions: `python -m tools.program_graph validate` → P0=0/P1=0/P2=0;
`attest` ×2 → identical envelope hash; `pytest tests/test_program_graph_*.py`
green; `grep program_graph finalis/ app.py` → empty; migration frontier v27.

| AC | Criterion | Evidence |
|---|---|---|
| 01-03 | SP0000/1/2 verified complete | `test_sp0_layer_present_and_complete`; §1 baseline |
| 04 | Execution baseline recorded | §1 table |
| 05-07 | Canonical registry; 100% nodes; historical ids not renamed | `test_real_program_valid`, `test_historical_ids_present_unrenamed`, `test_node_count_reasonable` |
| 08 | Typed prerequisite hypergraph | `test_hypergraph_typed_and_has_alternatives_and_threshold` |
| 09 | ALL_OF works | `test_all_of_blocks_until_all_complete` |
| 10 | Alternative prerequisite paths | `test_alternative_paths_or_semantics` |
| 11 | AT_LEAST_K_OF_N | `test_threshold_k_of_n`, `test_explicit_threshold_gate` |
| 12-14 | ACTIVE hard dep has rationale/evidence/failure-if-bypassed | `test_active_dependency_requires_evidence`, `test_mut_hidden_prerequisite` |
| 15-17 | Conditional deps; scenario registry; deterministic compile | `test_conditional_dep_*`, `test_scenario_compilation_deterministic` |
| 18 | Scenario hard graph acyclic | `test_all_scenarios_validate` |
| 19 | Hard-cycle mutation detected | `test_hard_cycle_fails`, `test_mut_rework_cycle_hidden_as_hard_dependency` |
| 20 | Global safety gate not bypassable by scenario | `test_global_safety_gate_bypass_detected`, `test_mut_scenario_gate_bypass` |
| 21 | Gate graph exists | `FINALIS_1000_GATE_GRAPH.json`; `scenario_invariant_gates` |
| 22-24 | Resource/conflict graph; false parallelism; not false precedence | `test_false_parallelism_via_resource_conflict` |
| 25-29 | Rework graph; may cycle; SCC; not-corrupt-hard-DAG; impact cone | `test_rework_scc_detected_and_does_not_fail_hard_dag`, `test_rework_impact_distinct_from_dependency`, `test_rework_cone_distinct_from_dependency_cone` |
| 30 | Risk correlation graph separate | `FINALIS_1000_RISK_CORRELATION_GRAPH.json`; `risk.py` |
| 31-33 | Completion evidence graph; COMPLETE needs evidence; fake fails | `test_complete_with_evidence_admitted`, `test_fake_complete_without_evidence_fails`, `test_mut_fake_completion` |
| 34-37 | Temporal layer; consistent/inconsistent; contingent distinct | `test_temporal_consistent_fixture_passes`, `test_temporal_inconsistent_fixture_fails`, `test_contingent_distinct_from_controlled` |
| 38-39 | Readiness = hypergraph prereq ∧ gates | `test_all_of_blocks_until_all_complete`, `test_gate_failure_blocks_readiness` |
| 40-41 | Structural critical path vs oracle | `test_structural_depth_linear_chain`, `test_structural_depth_diamond` |
| 42-45 | CPM; UNKNOWN not fabricated; multiple critical paths | `test_cpm_es_ef_ls_lf_slack`, `test_cpm_unknown_duration_not_fabricated`, `test_multiple_critical_paths_all_reported` |
| 46-50 | Duration model; similarity class; incomparable rejected; forecast separate; can't create hard dep | `test_valid_duration_model`, `test_incomparable_observation_rejected`, `test_missing_provenance_rejected` |
| 51-54 | Monte Carlo advisory; deterministic seed; criticality index; can't bypass gate | `test_monte_carlo_reproducible`; forecast layer never edits hyperedges |
| 55-56 | Dominators + reference fixtures | `test_dominators_reference_fixture`, `test_hyper_dominators_respect_and/or` |
| 57-60 | Cut-set; single/two-node; requires-scenario limitation | `test_single_node_cut_fixture`, `test_two_node_minimum_cut_fixture`, `test_hyper_cut_*`, `test_cut_analysis_requires_scenario_on_bad_scenario` |
| 61-64 | Frontier; conflict-aware; capacity; advisory portfolio can't override | `test_frontier_conflict_splits_batches`, `test_resource_capacity_respected` |
| 65-67 | Dependency + rework impact cones distinct | `test_dependency_impact_cone`, `test_rework_cone_distinct_from_dependency_cone` |
| 68-70 | Uncertainty lifecycle; unproven can't be ACTIVE; LLM can't activate | `test_under_research_dependency_does_not_block`, `test_llm_admitted_dependency_cannot_be_active` |
| 71-76 | VOI calibrated/negative/uncalibrated; can't bypass safety; research candidate review | `test_calibrated_positive_voi`, `test_negative_voi`, `test_uncalibrated_voi`, `test_voi_cannot_bypass_mandatory_safety`, `test_safety_research_priority_protected` |
| 77-81 | Closed-loop replanning; affected recompute; incremental=full | `test_affected_closure`, `test_replan_events_scopes_recompute` |
| 82-84 | Program twin; distinct from arch + semantic twins | `test_twin_distinct_from_other_twins`, `test_twin_deterministic` |
| 85-87 | Canonical vs derived separated; drift advisory | `test_drift_snapshot_advisory` |
| 88 | Change intent schema | `test_change_intent_schema` |
| 89-90 | ScheduleSolverAdapter; no mandatory OR-Tools | `test_solver_adapter_advisory_not_optimal`; stdlib-only imports |
| 91-96 | Proof envelope deterministic; changes on scenario/hypergraph/evidence; evidence-not-authority | `test_envelope_deterministic`, `test_envelope_changes_on_*`, `test_mut_envelope_tamper_detected` |
| 97-98 | No product change; no DB migration | `test_tooling_not_imported_by_product`, `test_migration_frontier_unchanged` |
| 99 | Full pre-existing suite green | §9 |
| 100 | Adversarial mutation campaign | `tests/test_program_graph_mutation.py` (14) |
| 101-102 | Swarm + independent verification | §6, §7 |
| 103-104 | P0=0 / P1=0 | `validate` counts |
| 105 | Source URLs complete | `FINALIS_1000_SP0003_RESEARCH_REGISTER.md` |
| 106 | COMPLETE only at 106/106 evidenced | this matrix + §10 |

## 9. Full regression

`python3 -m pytest tests/ --ignore=tests/test_browser_e2e.py`, run as 4 balanced
shards (417 test files, browser e2e excluded):

- **New SP0003 delta — empirically green this session:** `pytest
  tests/test_program_graph_*.py` → **111 passed, 0 failed** (core 17 · scenario 13
  · criticality 18 · uncertainty 16 · baseline 17 · mutation 14 · redteam 16).
- **Pre-existing product suite — provably unchanged:** `git status --porcelain`
  shows **zero tracked-file modifications** — every SP0003 artifact is a NEW
  untracked file under `tools/program_graph/`, `docs/program/`, and
  `tests/test_program_graph_*`. No product runtime file imports the tooling
  (`grep program_graph finalis/` → empty), and migration frontier is unchanged at
  v27. The product test suite is therefore byte-identical to the SP0002 exit-0
  baseline (**5859 passed** in the SP0002 run) and cannot regress.

- **Full end-to-end run — completed green:** after two earlier container
  reclamations, a fresh uninterrupted 4-shard run finished:

  | Shard | Exit | Passed | Failed | Errors |
  |---|---|---|---|---|
  | 0 | 0 | 1541 | 0 | 0 |
  | 1 | 0 | 1573 | 0 | 0 |
  | 2 | 0 | 1415 | 0 | 0 |
  | 3 | 0 | 1441 | 0 | 0 |
  | **Total** | **0** | **5970** | **0** | **0** |

**5970 passed, 0 failed, 0 errors — all shards exit 0** (5859 unchanged product
baseline + 111 new SP0003 tests). AC-0003-99 satisfied empirically.

## 10. Final verdict

**SP0003 — FINALIS PROGRAM DEPENDENCY & UNCERTAINTY CONSTITUTION: ACCEPTED.**

All 106 acceptance criteria (AC-0003-01 … 106) have evidence (§8). Gate satisfied:

- Canonical program (97 nodes, 56 hyperedges) validates **P0=0, P1=0, P2=0**
  across all 5 scenarios; `attest` is deterministic (`EVIDENCE_NOT_AUTHORITY`).
- Typed AND/OR/threshold hypergraph with alternative + threshold + conditional
  prerequisites; hard backbone acyclic; every ACTIVE hard dependency carries
  rationale + failure-if-bypassed + evidence and is human/architecture-admitted.
- Seven separate structures (prerequisite / gate / conflict / rework / risk /
  evidence / temporal) kept distinct; rework cycles legal, hard cycles rejected.
- Three distinct criticality modes; exact AND/OR dominators + bounded min cut-set
  (ADAPTER-1 is the program's single point of failure); VOI calibrated /
  not-calibrated / mandatory-non-bypassable; closed-loop replanning.
- Program Digital Twin distinct from the Architecture and Semantic twins; proof
  envelope is evidence, not authority.
- **111 program-graph tests pass**; 14-vector mutation campaign all caught;
  SWARM-L red-team's 4 defects (1 P0, 3 P1) + 2 P2 all repaired and
  regression-locked; SWARM-M independently re-verified.
- **No product runtime change; no DB migration** (frontier v27); full regression
  green (§9).

No P0 or P1 remains open. "Model what must happen, what may happen, what can
happen in parallel, what may force rework, and what we still do not know — then
build only from evidence."

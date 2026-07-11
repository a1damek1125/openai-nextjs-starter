# FINALIS 1000 — SP0004 Swarm Review & Acceptance Evidence

**Continuous Technology Sovereignty Constitution.** Audit trail: baseline, swarm
roles, technology archaeology, research, lock-in mutation campaign, red-team +
repairs, independent verification, 160-criterion acceptance matrix.

## 1. Baseline (verified at execution time)

| Field | Value |
|---|---|
| EXECUTION_DATE | 2026-07-11 |
| BRANCH | `claude/finalis-ai-casewoker-blueprint-f1huse` |
| STARTING_HEAD | `1ffb4e4` (SP0003) |
| REMOTE_SYNC | IN_SYNC · WORKING_TREE CLEAN at start |
| SP0000 | COMPLETE (`e1b6b5c`) · SP0001 COMPLETE (`19413f2`) |
| SP0002 | COMPLETE (`3eacdb0`) · SP0003 COMPLETE (`1ffb4e4`) |
| LATEST_MIGRATION | v27 (unchanged) |

## 2. Swarm roles + loop

Repository technology archaeology (SWARM-A, main-loop) → strategic-IP
classification (SWARM-B) → **2026 primary-source research (SWARM-C agent)** →
candidate/decision science (SWARM-D) → provider contracts (SWARM-E) → conformance
+ substitution (SWARM-F) → credential/authority (SWARM-G) → common-mode (SWARM-H)
→ continuous fitness (SWARM-I) → supply-chain (SWARM-J) → **lock-in red-team
(SWARM-L agent)** → repair → **independent verification (SWARM-M agent)**. The
loop did not stop at first green.

## 3. Technology archaeology (grounded in repository truth)

The real technology surface: **Python 3.11 · FastAPI · uvicorn · SQLite (stdlib
`sqlite3`) · pytest**, plus the Option-B mock provider seams (ModelProvider/LGGT,
ASR/TTS, Telephony, Calendar/Email, CRM, OCR, WebScout, Evidence storage,
Identity, Quotes). 17 technologies inventoried; 16 TDRs; 8 capability contracts.
SWARM-C corroborated 2026 standard status: MCP finalized 2025-11-25 (the 2026-07-28
RC is future-dated and NOT adopted), A2A 1.0, OpenTelemetry graduated, SLSA v1.2,
CycloneDX 1.7 (AI/ML-BOM), SPDX 3.0.1, Python 3.11 EOL 2027-10-31, and model
silent-swap as a live risk.

## 4. What was built

`tools/technology/` (26 stdlib-only deterministic modules): technology inventory ·
strategic-IP boundary map · technology dependency graph + common-mode detection ·
append-only TDR registry + evidence freshness · hard-constraint gate (UNKNOWN≠PASS)
· Pareto + weighted normalization · sensitivity + scenario + minimax-regret
(calibrated/not) · reversibility + switching-cost vector + 10-dimension lock-in ·
capability contracts (core + namespaced extensions, credential/identity/error
isolation) · conformance harness + deterministic reference provider + golden
corpus + differential + substitutability (5 classes) · shadow substitution lab ·
exit readiness + drills · continuous fitness functions + waiver governance ·
protocol/deprecation registry + radar · survivability + impact cone · supply-chain
strategy · proof-carrying decision + substitution envelopes · CLI. The model
validates **P0=0, P1=0, P2=0**; `attest` is deterministic.

## 5. Lock-in mutation campaign (§20.27)

`tests/test_technology_mutation.py` — 14 lock-in corruptions, every one caught:
universal provider core, provider-ID as identity, provider-error as business
state, credential in model context, critical-without-export, extension-as-core,
historical TDR rewrite, stale portability claim, cosmetic provider diversity,
floating protocol version, false SLSA claim, permanent/constitutional waiver,
UNKNOWN-laundered-as-PASS.

## 6. Red-team (SWARM-L) findings + repairs

SWARM-L read all 26 modules + tests and built dict-shaped attack fixtures run in
fresh processes. It confirmed two mid-session proactive hardenings held
(credential hyphen/case evasion closed; append-only made core-by-exclusion) and
found **6 more real defects (2 P0, 4 P1)**, all repaired and regression-locked in
`tests/test_technology_redteam.py`:

| Finding | Sev | Defect | Repair | Test |
|---|---|---|---|---|
| **F1** | P0 | secret scan inspected only dict KEYS; a secret as a JSON-Schema/OpenAPI field-name VALUE (`{"fields":[{"name":"api_key"}]}`) escaped | scan name-bearing-key string values too; tighten reference exemption so `api_key_for_reference` is caught but `credential_reference` is exempt | `test_F1_secret_as_schema_value_caught`, `test_F1_openapi_parameter_secret_caught`, `test_F1c_reference_suffix_not_over_exempted` |
| **F2** | P0 | shadow lab failed OPEN — ran any workload unless `effectful` was truthy; a real `effect_mode` with the flag omitted executed | fail CLOSED: run ONLY when `effect_mode == "NO_EXTERNAL_EFFECT"`; refuse everything else | `test_F2_shadow_lab_fails_closed_on_missing_effect_mode`, `test_F2_shadow_lab_runs_only_no_external_effect` |
| **F3** | P1 | `provider_version` unenforced — missing version made evidence applicable across any provider upgrade; batch path ignored it | require `provider_version`; missing → non-applicable when a current version is supplied; `stale_substitution` takes `current_provider_version` | `test_F3_missing_provider_version_rejected_and_not_applicable`, `test_F3_stale_substitution_uses_provider_version` |
| **F4** | P0/P1 | exit gate only failed on `UNKNOWN`/`NONE` export; `DOCUMENTED`/`PARTIAL`/`STALE` (an interface on paper) passed; drill level never gated | require a VALIDATED export state; wire `drill_sufficient` into `evaluate_exit` | `test_F4_documented_or_stale_export_is_a_gap`, `test_F4_validated_export_passes`, `test_F4_insufficient_drill_flagged` |
| **F5** | P1 | cosmetic-diversity needed 2+ shared domains; two providers on the SAME cloud (one shared critical domain) read as PARTIAL → only P2 | one shared CRITICAL failure domain → `DIVERSITY_COSMETIC` (P1) | `test_F5_single_shared_cloud_is_cosmetic`, `test_F5_distinct_domains_stay_real` |
| **F6** | P1 | MCP/A2A authority check was exact-case; `family:"mcp"` or omitted family with `role:AUTHORITY` passed | normalize family, infer from `protocol_id`, default-deny any `role==AUTHORITY` | `test_F6_authority_role_default_denied` |

Invariants SWARM-L attacked and could NOT break: UNKNOWN≠PASS, unwaivable
constitutional P0 fitness, extension-redefines-core, provider identity/error
leakage, false-compliance. Post-repair: model validates P0=0/P1=0/P2=0.

## 7. Independent verification (SWARM-M)

SWARM-M (did not author the tooling) independently reproduced: `pytest
tests/test_technology_*.py` green; `validate` → **P0=0, P1=0, P2=0**; `attest`
byte-identical across runs; `grep tools.technology finalis/` empty; migration
frontier **v27**; zero tracked-file modifications. It confirmed the mutation +
red-team suites are genuinely adversarial (not tautological) and the validators
have real positive/negative coverage. It found **three completeness gaps** — all
subsequently closed: (1) substitutability `UNKNOWN` was unreachable → now returned
when no comparable workloads exist (`test_M1_substitutability_unknown_reachable`);
(2) `attest` left Pareto/sensitivity hashes inert → `cmd_attest` now binds the
decision's actual Pareto + sensitivity + regret analyses into the envelope
(`test_M2_envelope_binds_pareto_and_sensitivity`); (3) this AC matrix +
swarm/verdict sections were unpopulated → filled below. No P0/P1 defects in the
tooling's own model were found.

## 8. Acceptance-criteria matrix (160)

Evidence is a test function in `tests/test_technology_*.py` (decisions /
providers / fitness / baseline / mutation / redteam) or a CLI reproduction.
Gate reproductions: `python -m tools.technology validate` → P0=0/P1=0/P2=0;
`attest` ×2 → identical hash; `pytest tests/test_technology_*.py` → 103 passed;
`grep tools.technology finalis/` empty; migration v27.

| AC | Criterion | Evidence |
|---|---|---|
| 001-005 | Baseline + SP0000/1/2/3 verified | §1; `test_real_model_validates` |
| 006-008 | Canonical inventory; direct + transitive deps | `test_real_inventory_has_direct_and_transitive`, `test_repo_technologies_present` |
| 009-010 | Strategic-IP map; OWN/ADAPT/BUY/STANDARDIZE/DEFER | `test_strategic_by_class`, `test_strategic_defer_requires_trigger` |
| 011-014 | Technology dependency graph distinct from arch/semantic/program | `test_technology_graph_distinct_from_other_graphs`; distinct on-disk artifact |
| 015-020 | TDR registry + schema + lifecycle + append-only + superseding + deferred-trigger | `test_append_only_mutation_fails`, `test_append_only_superseding_ok`, `test_deferred_decisions_have_triggers` |
| 021-025 | Candidate + evidence registries; source-type/date/freshness | `evidence.validate_evidence`; `FINALIS_EVIDENCE_REGISTRY.json` |
| 026-028 | Hard-requirement gate; UNKNOWN≠PASS; hard-fail→infeasible | `test_unknown_is_not_pass`, `test_hard_failure_makes_infeasible` |
| 029-031 | Pareto + reference fixtures + normalized weighting | `test_pareto_dominance`, `test_weighted_utility_normalized_and_explained` |
| 032-035 | Sensitivity ROBUST/SENSITIVE/UNSTABLE; scenario; uncalibrated regret | `test_sensitivity_robust_vs_sensitive`, `test_regret_not_calibrated_without_scenarios`, `test_regret_calibrated` |
| 036-040 | Reversibility R0-R4 + switching-cost vector + lock-in separate + T3/T4 stronger exit | `test_reversibility_r4_needs_one_way_ack`, `test_switching_cost_vector_and_lock_in_separate`, `test_all_critical_deps_have_exit_profiles` |
| 041-044 | Common-mode; shared upstream; cosmetic diversity; failure-domain | `test_cosmetic_diversity_detected`, `test_shared_upstream_detected`, `test_F5_single_shared_cloud_is_cosmetic` |
| 045-050 | Capability-specific contracts; no universal execute; core + namespaced ext; ext can't redefine core | `test_universal_provider_contract_flagged`, `test_extension_cannot_redefine_core`, `test_extension_must_be_namespaced` |
| 051-055 | Provider profile; id external-ref; error not business state; taxonomy; UNKNOWN_OUTCOME | `test_provider_id_as_canonical_identity_flagged`, `test_provider_error_as_business_state_flagged`, `test_effectful_contract_requires_unknown_outcome` |
| 056-060 | Credential reference; no raw secret; tenant/personal-shared/read-write scope | `test_raw_secret_exposure`, `test_credential_reference_ok`, `test_F1_secret_as_schema_value_caught` |
| 061-065 | Deterministic reference provider + fault; provider-neutral corpus; effectful→NO_EXTERNAL_EFFECT | `test_reference_provider_deterministic_and_fault`, `test_workload_must_be_provider_neutral`, `test_effectful_workload_defaults_no_external_effect` |
| 066-074 | Conformance harness; invalid fails; differential; substitutability 5 classes | `test_conformance_pass_and_substitutability_not_boolean`, `test_M1_substitutability_unknown_reachable` |
| 075-077 | Shadow lab no unauthorized effect; no unsafe dual-run | `test_shadow_lab_blocks_effectful_workload`, `test_F2_shadow_lab_fails_closed_on_missing_effect_mode` |
| 078-084 | Exit readiness profile; critical-without-exit fails; export/state/rollback; drill levels | `test_critical_dependency_without_exit_plan_fails`, `test_data_export_gap_detected`, `test_F4_documented_or_stale_export_is_a_gap`, `test_drill_level_scales_with_criticality` |
| 085-088 | Substitution evidence version-bound (provider/contract/corpus); stale detected | `test_substitution_evidence_version_bound`, `test_F3_stale_substitution_uses_provider_version` |
| 089-098 | Fitness hard/advisory separate; leakage/secret/protocol checks; cannot grant authority; observatory | `test_fitness_catches_raw_secret_and_unsupported_protocol`, `test_observatory_advisory_and_deterministic` |
| 099-106 | Deprecation watch; protocol registry; explicit versions; no floating latest; MCP/A2A interop-boundary; OTel replaceable; review clock; radar advisory | `test_floating_version_flagged`, `test_mcp_must_be_interop_boundary_not_authority`, `test_sunset_protocol_flagged`, `test_radar_valid_rings` |
| 107-111 | Review clock; review-due; invalidated; radar advisory | `test_freshness_states`; `TDR review_by`; `test_radar_valid_rings` |
| 112-117 | Survivability dims separate; scenarios; open-source-not-lockin-free | `test_survivability_dimensions_separate`; `EV-OSS-LOCKIN` evidence |
| 118-122 | Data portability; business-state-not-provider-only; one-way; migration lifecycle; last-safe-rollback | `test_reversibility_r4_needs_one_way_ack`; `FINALIS_TECHNOLOGY_EXIT_PLAN_SCHEMA.json` |
| 123-127 | Change intent; impact cone maps architecture/semantic/program | `test_change_intent_schema`, `test_impact_cone_spans_graphs` |
| 128-134 | SLSA/CycloneDX/SPDX/AI-ML-BOM strategy; no false compliance; attestation≠verification | `test_supply_chain_requires_all_standards`, `test_false_compliance_claim_flagged`, `test_attestation_distinct_from_verification` |
| 135-139 | Model provider separate; Model Capability Profile; no Model Router; provider-identity-uncertainty; no false crypto identity | `test_model_provider_owned_contract_no_router`; `EV-MODEL-SWAP` |
| 140-148 | Proof envelopes deterministic; change on candidate/evidence/exit-plan/fitness-policy; evidence-not-authority; substitution envelope version-bound | `test_decision_envelope_deterministic_and_evidence`, `test_envelope_changes_on_candidate_and_evidence_change`, `test_M2_envelope_binds_pareto_and_sensitivity`, `test_substitution_envelope_version_bound` |
| 149-150 | No product change; no DB migration | `test_tooling_not_imported_by_product`, `test_migration_frontier_unchanged` |
| 151-152 | Lock-in mutation campaign; fitness tests pass | `tests/test_technology_mutation.py` (14); `test_fitness_catches_*` |
| 153-154 | Full suite green; no tests weakened | §9 |
| 155-156 | Swarm + independent verification | §6, §7 |
| 157-158 | P0=0 / P1=0 | `validate` counts |
| 159 | Source URLs complete | `FINALIS_SP0004_RESEARCH_REGISTER.md` (≥40 URLs) |
| 160 | COMPLETE only at 160/160 evidenced | this matrix + §10 |

## 9. Full regression

`python3 -m pytest tests/ --ignore=tests/test_browser_e2e.py`, run as 4 balanced
shards (423 test files, browser e2e excluded):

- **New SP0004 delta — empirically green:** `pytest tests/test_technology_*.py`
  → **103 passed, 0 failed** (decisions 19 · providers 21 · fitness 18 · baseline
  12 · mutation 14 · redteam 19).
- **Pre-existing product suite — provably unchanged:** `git status --porcelain`
  shows **zero tracked-file modifications** — every SP0004 artifact is a NEW
  untracked file under `tools/technology/`, `docs/technology/`,
  `tests/test_technology_*`. No product runtime file imports the tooling
  (`grep tools.technology finalis/` → empty); migration frontier is v27. The
  product suite is therefore byte-identical to the SP0003 exit-0 baseline
  (**5970 passed**) and cannot regress.

- **Full end-to-end run — completed green:** a fresh uninterrupted 4-shard run
  finished:

  | Shard | Exit | Passed | Failed | Errors |
  |---|---|---|---|---|
  | 0 | 0 | 1517 | 0 | 0 |
  | 1 | 0 | 1539 | 0 | 0 |
  | 2 | 0 | 1469 | 0 | 0 |
  | 3 | 0 | 1548 | 0 | 0 |
  | **Total** | **0** | **6073** | **0** | **0** |

**6073 passed, 0 failed, 0 errors — all shards exit 0** (5970 unchanged product
baseline + 103 new SP0004 tests). AC-0004-153 satisfied empirically.

## 10. Final verdict

**SP0004 — FINALIS CONTINUOUS TECHNOLOGY SOVEREIGNTY CONSTITUTION: ACCEPTED.**

All 160 acceptance criteria (AC-0004-001 … 160) have evidence (§8). Gate satisfied:

- Technology model (17 technologies, 16 append-only TDRs, 8 capability contracts,
  17 graph nodes) validates **P0=0, P1=0, P2=0**; `attest` is deterministic and
  binds the decision's Pareto + sensitivity analyses (`EVIDENCE_NOT_AUTHORITY`).
- Finalis owns the semantics + capability contracts; providers are bounded
  implementations behind the five-layer separation; provider IDs, errors and raw
  secrets can never become canonical Finalis semantics.
- Capability-specific contracts with core + namespaced extensions; hard-constraint
  gate (UNKNOWN≠PASS); Pareto → sensitivity → scenario / calibrated-regret;
  reversibility + switching-cost vector + 10-dimension lock-in.
- Common-mode detection (a single shared critical failure domain → cosmetic
  diversity); exit readiness by validated evidence + drills; version-bound
  substitution evidence; a shadow lab that fails closed on any external effect.
- Continuous fitness functions (hard/advisory separate, constitutional P0
  unwaivable); MCP 2025-11-25 / A2A 1.0 pinned as interop boundaries, never
  authority; OpenTelemetry with a replaceable backend; SLSA v1.2 + CycloneDX
  AI/ML-BOM strategy with no compliance claim without evidence.
- **103 technology tests pass**; 14-vector lock-in mutation campaign all caught;
  SWARM-L red-team's 6 defects (2 P0, 4 P1) + SWARM-M's 3 completeness gaps all
  repaired and regression-locked; SWARM-M independently re-verified.
- **No product runtime change; no DB migration** (frontier v27); full regression
  green (§9).

No P0 or P1 remains open. "Choose the best technology of today. Continuously
verify that it is still the right technology. Always preserve the engineering
ability to leave."

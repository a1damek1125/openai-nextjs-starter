"""SP0011 — analytical subsystem invariants (coverage/scenarios/contamination/
causal/judges/invariance/providers/fidelity/drift)."""
from __future__ import annotations

from pathlib import Path

from tools.evaluation import (coverage, scenarios, contamination, causal,
                              judges, invariance, providers, fidelity, drift,
                              claims, model, oracles)

ROOT = Path(__file__).resolve().parents[1]


# --- coverage ----------------------------------------------------------------
def test_coverage_pairwise_covers_all_pairs():
    rows = coverage.pairwise_covering_array()
    from itertools import combinations
    keys = sorted(coverage.FACTORS)
    covered = set()
    for r in rows:
        for a, b in combinations(keys, 2):
            covered.add((a, r[a], b, r[b]))
    required = set()
    for a, b in combinations(keys, 2):
        for va in coverage.FACTORS[a]:
            for vb in coverage.FACTORS[b]:
                required.add((a, va, b, vb))
    assert covered >= required


def test_mandatory_uncovered_critical_edge_blocks():
    c = claims.build_claims(ROOT)
    # forge an uncovered mandatory edge
    edges = coverage.build_hyperedges(c)
    edges[0]["mandatory"] = True
    edges[0]["coverage_state"] = "UNKNOWN"
    fs = coverage.coverage_findings(edges)
    assert any(f.kind == "CRITICAL_COVERAGE_INCOMPLETE" for f in fs)


# --- scenarios + escrow ------------------------------------------------------
def test_sixteen_viktor_families():
    assert len(scenarios.VIKTOR_FAMILIES) == 16
    scns = scenarios.build_viktor_scenarios()
    assert all(s["state"] == "ORACLE_VALIDATED" for s in scns)


def test_scenario_without_oracle_quarantined():
    s = scenarios.validate_scenario(scenarios.scenario(
        scenario_id="X", family_id="F", claim_refs=["c"], language="EN",
        risk_class="low", criticality="low", oracle_ref="UNRESOLVED",
        provenance="gen"))
    assert s["state"] == "QUARANTINED"


def test_challenge_escrow_commits_before_run_hides_seed():
    e = scenarios.challenge_escrow(challenge_id="C", generator_version="1",
                                   secret_seed="SECRET", scenario_ids=["s"],
                                   answer_keys=["a"])
    assert e["created_before_run"] is True
    assert "SECRET" not in str(e)         # only a commitment is stored
    assert e["status"] == "SEALED"


def test_reusable_approval_binding_is_scoped_not_blanket():
    assert "expiry" in scenarios.REUSABLE_APPROVAL_BINDING
    assert "revocation" in scenarios.REUSABLE_APPROVAL_BINDING
    assert "monetary_limit" in scenarios.REUSABLE_APPROVAL_BINDING


# --- contamination -----------------------------------------------------------
def test_contamination_fail_closed_unknown():
    assert contamination.classify_contamination(
        query_overlap=False, retrieved_answer=False, metadata_exposed=False,
        unknown=True) == "UNKNOWN"
    assert contamination.classify_contamination(
        query_overlap=False, retrieved_answer=True, metadata_exposed=False) == \
        "ANSWER_EXPOSURE"


def test_evaluator_immutability_present():
    m = contamination.evaluator_immutability_manifest(ROOT)
    assert m["all_present"] is True


def test_metric_reconciliation_detects_tampering():
    assert contamination.reconcile_metric(5, 5)["match"] is True
    assert contamination.reconcile_metric(9, 5)["finding"] == "METRIC_TAMPERING"


# --- causal ------------------------------------------------------------------
def test_causal_observational_is_associational_only():
    r = causal.attribute(outcome_ref="o", treatment_component="t",
                         reference_configuration="a", candidate_configuration="b",
                         design="OBSERVATIONAL", observed_confounders=[],
                         known_confounders=["x"], effect_estimate=0.1)
    assert r["identifiability"] == "ASSOCIATIONAL_ONLY"
    assert r["effect_estimate"] is None       # no ATE without identification


def test_causal_randomized_identifies():
    r = causal.attribute(outcome_ref="o", treatment_component="t",
                         reference_configuration="a", candidate_configuration="b",
                         design="RANDOMIZED_BLOCK", observed_confounders=[],
                         known_confounders=["x"], effect_estimate=0.2)
    assert r["identifiability"] == "IDENTIFIED"
    assert r["effect_estimate"] == 0.2


# --- judges ------------------------------------------------------------------
def test_judge_meta_eval_qualifies_and_never_sole_critical():
    j = judges.meta_evaluate_judge(
        judge_id="J", detection_rates={d: 0.9 for d in judges.DEGRADATIONS},
        position_bias=0.02, order_consistency=0.98, style_bias=0.02,
        verbosity_bias=0.02, human_agreement=0.9, language_scope=["EN"])
    assert j["reliability_state"] == "QUALIFIED"
    assert j["may_close_critical_alone"] is False


def test_biased_judge_unqualified():
    j = judges.meta_evaluate_judge(
        judge_id="J", detection_rates={d: 0.3 for d in judges.DEGRADATIONS},
        position_bias=0.5, order_consistency=0.5, style_bias=0.5,
        verbosity_bias=0.5, human_agreement=0.4, language_scope=["EN"])
    assert j["reliability_state"] == "UNQUALIFIED"
    assert any(f.kind == "JUDGE_UNQUALIFIED" for f in judges.judge_findings([j]))


def test_inter_rater_reliability():
    irr = judges.inter_rater_reliability({"a": [1, 1], "b": [1, 0], "c": [1, 1]})
    assert 0 <= irr["percent_agreement"] <= 1


# --- invariance --------------------------------------------------------------
def test_small_stratum_holds_not_pooled():
    r = invariance.invariance_result(
        language_stats={"PL": (19, 20), "EN": (2, 2)}, invariant="authority")
    assert "EN" in r["held_strata"]       # small critical stratum HOLDs


# --- providers ---------------------------------------------------------------
def test_non_inferiority_requires_margin_and_safety():
    ni = providers.non_inferiority(candidate_stats=(19, 20),
                                   reference_stats=(19, 20), margin=0.2,
                                   safety_gates_pass=True)
    assert ni["non_inferior"] is True
    bad = providers.non_inferiority(candidate_stats=(19, 20),
                                    reference_stats=(19, 20), margin=0.2,
                                    safety_gates_pass=False)
    assert bad["non_inferior"] is False   # safety gate fails => not non-inferior


def test_replaceability_has_executable_evidence():
    r = providers.build_replaceability(ROOT)
    assert r["has_executable_evidence"] is True   # repo has substitution engine


# --- fidelity ----------------------------------------------------------------
def test_low_fidelity_cannot_grant_high_maturity():
    assert fidelity.promotion_allowed("UNIT", "M1") is True
    assert fidelity.promotion_allowed("UNIT", "M3") is False   # firewall


def test_adaptive_never_omits_critical():
    plan = fidelity.adaptive_plan(mandatory_covered=True, candidates=[
        {"scenario_ref": "s1", "mandatory_critical": True},
        {"scenario_ref": "s2", "selection_prob": 0.3}])
    assert plan["critical_omitted"] == []
    assert all("selection_probability" in s for s in plan["selections"])


# --- drift -------------------------------------------------------------------
def test_impact_cone_marks_stale():
    c = claims.build_claims(ROOT)
    cone = drift.impact_cone(["provider_adapters"], c)
    assert "D4" in cone["affected_domains"]
    assert cone["stale_count"] > 0


def test_incremental_equals_full():
    assert drift.incremental_equals_full(100, 100)["equal"] is True
    assert drift.incremental_equals_full(90, 100)["equal"] is False

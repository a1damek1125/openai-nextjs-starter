"""SP0004 decision-science: inventory, strategic-IP, TDR append-only, hard
constraints, Pareto, sensitivity, reversibility, lock-in. Covers AC-0004-006..043,
069..074 (analysis parts)."""
from __future__ import annotations

from tools.technology.inventory import validate_inventory, inventory_stats
from tools.technology.strategic import validate_boundaries, by_class
from tools.technology.decisions import (validate_tdr, validate_registry,
                                        check_append_only, freshness,
                                        decision_core_hash)
from tools.technology.constraints import candidate_feasible, feasible_set
from tools.technology.pareto import (pareto_frontier, dominates,
                                     normalized_utility)
from tools.technology.sensitivity import sensitivity, minimax_regret
from tools.technology.reversibility import (validate_reversibility,
                                            switching_cost_vector,
                                            lock_in_exposure)
from tools.technology.model import (APPEND_ONLY_VIOLATION, HARD_REQUIREMENT_FAILED,
                                    ONE_WAY_MIGRATION_RISK, INSUFFICIENT_EVIDENCE,
                                    INVALID_TDR, REGRET_NOT_CALIBRATED)


def _kinds(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


# ---- inventory (AC-0004-006/007/008/039) -----------------------------------
def test_inventory_valid_and_stats():
    inv = {"technologies": [
        {"technology_id": "x", "status": "ACTIVE", "criticality": "T3",
         "strategic_class": "ADAPT", "direct_or_transitive": "DIRECT",
         "runtime_scope": "PRODUCTION"}]}
    assert not validate_inventory(inv)
    assert inventory_stats(inv)["direct"] == 1


def test_inventory_bad_criticality_flagged():
    inv = {"technologies": [{"technology_id": "x", "status": "ACTIVE",
                             "criticality": "T9", "strategic_class": "ADAPT"}]}
    assert INVALID_TDR in _kinds(validate_inventory(inv))


# ---- strategic-IP (AC-0004-009/010) ----------------------------------------
def test_strategic_defer_requires_trigger():
    smap = {"boundaries": [{"domain": "d", "strategic_class": "DEFER"}]}
    assert INVALID_TDR in _kinds(validate_boundaries(smap))


def test_strategic_own_domain_outsourced_needs_rationale():
    smap = {"boundaries": [{"domain": "authority", "strategic_class": "BUY"}]}
    assert INVALID_TDR in _kinds(validate_boundaries(smap))


def test_strategic_by_class():
    smap = {"boundaries": [{"domain": "a", "strategic_class": "OWN"},
                           {"domain": "b", "strategic_class": "BUY"}]}
    assert by_class(smap)["OWN"] == ["a"]


# ---- TDR append-only (AC-0004-016/017/018/019) -----------------------------
def _tdr(did, status="ACTIVE", **kw):
    d = {"decision_id": did, "status": status, "fitness_status": "ACTIVE_AND_FIT",
         "criticality": "T2", "reversibility_class": "R1", "scope": "s",
         "problem": "p", "candidates": [], "selected_candidate": None,
         "rejected_candidates": [], "decision_method": ["KEEP_CURRENT"],
         "evidence_refs": ["EV"], "review_by": "2027-01-01"}
    d.update(kw)
    return d


def test_accepted_tdr_without_evidence_fails():
    d = _tdr("T", status="ACCEPTED", evidence_refs=[])
    assert INSUFFICIENT_EVIDENCE in _kinds(validate_tdr(d))


def test_append_only_mutation_fails():
    old = {"decisions": [_tdr("T", scope="original")]}
    new = {"decisions": [_tdr("T", scope="CHANGED IN PLACE")]}
    assert APPEND_ONLY_VIOLATION in _kinds(check_append_only(old, new))


def test_append_only_superseding_ok():
    old = {"decisions": [_tdr("T", scope="original")]}
    # same core preserved + a NEW superseding record added
    new = {"decisions": [_tdr("T", scope="original", status="SUPERSEDED"),
                         _tdr("T2", supersedes=["T"])]}
    assert APPEND_ONLY_VIOLATION not in _kinds(check_append_only(old, new))


def test_freshness_states():
    d = _tdr("T", review_by="2020-01-01")
    assert freshness(d, today="2026-07-11") == "REVIEW_DUE"
    assert freshness(_tdr("T"), today="2026-07-11",
                     invalidating_triggers_fired=True) == "INVALIDATED"
    assert freshness(_tdr("T", review_by="2099-01-01"),
                     today="2026-07-11") == "CURRENT"


# ---- hard constraints (AC-0004-026/027/028) --------------------------------
def test_unknown_is_not_pass():
    c = {"hard_constraint_results": {"security": "PASS", "region": "UNKNOWN"}}
    feasible, failed, unknown = candidate_feasible(c, ["security", "region"])
    assert feasible is False and unknown == ["region"]


def test_hard_failure_makes_infeasible():
    cands = [{"candidate_id": "a", "hard_constraint_results": {"h": "PASS"}},
             {"candidate_id": "b", "hard_constraint_results": {"h": "FAIL"}}]
    assert [c["candidate_id"] for c in feasible_set(cands, ["h"])] == ["a"]


# ---- Pareto (AC-0004-029/030/031) ------------------------------------------
def test_pareto_dominance():
    a = {"candidate_id": "A", "scores": {"cost": 1, "quality": 9}}
    b = {"candidate_id": "B", "scores": {"cost": 2, "quality": 5}}
    crit = [{"key": "cost", "direction": "MIN"},
            {"key": "quality", "direction": "MAX"}]
    assert dominates(a, b, crit) is True
    pf = pareto_frontier([a, b], crit)
    assert pf["non_dominated"] == ["A"]


def test_weighted_utility_normalized_and_explained():
    c = {"candidate_id": "A", "scores": {"q": 8}}
    crit = [{"key": "q", "direction": "MAX", "min": 0, "max": 10, "weight": 1.0}]
    u = normalized_utility(c, crit, {"q": 1.0})
    assert u["utility"] == 0.8 and "breakdown" in u


# ---- sensitivity + regret (AC-0004-032/033/034/035) ------------------------
def test_sensitivity_robust_vs_sensitive():
    crit = [{"key": "q", "direction": "MAX", "min": 0, "max": 10, "weight": 1.0}]
    cands = [{"candidate_id": "A", "scores": {"q": 9}},
             {"candidate_id": "B", "scores": {"q": 1}}]
    assert sensitivity({"criteria": crit, "candidates": cands})[
        "classification"] == "ROBUST"


def test_regret_not_calibrated_without_scenarios():
    d = {"candidates": [{"candidate_id": "A"}], "scenarios": []}
    assert minimax_regret(d)["status"] == REGRET_NOT_CALIBRATED


def test_regret_calibrated():
    d = {"candidates": [{"candidate_id": "A"}, {"candidate_id": "B"}],
         "scenarios": [{"candidate_utility": {"A": 10, "B": 4}},
                       {"candidate_utility": {"A": 2, "B": 8}}]}
    r = minimax_regret(d)
    assert r["status"] == "CALIBRATED" and "minimax_regret_choice" in r


# ---- reversibility + lock-in (AC-0004-036/037/038) -------------------------
def test_reversibility_r4_needs_one_way_ack():
    d = {"decision_id": "T", "reversibility_class": "R4"}
    assert ONE_WAY_MIGRATION_RISK in _kinds(validate_reversibility(d))


def test_switching_cost_vector_and_lock_in_separate():
    d = {"switching_cost": {"data": "LOW"}, "lock_in_exposure": {"data_lock_in": "HIGH"}}
    sc = switching_cost_vector(d)
    assert sc["data"] == "LOW" and sc["state"] == "UNKNOWN"
    li = lock_in_exposure(d)
    assert li["data_lock_in"] == "HIGH" and li["semantic_lock_in"] == "UNKNOWN"


def test_decision_core_hash_deterministic():
    d = _tdr("T")
    assert decision_core_hash(d) == decision_core_hash(dict(d))

"""Regression locks for SWARM-L red-team findings + SWARM-M strengthening
(SP0003 repair round). Each test fails on the pre-repair behaviour."""
from __future__ import annotations

import json

from tools.program_graph.registry import validate_registry
from tools.program_graph.hypergraph import edge_satisfied, prerequisite_ready
from tools.program_graph.scenario import eval_condition, compile_scenario
from tools.program_graph.envelope import build_envelope
from tools.program_graph.voi import evaluate_voi
from tools.program_graph.validate import validate_program
from tools.program_graph.criticality import structural_depth
from tools.program_graph.forecast import monte_carlo_criticality
from tools.program_graph.replan import affected_closure
from tools.program_graph.loader import load_program_bundle
from tools.program_graph.model import (LLM_DEPENDENCY_ACTIVATION, INVALID_HYPEREDGE,
                                       SCENARIO_CONDITION_ERROR,
                                       HARD_DEPENDENCY_CYCLE, INVALID_PROGRAM_SCHEMA)
from tests._pg_helpers import node, edge, program


def _kinds(x):
    fs = x.findings if hasattr(x, "findings") else x
    return {f.kind for f in fs}


# ---- SWARM-L Finding 1 (P0): LLM admission by any model name -----------------
def test_L1_model_name_admission_rejected():
    for name in ("gpt-4o", "claude-opus-4", "o3", "LLM-assisted", "gemini",
                 None, ["human"], ""):
        e = edge("X", ["A"]); e["admitted_by"] = name
        p = program([node("A"), node("X")], [e])
        assert LLM_DEPENDENCY_ACTIVATION in _kinds(validate_registry(p)), name


def test_L1_human_admission_accepted():
    for name in ("ARCHITECTURE_REVIEW", "HUMAN_REVIEW", "PROGRAM_ARCHITECT"):
        e = edge("X", ["A"]); e["admitted_by"] = name
        p = program([node("A"), node("X")], [e])
        assert LLM_DEPENDENCY_ACTIVATION not in _kinds(validate_registry(p)), name


# ---- SWARM-L Finding 2 (P1): duplicate tails cannot pad a threshold ----------
def test_L2_duplicate_tails_do_not_inflate_threshold():
    e = edge("X", ["A", "A"], "AT_LEAST_K_OF_N", threshold_k=2)
    assert edge_satisfied(e, {"A"}) is False   # 1 distinct != 2


def test_L2_duplicate_tail_threshold_flagged_in_schema():
    p = program([node("A"), node("X")],
                [edge("X", ["A", "A"], "AT_LEAST_K_OF_N", threshold_k=2)])
    assert INVALID_HYPEREDGE in _kinds(validate_registry(p))


# ---- SWARM-L Finding 3 (P1): envelope covers gate_bindings/threshold/uncert --
def test_L3_envelope_changes_on_gate_binding_change():
    p = program([node("X")],
                gates=[{"gate_id": "G", "gate_type": "SAFETY_GATE"}],
                gate_bindings=[{"node_id": "X", "gate_id": "G"}])
    h0 = build_envelope(p)["envelope_hash"]
    p2 = json.loads(json.dumps(p)); p2["gate_bindings"] = []   # un-guard!
    assert build_envelope(p2)["envelope_hash"] != h0


def test_L3_envelope_changes_on_threshold_and_uncertainty_change():
    p = program([node("X")])
    h0 = build_envelope(p)["envelope_hash"]
    p2 = json.loads(json.dumps(p))
    p2["threshold_gates"] = [{"gate_id": "t", "threshold_k": 1,
                              "candidate_nodes": ["X"]}]
    assert build_envelope(p2)["envelope_hash"] != h0
    p3 = json.loads(json.dumps(p))
    p3["uncertainties"] = [{"uncertainty_id": "u", "status": "IDENTIFIED",
                            "decision_impact": "LOW"}]
    assert build_envelope(p3)["envelope_hash"] != h0


def test_L3_gate_binding_unknown_refs_flagged():
    p = program([node("X")],
                gates=[{"gate_id": "G", "gate_type": "SAFETY_GATE"}],
                gate_bindings=[{"node_id": "GHOST", "gate_id": "G"},
                               {"node_id": "X", "gate_id": "NOGATE"}])
    assert INVALID_PROGRAM_SCHEMA in _kinds(validate_program(p, "BASELINE"))


# ---- SWARM-L Finding 4 (P1): malformed IN/NOT_IN condition is a diagnostic ---
def test_L4_malformed_in_condition_is_error_not_silent():
    ok, err = eval_condition({"variable": "env", "operator": "IN"},
                             {"env": "prod"})
    assert ok is False and err is not None and err.kind == SCENARIO_CONDITION_ERROR


def test_L4_compile_surfaces_malformed_condition():
    p = program([node("A"), node("X")],
                [edge("X", ["A"], scenario_condition={"variable": "env",
                                                      "operator": "IN"})],
                scenarios=[{"scenario_id": "BASELINE",
                            "variables": {"env": "prod"}, "status": "ACTIVE"}])
    _, findings = compile_scenario(p, "BASELINE")
    assert SCENARIO_CONDITION_ERROR in _kinds(findings)


def test_L4_non_list_value_no_substring_activation():
    # "prod" must NOT be considered "in" the string "prod_allowlist"
    ok, err = eval_condition({"variable": "env", "operator": "IN",
                              "value": "prod_allowlist"}, {"env": "prod"})
    assert ok is False and err is not None


# ---- SWARM-L P2a: ANY_OF/threshold must not raise a phantom hard cycle -------
def test_P2a_or_alternative_not_false_cycle():
    # X <- (A OR B), A <- X, B source. Achievable; must NOT be a hard cycle.
    p = program([node("A"), node("B"), node("X")],
                [edge("X", ["A", "B"], "ANY_OF", dependency_id="e1"),
                 edge("A", ["X"], "ALL_OF", dependency_id="e2")])
    rep = validate_program(p, "BASELINE")
    assert HARD_DEPENDENCY_CYCLE not in _kinds(rep)


def test_P2a_real_all_of_cycle_still_fails():
    p = program([node("A"), node("B")],
                [edge("A", ["B"], "ALL_OF", dependency_id="e1"),
                 edge("B", ["A"], "ALL_OF", dependency_id="e2")])
    assert HARD_DEPENDENCY_CYCLE in _kinds(validate_program(p, "BASELINE"))


# ---- SWARM-L P2b: external-effect precondition is non-bypassable -------------
def test_P2b_external_effect_not_bypassable():
    u = {"uncertainty_id": "u", "dependency_type": "EXTERNAL_EFFECT_PRECONDITION",
         "probability_model": {"p_wrong_now": 1, "p_wrong_after": 0},
         "loss_model": {"impact_loss": 1}, "research_cost": 0}
    assert evaluate_voi(u)["bypassable"] is False


# ---- SWARM-M strengthening: forecast isolation (AC-0003-50) ------------------
def test_M_forecast_does_not_mutate_hard_dependencies():
    p = program([node("A"), node("B")], [edge("B", ["A"])])
    p["duration_models"] = [{"duration_model_id": "d", "node_id": "A",
                             "mode": "THREE_POINT_ESTIMATE",
                             "parameters": {"optimistic": 1, "mode": 2,
                                            "pessimistic": 3}}]
    before = json.dumps(p["hyperedges"], sort_keys=True)
    monte_carlo_criticality(p, samples=50, seed=1)
    structural_depth(p)
    assert json.dumps(p["hyperedges"], sort_keys=True) == before


# ---- SWARM-M strengthening: incremental recompute == full (AC-0003-81) -------
def test_M_incremental_scope_covers_all_changed_values():
    old = program([node(x) for x in ["A", "B", "D", "E"]],
                  [edge("B", ["A"], dependency_id="e1"),
                   edge("E", ["D"], dependency_id="e2")])
    depth_old = structural_depth(old)["depth"]
    new = json.loads(json.dumps(old))
    new["hyperedges"].append(edge("D", ["B"], dependency_id="e3"))  # link chains
    changed = {"D"}
    affected = set(affected_closure(new, changed)["affected"])
    depth_new = structural_depth(new)["depth"]
    # every node whose depth actually changed MUST be inside the affected closure
    for n in depth_new:
        if depth_new[n] != depth_old.get(n):
            assert n in affected, n
    # and unaffected nodes are unchanged (incremental reuse is sound)
    for n in depth_new:
        if n not in affected:
            assert depth_new[n] == depth_old[n]


# ---- SWARM-M strengthening: exhaustive node coverage (AC-0003-06) -----------
def test_M_all_roadmap_and_program_layer_nodes_present():
    import os
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    seq = json.load(open(os.path.join(
        repo, "docs", "roadmap", "ROADMAP_LOCK_1_SP_SEQUENCE.json")))
    ids = {n["node_id"] for n in load_program_bundle()["nodes"]}
    for item in seq["sequence"]:
        assert item["id"] in ids, item["id"]
    for sp in ("SP0000", "SP0001", "SP0002", "SP0003", "SP0004", "SP0010"):
        assert sp in ids, sp

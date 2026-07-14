"""SP0003 uncertainty, duration models, Bayesian admission, VOI, replanning.
Covers AC-0003-46..50, 68..81, 88, 89, 90."""
from __future__ import annotations

from tools.program_graph.forecast import (validate_duration_model,
                                          observation_comparable,
                                          admit_observations)
from tools.program_graph.voi import evaluate_voi, research_priority
from tools.program_graph.replan import affected_closure, replan_events
from tools.program_graph.intent import validate_intent
from tools.program_graph.solver import GreedyReferenceSolver, DEFAULT_SOLVER
from tools.program_graph.model import (INVALID_DURATION_MODEL,
                                       INCOMPARABLE_DURATION_EVIDENCE)
from tests._pg_helpers import node, edge, program


def _kinds(fs):
    return {f.kind for f in fs}


# ---- AC-0003-46/47/48: duration model + Bayesian admission -----------------
def test_valid_duration_model():
    assert not validate_duration_model(
        {"duration_model_id": "d", "mode": "UNKNOWN"})


def test_estimated_mode_requires_parameters():
    fs = validate_duration_model(
        {"duration_model_id": "d", "mode": "THREE_POINT_ESTIMATE",
         "parameters": {}})
    assert INVALID_DURATION_MODEL in _kinds(fs)


def test_comparable_observation_admitted():
    model = {"duration_model_id": "m", "similarity_class": "TOOL_SP",
             "boundary": "b", "blocked_time_policy": "excluded"}
    obs = {"provenance": "run-1", "similarity_class": "TOOL_SP", "boundary": "b",
           "blocked_time_policy": "excluded", "value": 5}
    ok, _ = observation_comparable(model, obs)
    assert ok


def test_incomparable_observation_rejected():
    model = {"duration_model_id": "m", "similarity_class": "TOOL_SP"}
    # wrong similarity class
    bad = {"provenance": "x", "similarity_class": "DOCS_SP", "value": 1}
    admitted, findings = admit_observations(model, [bad])
    assert not admitted
    assert INCOMPARABLE_DURATION_EVIDENCE in _kinds(findings)


def test_missing_provenance_rejected():
    model = {"duration_model_id": "m", "similarity_class": "TOOL_SP"}
    admitted, findings = admit_observations(
        model, [{"similarity_class": "TOOL_SP", "value": 1}])
    assert not admitted


# ---- AC-0003-71..75: value of information ----------------------------------
def test_calibrated_positive_voi():
    u = {"uncertainty_id": "u1", "dependency_type": "CAPABILITY_PRECONDITION",
         "probability_model": {"p_wrong_now": 0.5, "p_wrong_after": 0.0},
         "loss_model": {"impact_loss": 100}, "research_cost": 10}
    r = evaluate_voi(u)
    assert r["status"] == "CALIBRATED" and r["voi"] == 40.0
    assert r["recommend_research_first"] is True


def test_negative_voi():
    u = {"uncertainty_id": "u2", "dependency_type": "CAPABILITY_PRECONDITION",
         "probability_model": {"p_wrong_now": 0.1, "p_wrong_after": 0.09},
         "loss_model": {"impact_loss": 10}, "research_cost": 50}
    r = evaluate_voi(u)
    assert r["status"] == "CALIBRATED" and r["voi"] < 0
    assert r["recommend_research_first"] is False


def test_uncalibrated_voi():
    u = {"uncertainty_id": "u3", "dependency_type": "CAPABILITY_PRECONDITION",
         "probability_model": None, "loss_model": None, "research_cost": None}
    assert evaluate_voi(u)["status"] == "VOI_NOT_CALIBRATED"


def test_voi_cannot_bypass_mandatory_safety():
    u = {"uncertainty_id": "u4", "dependency_type": "SAFETY_PRECONDITION",
         "probability_model": {"p_wrong_now": 0.0, "p_wrong_after": 0.0},
         "loss_model": {"impact_loss": 0}, "research_cost": 0}
    r = evaluate_voi(u)
    assert r["status"] == "MANDATORY_NON_BYPASSABLE" and r["bypassable"] is False


def test_safety_research_priority_protected():
    u = {"uncertainty_id": "u5", "dependency_type": "SAFETY_PRECONDITION",
         "decision_impact": "LOW"}
    assert research_priority(u)["safety_protected"] is True


# ---- AC-0003-68/69/70: uncertain / LLM dependency cannot activate ----------
def test_llm_admitted_dependency_cannot_be_active():
    from tools.program_graph.registry import validate_registry
    from tools.program_graph.model import LLM_DEPENDENCY_ACTIVATION
    e = edge("X", ["A"])
    e["admitted_by"] = "LLM"
    p = program([node("A"), node("X")], [e])
    assert LLM_DEPENDENCY_ACTIVATION in _kinds(validate_registry(p).findings)


def test_under_research_dependency_does_not_block():
    from tools.program_graph.hypergraph import prerequisite_ready
    # X's only edge is UNDER_RESEARCH -> not active -> X is a source (ready)
    p = program([node("A"), node("X")],
                [edge("X", ["A"], status="UNDER_RESEARCH", active_ok=False)])
    assert prerequisite_ready(p, "X", set()) is True


# ---- AC-0003-77..81: replanning --------------------------------------------
def test_affected_closure():
    p = program([node("A"), node("B"), node("C")],
                [edge("B", ["A"], dependency_id="e1"),
                 edge("C", ["B"], dependency_id="e2")])
    r = affected_closure(p, {"A"})
    assert set(r["downstream"]) == {"B", "C"}


def test_replan_events_scopes_recompute():
    p = program([node("A"), node("B")], [edge("B", ["A"])])
    r = replan_events(p, {"event_type": "SP_COMPLETED", "changed_nodes": ["A"]})
    assert "criticality" in r["recompute"] and "dominators" in r["recompute"]


# ---- AC-0003-88/89/90: change intent + solver adapter ----------------------
def test_change_intent_schema():
    assert not validate_intent(
        {"change_id": "c1", "change_kind": "ADD_NODE", "target": "Z"})
    assert validate_intent({"change_id": "c1", "change_kind": "BOGUS",
                            "target": "Z"})


def test_solver_adapter_advisory_not_optimal():
    p = program([node("A", status="READY"), node("B")], [edge("B", ["A"])])
    res = DEFAULT_SOLVER.schedule(p)
    assert res["advisory"] is True and res["optimal"] is False
    assert isinstance(GreedyReferenceSolver().schedule(p)["waves"], list)

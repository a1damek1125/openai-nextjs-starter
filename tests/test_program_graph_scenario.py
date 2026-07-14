"""SP0003 scenario/gate/conflict/rework/temporal layers.
Covers AC-0003-15..37 (scenario, gate bypass, conflict, rework, temporal)."""
from __future__ import annotations

from tools.program_graph.scenario import compile_scenario, eval_condition
from tools.program_graph.hypergraph import prerequisite_ready
from tools.program_graph.gates import (detect_gate_bypass, required_gates_pass,
                                       scenario_invariant_gates)
from tools.program_graph.conflict import (conflicting_pairs, resource_batch_ok,
                                          conflicts_with)
from tools.program_graph.rework import (feedback_clusters, rework_impact,
                                        strongly_connected_components)
from tools.program_graph.temporal import (check_temporal_consistency,
                                          negative_cycle, difference_edges)
from tools.program_graph.validate import validate_program
from tools.program_graph.model import (GATE_BYPASS, RESOURCE_CONFLICT,
                                       TEMPORAL_CONSTRAINT_INCONSISTENCY,
                                       HARD_DEPENDENCY_CYCLE)
from tests._pg_helpers import node, edge, program


def _kinds(x):
    fs = x.findings if hasattr(x, "findings") else x
    return {f.kind for f in fs}


# ---- AC-0003-15/16/17: conditional / scenario dependencies -----------------
def _scenario_program():
    return program(
        [node("A"), node("B"), node("X")],
        [edge("X", ["A"], dependency_id="always"),
         edge("X", ["B"], dependency_id="temporal_only",
              scenario_condition={"variable": "runtime", "operator": "EQUALS",
                                  "value": "TEMPORAL"})],
        scenarios=[
            {"scenario_id": "BASELINE", "variables": {"runtime": "UNDECIDED"},
             "status": "ACTIVE"},
            {"scenario_id": "TEMPORAL", "variables": {"runtime": "TEMPORAL"},
             "status": "ACTIVE"}])


def test_conditional_dep_inactive_outside_scenario():
    p = _scenario_program()
    base, _ = compile_scenario(p, "BASELINE")
    # only the always-edge is active; B-edge inactive under BASELINE
    assert sum(1 for e in p["hyperedges"] if base(e)) == 1


def test_conditional_dep_active_in_matching_scenario():
    p = _scenario_program()
    temporal, _ = compile_scenario(p, "TEMPORAL")
    assert sum(1 for e in p["hyperedges"] if temporal(e)) == 2


def test_scenario_compilation_deterministic():
    p = _scenario_program()
    a1, f1 = compile_scenario(p, "TEMPORAL")
    a2, f2 = compile_scenario(p, "TEMPORAL")
    ids = lambda act: sorted(e["dependency_id"] for e in p["hyperedges"] if act(e))
    assert ids(a1) == ids(a2)


def test_eval_condition_unknown_variable_fails_closed():
    ok, err = eval_condition({"variable": "ghost", "operator": "EQUALS",
                              "value": 1}, {})
    assert ok is False and err is not None


# ---- AC-0003-18/20: scenario cannot deactivate a global safety gate ---------
def test_global_safety_gate_bypass_detected():
    p = program([node("X")],
                gates=[{"gate_id": "G", "gate_type": "SAFETY_GATE",
                        "guarded_nodes": ["X"],
                        "scenario_condition": {"variable": "x",
                                               "operator": "EQUALS",
                                               "value": 1}}])
    base, _ = compile_scenario(p, "BASELINE")
    assert GATE_BYPASS in _kinds(detect_gate_bypass(p, base))


def test_global_gates_are_scenario_invariant():
    p = program([node("X")],
                gates=[{"gate_id": "G", "gate_type": "SAFETY_GATE"}])
    assert scenario_invariant_gates(p)


# ---- AC-0003-22/23/24: resource conflict != false precedence ---------------
def test_false_parallelism_via_resource_conflict():
    p = program([node("A", resource_keys=["lane"]),
                 node("B", resource_keys=["lane"])],
                conflicts=[{"resource_key": "lane", "capacity": 1,
                            "nodes": ["A", "B"]}])
    assert ("A", "B") in conflicting_pairs(p)
    ok, findings = resource_batch_ok(p, {"A", "B"})
    assert ok is False and RESOURCE_CONFLICT in _kinds(findings)
    # but there is NO precedence edge created between them
    assert not p["hyperedges"]


def test_resource_capacity_respected():
    p = program([node(x, resource_keys=["pool"]) for x in ["A", "B", "C"]],
                conflicts=[{"resource_key": "pool", "capacity": 2,
                            "nodes": ["A", "B", "C"]}])
    assert resource_batch_ok(p, {"A", "B"})[0] is True
    assert resource_batch_ok(p, {"A", "B", "C"})[0] is False


# ---- AC-0003-25/26/27/28: rework graph -------------------------------------
def test_rework_scc_detected_and_does_not_fail_hard_dag():
    p = program([node("A"), node("B")],
                rework_edges=[
                    {"rework_edge_id": "r1", "from_node": "A", "to_node": "B",
                     "rework_type": "REWORK_TRIGGER"},
                    {"rework_edge_id": "r2", "from_node": "B", "to_node": "A",
                     "rework_type": "RECALIBRATE_IF_CHANGED"}])
    clusters = feedback_clusters(p)
    assert ["A", "B"] in clusters
    # the hard backbone (no hyperedges) is still acyclic/valid
    rep = validate_program(p, "BASELINE")
    assert HARD_DEPENDENCY_CYCLE not in _kinds(rep)
    assert rep.valid


def test_rework_impact_distinct_from_dependency():
    p = program([node("A"), node("B"), node("C")],
                rework_edges=[{"rework_edge_id": "r1", "from_node": "A",
                               "to_node": "B", "rework_type": "MAY_INVALIDATE"}])
    assert rework_impact(p, {"A"}) == {"B"}
    assert rework_impact(p, {"C"}) == set()


# ---- AC-0003-34/35/36: temporal consistency --------------------------------
def test_temporal_consistent_fixture_passes():
    p = program([node("A"), node("B")],
                temporal_constraints=[
                    {"constraint_id": "t1", "from_timepoint": "A",
                     "to_timepoint": "B", "lower_bound": 1, "upper_bound": 10,
                     "unit": "days", "constraint_type": "REQUIREMENT"}])
    assert not check_temporal_consistency(p)


def test_temporal_inconsistent_fixture_fails():
    # B - A >= 10 AND B - A <= 5  => negative cycle
    p = program([node("A"), node("B")],
                temporal_constraints=[
                    {"constraint_id": "t1", "from_timepoint": "A",
                     "to_timepoint": "B", "lower_bound": 10, "upper_bound": 5,
                     "unit": "days", "constraint_type": "REQUIREMENT"}])
    assert TEMPORAL_CONSTRAINT_INCONSISTENCY in _kinds(
        check_temporal_consistency(p))


def test_contingent_distinct_from_controlled():
    p = program([node("A"), node("B")],
                temporal_constraints=[
                    {"constraint_id": "t1", "from_timepoint": "A",
                     "to_timepoint": "B", "upper_bound": 30, "unit": "days",
                     "constraint_type": "CONTINGENT", "contingent": True}])
    from tools.program_graph.temporal import contingent_timepoints
    assert "B" in contingent_timepoints(p)

"""SP0003 criticality, dominators, cut-set, frontier, impact.
Covers AC-0003-40..45, 51..67."""
from __future__ import annotations

from tools.program_graph.criticality import (structural_depth, cpm,
                                             display_critical_path)
from tools.program_graph.forecast import monte_carlo_criticality
from tools.program_graph.graphalgo import (dominators, min_vertex_cut,
                                           detect_cycle)
from tools.program_graph.hyperreach import hyper_dominators, hyper_min_cut
from tools.program_graph.resilience import program_dominators, milestone_cut_set
from tools.program_graph.frontier import (safe_ready_set, safe_parallel_batches,
                                          downstream_unlock)
from tools.program_graph.impact import (dependency_impact_cone,
                                        rework_impact_cone)
from tests._pg_helpers import node, edge, program


def _chain(ids):
    """A -> B -> C ... linear ALL_OF chain."""
    nodes = [node(i) for i in ids]
    edges = [edge(ids[k + 1], [ids[k]], dependency_id=f"e{k}")
             for k in range(len(ids) - 1)]
    return program(nodes, edges)


# ---- AC-0003-40/41: structural critical path vs oracle ---------------------
def test_structural_depth_linear_chain():
    p = _chain(["A", "B", "C", "D"])
    sd = structural_depth(p)
    assert sd["critical_depth"] == 4
    assert sd["deepest_nodes"] == ["D"]


def test_structural_depth_diamond():
    p = program([node(x) for x in ["A", "B", "C", "D"]],
                [edge("B", ["A"], dependency_id="e1"),
                 edge("C", ["A"], dependency_id="e2"),
                 edge("D", ["B"], dependency_id="e3"),
                 edge("D", ["C"], dependency_id="e4")])
    assert structural_depth(p)["critical_depth"] == 3


# ---- AC-0003-42/43/44/45: CPM ----------------------------------------------
def test_cpm_es_ef_ls_lf_slack():
    p = _chain(["A", "B", "C"])
    durs = {"A": 2, "B": 3, "C": 4}
    r = cpm(p, durs)
    assert r["project_duration"] == 9
    assert r["ES"]["C"] == 5 and r["EF"]["C"] == 9
    assert r["slack"]["A"] == 0 and r["critical_nodes"] == ["A", "B", "C"]


def test_cpm_unknown_duration_not_fabricated():
    # node with no duration -> treated as 0, never invented
    p = _chain(["A", "B"])
    r = cpm(p, {"A": 5})   # B missing
    assert r["EF"]["B"] == 5   # B contributes 0, not a phantom estimate


def test_multiple_critical_paths_all_reported():
    # two parallel equal-length paths -> both critical
    p = program([node(x) for x in ["S", "A", "B", "T"]],
                [edge("A", ["S"], dependency_id="e1"),
                 edge("B", ["S"], dependency_id="e2"),
                 edge("T", ["A"], dependency_id="e3"),
                 edge("T", ["B"], dependency_id="e4")])
    r = cpm(p, {"S": 1, "A": 2, "B": 2, "T": 1})
    assert set(r["critical_nodes"]) == {"S", "A", "B", "T"}


# ---- AC-0003-51/52/53/54: Monte Carlo --------------------------------------
def test_monte_carlo_reproducible():
    p = _chain(["A", "B"])
    p["duration_models"] = [
        {"duration_model_id": "d", "node_id": "A", "mode": "THREE_POINT_ESTIMATE",
         "parameters": {"optimistic": 1, "mode": 2, "pessimistic": 4}}]
    r1 = monte_carlo_criticality(p, samples=100, seed=7)
    r2 = monte_carlo_criticality(p, samples=100, seed=7)
    assert r1 == r2
    assert r1["samples"] == 100 and r1["seed"] == 7


# ---- AC-0003-55/56: dominators (ordinary + AND/OR) -------------------------
def test_dominators_reference_fixture():
    # S -> A -> T and S -> A (A is unavoidable)
    pairs = [("S", "A"), ("A", "T")]
    assert dominators(["S", "A", "T"], pairs, "S", "T") == ["A"]


def test_hyper_dominators_respect_and():
    # X requires BOTH A and B (joint) -> both are dominators
    p = program([node("A"), node("B"), node("X")],
                [edge("X", ["A", "B"], "ALL_OF")])
    assert set(hyper_dominators(p, "X")) == {"A", "B"}


def test_hyper_dominators_respect_or():
    # X via A OR via B -> neither alone is a dominator
    p = program([node("A"), node("B"), node("X")],
                [edge("X", ["A"], dependency_id="e1"),
                 edge("X", ["B"], dependency_id="e2")])
    assert hyper_dominators(p, "X") == []


# ---- AC-0003-57/58/59/60: cut-set ------------------------------------------
def test_single_node_cut_fixture():
    pairs = [("S", "A"), ("A", "T")]
    size, cut = min_vertex_cut(["S", "A", "T"], pairs, "S", "T")
    assert size == 1 and cut == ["A"]


def test_two_node_minimum_cut_fixture():
    # two disjoint paths S->A->T and S->B->T -> min cut = 2
    pairs = [("S", "A"), ("A", "T"), ("S", "B"), ("B", "T")]
    size, cut = min_vertex_cut(["S", "A", "B", "T"], pairs, "S", "T")
    assert size == 2 and sorted(cut) == ["A", "B"]


def test_hyper_cut_single_point():
    p = program([node("A"), node("B"), node("X")],
                [edge("X", ["A", "B"], "ALL_OF")])
    r = hyper_min_cut(p, "X", max_size=3)
    assert r["min_cut_size"] == 1   # blocking A OR B kills X (AND)


def test_hyper_cut_requires_two_for_or():
    p = program([node("A"), node("B"), node("X")],
                [edge("X", ["A"], dependency_id="e1"),
                 edge("X", ["B"], dependency_id="e2")])
    r = hyper_min_cut(p, "X", max_size=3)
    assert r["min_cut_size"] == 2   # must block BOTH alternatives


def test_cut_analysis_requires_scenario_on_bad_scenario():
    p = program([node("A")])
    r = milestone_cut_set(p, "A", scenario_id="NONEXISTENT")
    assert r.get("error") == "CUT_ANALYSIS_REQUIRES_SCENARIO"


# ---- AC-0003-61/62/63/64: frontier -----------------------------------------
def test_frontier_conflict_splits_batches():
    p = program([node("A", status="READY", resource_keys=["lane"]),
                 node("B", status="READY", resource_keys=["lane"])],
                conflicts=[{"resource_key": "lane", "capacity": 1,
                            "nodes": ["A", "B"]}])
    batches = safe_parallel_batches(p, complete=set())
    # A and B are both ready but cannot share a batch (exclusive resource)
    assert all(not ({"A", "B"} <= set(b)) for b in batches)
    assert sorted(x for b in batches for x in b) == ["A", "B"]


def test_downstream_unlock_is_structural():
    p = _chain(["A", "B", "C"])
    assert downstream_unlock(p, "A") == 2   # B and C


# ---- AC-0003-65/66/67: impact cones ----------------------------------------
def test_dependency_impact_cone():
    p = _chain(["A", "B", "C"])
    r = dependency_impact_cone(p, {"A"})
    assert set(r["downstream"]) == {"B", "C"}


def test_rework_cone_distinct_from_dependency_cone():
    p = _chain(["A", "B", "C"])
    p["rework_edges"] = [{"rework_edge_id": "r1", "from_node": "A",
                          "to_node": "X", "rework_type": "REVERIFY_IF_CHANGED"}]
    p["nodes"].append(node("X"))
    dep = set(dependency_impact_cone(p, {"A"})["downstream"])
    rew = set(rework_impact_cone(p, {"A"})["rework_cone"])
    assert dep == {"B", "C"} and rew == {"X"}

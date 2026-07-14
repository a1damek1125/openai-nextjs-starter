"""SP0003 core: schema, hypergraph AND/OR/threshold readiness, cycles, gates,
evidence-derived completion. Covers AC-0003-05..14, 19, 21, 32/33, 38/39."""
from __future__ import annotations

from tools.program_graph.registry import validate_registry, validate_nodes
from tools.program_graph.hypergraph import (prerequisite_ready, edge_satisfied,
                                            threshold_gate_satisfied,
                                            alternative_groups)
from tools.program_graph.validate import validate_program
from tools.program_graph.readiness import ready_nodes, prerequisite_ready_nodes
from tools.program_graph.evidence import (evidence_derived_complete_set,
                                          validate_completion_evidence)
from tools.program_graph.gates import required_gates_pass
from tools.program_graph.model import (P0, P1, DUPLICATE_NODE, UNKNOWN_NODE,
                                       SELF_DEPENDENCY, HARD_DEPENDENCY_CYCLE,
                                       UNPROVEN_HARD_DEPENDENCY,
                                       COMPLETION_EVIDENCE_MISSING)
from tests._pg_helpers import (node, edge, complete_node, sp_evidence, program)


def _kinds(rep):
    findings = rep.findings if hasattr(rep, "findings") else rep
    return {f.kind for f in findings}


# ---- AC-0003-05/06: registry -----------------------------------------------
def test_valid_node_passes():
    rep = validate_registry(program([node("A")]))
    assert rep.valid


def test_duplicate_node_fails():
    rep = validate_registry(program([node("A"), node("A")]))
    assert DUPLICATE_NODE in _kinds(rep)


def test_unknown_head_node_fails():
    p = program([node("A")], [edge("GHOST", ["A"])])
    assert UNKNOWN_NODE in _kinds(validate_registry(p))


# ---- AC-0003-09: ALL_OF ----------------------------------------------------
def test_all_of_blocks_until_all_complete():
    p = program([complete_node("A"), node("B"), node("X")],
                [edge("X", ["A", "B"], "ALL_OF")])
    assert prerequisite_ready(p, "X", {"A"}) is False
    assert prerequisite_ready(p, "X", {"A", "B"}) is True


# ---- AC-0003-10: alternative prerequisite paths ----------------------------
def test_alternative_paths_or_semantics():
    # (A AND B) OR (C AND D) -> X
    p = program([node(x) for x in ["A", "B", "C", "D", "X"]],
                [edge("X", ["A", "B"], dependency_id="e1"),
                 edge("X", ["C", "D"], dependency_id="e2")])
    assert prerequisite_ready(p, "X", {"A", "B"}) is True
    assert prerequisite_ready(p, "X", {"C", "D"}) is True
    assert prerequisite_ready(p, "X", {"A", "C"}) is False
    assert "X" in alternative_groups(p)


# ---- AC-0003-11: AT_LEAST_K_OF_N -------------------------------------------
def test_threshold_k_of_n():
    e = edge("X", ["A", "B", "C"], "AT_LEAST_K_OF_N", threshold_k=2)
    assert edge_satisfied(e, {"A"}) is False
    assert edge_satisfied(e, {"A", "B"}) is True
    assert edge_satisfied(e, {"A", "B", "C"}) is True


def test_explicit_threshold_gate():
    g = {"candidate_nodes": ["A", "B", "C"], "threshold_k": 2}
    assert threshold_gate_satisfied(g, {"A"}) is False
    assert threshold_gate_satisfied(g, {"A", "C"}) is True


# ---- AC-0003-04: numbering does not create dependency ----------------------
def test_numbering_creates_no_dependency():
    # two nodes, no hyperedge -> both are sources / ready despite numeric order
    p = program([node("SP0039"), node("SP0040")])
    assert prerequisite_ready(p, "SP0040", set()) is True


# ---- AC-0003-12/13/14: active hard dependency needs evidence ----------------
def test_active_dependency_requires_evidence():
    bad = edge("X", ["A"])
    bad.pop("evidence_refs")
    p = program([node("A"), node("X")], [bad])
    assert UNPROVEN_HARD_DEPENDENCY in _kinds(validate_registry(p))


def test_active_dependency_with_full_evidence_ok():
    p = program([node("A"), node("X")], [edge("X", ["A"])])
    assert validate_registry(p).valid


# ---- AC-0003-19: hard cycle fails ------------------------------------------
def test_hard_cycle_fails():
    p = program([node("A"), node("B")],
                [edge("A", ["B"], dependency_id="e1"),
                 edge("B", ["A"], dependency_id="e2")])
    rep = validate_program(p, "BASELINE")
    assert HARD_DEPENDENCY_CYCLE in _kinds(rep)
    assert not rep.valid


def test_self_dependency_fails():
    p = program([node("A")], [edge("A", ["A"])])
    assert SELF_DEPENDENCY in _kinds(validate_registry(p))


# ---- AC-0003-32/33: completion requires evidence ---------------------------
def test_fake_complete_without_evidence_fails():
    p = program([complete_node("A")])   # no completion_evidence
    assert COMPLETION_EVIDENCE_MISSING in _kinds(validate_completion_evidence(p))


def test_complete_with_evidence_admitted():
    p = program([complete_node("A")], completion_evidence=sp_evidence("A"))
    assert not validate_completion_evidence(p)
    assert "A" in evidence_derived_complete_set(p)


def test_evidence_derived_complete_gates_downstream():
    # A is "COMPLETE" but has no evidence -> not in complete set -> X not ready
    p = program([complete_node("A"), node("X")], [edge("X", ["A"])])
    assert "A" not in evidence_derived_complete_set(p)
    assert prerequisite_ready(p, "X", evidence_derived_complete_set(p)) is False


# ---- AC-0003-39: gate failure blocks readiness -----------------------------
def test_gate_failure_blocks_readiness():
    p = program([node("X")],
                gates=[{"gate_id": "G1", "gate_type": "SAFETY_GATE",
                        "guarded_nodes": ["X"]}])
    assert "X" not in ready_nodes(p, complete=set(), gate_state={"G1": "FAIL"})
    assert "X" in ready_nodes(p, complete=set(), gate_state={"G1": "PASS"})
    # prerequisite-only readiness ignores the gate
    assert "X" in prerequisite_ready_nodes(p, complete=set())


def test_deterministic_validation():
    p = program([node("A"), node("X")], [edge("X", ["A"])])
    assert validate_program(p).to_dict() == validate_program(p).to_dict()

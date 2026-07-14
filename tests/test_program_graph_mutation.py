"""SP0003 adversarial mutation campaign (§20.25, AC-0003-100). Each corruption of
the canonical program must be caught by a deterministic check — never silently
pass."""
from __future__ import annotations

import json

from tools.program_graph.validate import validate_program
from tools.program_graph.registry import validate_registry
from tools.program_graph.hypergraph import prerequisite_ready
from tools.program_graph.gates import detect_gate_bypass
from tools.program_graph.scenario import compile_scenario
from tools.program_graph.temporal import check_temporal_consistency
from tools.program_graph.conflict import resource_batch_ok
from tools.program_graph.evidence import validate_completion_evidence
from tools.program_graph.forecast import admit_observations
from tools.program_graph.voi import evaluate_voi
from tools.program_graph.envelope import build_envelope
from tools.program_graph.model import (UNPROVEN_HARD_DEPENDENCY, GATE_BYPASS,
                                       HARD_DEPENDENCY_CYCLE, UNKNOWN_NODE,
                                       COMPLETION_EVIDENCE_MISSING,
                                       INCOMPARABLE_DURATION_EVIDENCE,
                                       TEMPORAL_CONSTRAINT_INCONSISTENCY,
                                       LLM_DEPENDENCY_ACTIVATION)
from tests._pg_helpers import node, edge, complete_node, sp_evidence, program


def _kinds(x):
    fs = x.findings if hasattr(x, "findings") else x
    return {f.kind for f in fs}


# 1) hidden prerequisite: ACTIVE dep with no evidence
def test_mut_hidden_prerequisite():
    e = edge("X", ["A"]); e.pop("evidence_refs")
    p = program([node("A"), node("X")], [e])
    assert UNPROVEN_HARD_DEPENDENCY in _kinds(validate_registry(p))


# 2) AND collapsed to OR (joint prerequisite corruption): behaviour differs
def test_mut_and_collapsed_to_or():
    joint = program([node("A"), node("B"), node("X")],
                    [edge("X", ["A", "B"], "ALL_OF")])
    split = program([node("A"), node("B"), node("X")],
                    [edge("X", ["A"], dependency_id="e1"),
                     edge("X", ["B"], dependency_id="e2")])
    # only A complete: joint NOT ready, corrupted split IS ready -> detectable
    assert prerequisite_ready(joint, "X", {"A"}) is False
    assert prerequisite_ready(split, "X", {"A"}) is True


# 3) OR made mandatory (AND): alternative wrongly blocked
def test_mut_or_made_and():
    p_or = program([node("A"), node("B"), node("X")],
                   [edge("X", ["A"], dependency_id="e1"),
                    edge("X", ["B"], dependency_id="e2")])
    p_and = program([node("A"), node("B"), node("X")],
                    [edge("X", ["A", "B"], "ALL_OF")])
    assert prerequisite_ready(p_or, "X", {"A"}) is True
    assert prerequisite_ready(p_and, "X", {"A"}) is False


# 4) K threshold changed
def test_mut_threshold_changed():
    from tools.program_graph.hypergraph import edge_satisfied
    e2 = edge("X", ["A", "B", "C"], "AT_LEAST_K_OF_N", threshold_k=2)
    e3 = edge("X", ["A", "B", "C"], "AT_LEAST_K_OF_N", threshold_k=3)
    assert edge_satisfied(e2, {"A", "B"}) is True
    assert edge_satisfied(e3, {"A", "B"}) is False


# 5) scenario bypass of a global safety gate
def test_mut_scenario_gate_bypass():
    p = program([node("X")],
                gates=[{"gate_id": "G", "gate_type": "SAFETY_GATE",
                        "guarded_nodes": ["X"],
                        "scenario_condition": {"variable": "x",
                                               "operator": "EQUALS", "value": 1}}])
    base, _ = compile_scenario(p, "BASELINE")
    assert GATE_BYPASS in _kinds(detect_gate_bypass(p, base))


# 6) safety gate disabled by rewiring a dependency into a rework cycle
def test_mut_rework_cycle_hidden_as_hard_dependency():
    # a real hard cycle in the prerequisite graph must FAIL (not be excused as
    # "rework")
    p = program([node("A"), node("B")],
                [edge("A", ["B"], dependency_id="e1"),
                 edge("B", ["A"], dependency_id="e2")])
    assert HARD_DEPENDENCY_CYCLE in _kinds(validate_program(p, "BASELINE"))


# 7) resource conflict removed -> false parallelism
def test_mut_resource_conflict_removed():
    # with the conflict, A+B cannot co-batch; removing it would (wrongly) allow it
    with_conflict = program([node("A", resource_keys=["lane"]),
                             node("B", resource_keys=["lane"])],
                            conflicts=[{"resource_key": "lane", "capacity": 1,
                                        "nodes": ["A", "B"]}])
    assert resource_batch_ok(with_conflict, {"A", "B"})[0] is False
    without = program([node("A"), node("B")])   # conflict deleted
    assert resource_batch_ok(without, {"A", "B"})[0] is True  # now unguarded


# 8) fake completion (no evidence)
def test_mut_fake_completion():
    p = program([complete_node("A")])
    assert COMPLETION_EVIDENCE_MISSING in _kinds(validate_completion_evidence(p))


# 9) fake / incomparable duration observation
def test_mut_incomparable_duration_evidence():
    model = {"duration_model_id": "m", "similarity_class": "REAL"}
    admitted, findings = admit_observations(
        model, [{"provenance": "x", "similarity_class": "FAKE", "value": 1}])
    assert INCOMPARABLE_DURATION_EVIDENCE in _kinds(findings) and not admitted


# 10) VOI with fabricated probability trying to bypass mandatory safety
def test_mut_voi_cannot_bypass_safety():
    u = {"uncertainty_id": "u", "dependency_type": "SAFETY_PRECONDITION",
         "probability_model": {"p_wrong_now": 9, "p_wrong_after": 0},
         "loss_model": {"impact_loss": 9}, "research_cost": 0}
    assert evaluate_voi(u)["bypassable"] is False


# 11) LLM-activated hard dependency
def test_mut_llm_dependency_activation():
    e = edge("X", ["A"]); e["admitted_by"] = "GPT"
    p = program([node("A"), node("X")], [e])
    assert LLM_DEPENDENCY_ACTIVATION in _kinds(validate_registry(p))


# 12) partial graph update: dangling node reference
def test_mut_partial_update_dangling_ref():
    p = program([node("A")], [edge("A", ["GHOST"])])
    assert UNKNOWN_NODE in _kinds(validate_registry(p))


# 13) temporal inconsistency injected
def test_mut_temporal_inconsistency():
    p = program([node("A"), node("B")],
                temporal_constraints=[
                    {"constraint_id": "t", "from_timepoint": "A",
                     "to_timepoint": "B", "lower_bound": 20, "upper_bound": 5}])
    assert TEMPORAL_CONSTRAINT_INCONSISTENCY in _kinds(
        check_temporal_consistency(p))


# 14) proof-envelope tamper: mutating a hashed input changes the envelope
def test_mut_envelope_tamper_detected():
    p = program([node("A"), node("X")], [edge("X", ["A"])])
    h0 = build_envelope(p)["envelope_hash"]
    p2 = json.loads(json.dumps(p))
    p2["nodes"][0]["status"] = "COMPLETE"   # silent status flip
    assert build_envelope(p2)["envelope_hash"] != h0

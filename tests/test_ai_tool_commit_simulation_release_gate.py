"""TOOL-B8: release gate. The negative-test release gate passes only when the
fault-injection harness blocked every case; passing it is a precondition of the
B8_V5_ACCEPTED terminal. Its report recomputes and is actor-independent."""
from finalis.ai_employee.tool_commit_simulation import (
    _core_hash, FAULT_CASES)
from tests import _b8_kernel as k


def _gate(o):
    return o["commit_sim_release_gate_report"]


def test_release_gate_passed_on_clean(gate):
    g = _gate(k.clean_outcome(gate))
    assert g["release_gate_status"] == "PASSED"
    assert g["signal"] is None


def test_all_negative_tests_blocked(gate):
    g = _gate(k.clean_outcome(gate))
    assert g["negative_tests_blocked"] == g["negative_tests_total"]


def test_negative_tests_total_matches_corpus(gate):
    g = _gate(k.clean_outcome(gate))
    assert g["negative_tests_total"] == len(FAULT_CASES)


def test_release_gate_hash_recomputes(gate):
    g = _gate(k.clean_outcome(gate))
    assert g["commit_sim_release_gate_hash"] == _core_hash(
        g, "commit_sim_release_gate_hash", "signal")


def test_release_gate_deterministic_across_actor(gate):
    b7 = k.b7_outcome(gate)
    a = _gate(k.prepare(gate, b7, actor_id="alice"))
    b = _gate(k.prepare(gate, b7, actor_id="bob", actor_type="ai_employee"))
    assert a["commit_sim_release_gate_hash"] == b["commit_sim_release_gate_hash"]


def test_release_gate_required_for_accepted_terminal(gate):
    o = k.clean_outcome(gate)
    assert o["commit_simulation_status"] == "B8_V5_ACCEPTED"
    # The accepted terminal implies the release gate passed.
    assert _gate(o)["release_gate_status"] == "PASSED"


def test_conformance_reflects_release_gate_passed(gate):
    cv = k.clean_outcome(gate)["commit_sim_conformance_vector"]
    assert cv["dimensions"]["release_gate_passed"] is True


def test_api_release_gate_subfield(gate):
    sid, _ = gate.prepared_commit_simulation()
    body = gate.cs(sid, "/release-gate").json()
    g = body["commit_sim_release_gate_report"]
    assert g["release_gate_status"] == "PASSED"

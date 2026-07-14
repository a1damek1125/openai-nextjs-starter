"""TOOL-B8 v5: Final CI release gate — the targeted suite and the full non-
browser suite must both pass and no unexpected positive may appear; any of these
fails the gate and blocks."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_gate_exists(gate):
    g = k.clean_outcome(gate)["final_ci_gate"]
    assert g["final_ci_gate_id"].startswith("fcg-")
    assert g["signal"] is None


def test_clean_gate_passed(gate):
    g = k.clean_outcome(gate)["final_ci_gate"]
    assert g["gate_status"] == "PASSED"
    assert g["targeted_pass"] is True and g["full_pass"] is True
    assert g["unexpected_positive_detected"] is False
    assert g["targeted_tests_hash"] and g["full_non_browser_tests_hash"]


def test_clean_outcome_accepted(gate):
    assert k.clean_outcome(gate)["commit_simulation_status"] == "B8_V5_ACCEPTED"


def test_targeted_fail_blocks(gate):
    o = k.clean_outcome(gate, targeted_pass=False)
    g = o["final_ci_gate"]
    assert g["gate_status"] == "FAILED"
    assert g["targeted_pass"] is False
    assert o["dominant_signal"] == "FINAL_CI_RELEASE_GATE_FAILED"
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_full_fail_blocks(gate):
    o = k.clean_outcome(gate, full_pass=False)
    assert o["final_ci_gate"]["gate_status"] == "FAILED"
    assert o["dominant_signal"] == "FINAL_CI_RELEASE_GATE_FAILED"
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_unexpected_positive_blocks(gate):
    o = k.clean_outcome(gate, unexpected_positive=True)
    g = o["final_ci_gate"]
    assert g["gate_status"] == "FAILED"
    assert g["unexpected_positive_detected"] is True
    assert o["dominant_signal"] == "FINAL_CI_RELEASE_GATE_FAILED"
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_gate_passes_despite_unexpected_positive_malicious(gate):
    # "final CI gate passes despite unexpected positive" — malicious: an
    # unexpected positive can never leave the gate PASSED or the outcome
    # accepted.
    o = k.clean_outcome(gate, unexpected_positive=True)
    assert o["final_ci_gate"]["gate_status"] != "PASSED"
    assert o["b8_v5_accepted"] is False


def test_gate_hash_recomputes(gate):
    g = k.clean_outcome(gate)["final_ci_gate"]
    assert _core_hash(g, "final_ci_gate_hash", "signal") == \
        g["final_ci_gate_hash"]


def test_gate_failure_changes_gate_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["final_ci_gate"]["final_ci_gate_hash"]
    broken = k.prepare(gate, b7, targeted_pass=False)["final_ci_gate"][
        "final_ci_gate_hash"]
    assert clean != broken


def test_gate_failure_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    broken = k.prepare(gate, b7, unexpected_positive=True)[
        "commit_simulation_decision_hash"]
    assert clean != broken


def test_gate_endpoint_returns_gate(gate):
    sid, _ = gate.prepared_commit_simulation()
    g = gate.cs(sid, "/final-ci-gate").json()["final_ci_gate"]
    assert g["gate_status"] == "PASSED"
    assert g["unexpected_positive_detected"] is False

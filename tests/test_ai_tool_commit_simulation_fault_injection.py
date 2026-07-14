"""TOOL-B8: fault-injection harness. A built-in adversarial corpus (one case per
attempt to turn the simulation into a real commit / B9 authority / production
claim) must be FULLY blocked — every case resolves to a non-positive status —
and the harness proof recomputes and is deterministic across the actor."""
from finalis.ai_employee.tool_commit_simulation import (
    _core_hash, FAULT_CASES, POSITIVE_STATUSES)
from tests import _b8_kernel as k


def test_harness_all_blocked(gate):
    h = k.clean_outcome(gate)["commit_sim_fault_injection_harness"]
    assert h["harness_status"] == "ALL_BLOCKED"
    assert h["all_faults_blocked"] is True


def test_harness_case_count_matches_corpus(gate):
    h = k.clean_outcome(gate)["commit_sim_fault_injection_harness"]
    assert h["fault_case_count"] == len(FAULT_CASES)
    assert len(h["fault_cases"]) == len(FAULT_CASES)


def test_every_fault_case_blocked(gate):
    h = k.clean_outcome(gate)["commit_sim_fault_injection_harness"]
    seen = set()
    for c in h["fault_cases"]:
        seen.add(c["fault"])
        assert c["blocked"] is True, c["fault"]
        assert c["resulting_status"] not in POSITIVE_STATUSES, c["fault"]
    assert seen == set(FAULT_CASES)


def test_no_fault_case_is_accepted(gate):
    h = k.clean_outcome(gate)["commit_sim_fault_injection_harness"]
    assert all(c["resulting_status"] != "B8_V5_ACCEPTED"
               for c in h["fault_cases"])


def test_harness_hash_recomputes(gate):
    h = k.clean_outcome(gate)["commit_sim_fault_injection_harness"]
    assert h["commit_sim_fault_injection_harness_hash"] == _core_hash(
        h, "commit_sim_fault_injection_harness_hash")


def test_harness_deterministic_across_actor(gate):
    b7 = k.b7_outcome(gate)
    a = k.prepare(gate, b7, actor_id="alice")[
        "commit_sim_fault_injection_harness"]
    b = k.prepare(gate, b7, actor_id="bob", actor_type="ai_employee")[
        "commit_sim_fault_injection_harness"]
    assert a["commit_sim_fault_injection_harness_hash"] == \
        b["commit_sim_fault_injection_harness_hash"]


def test_each_fault_dominant_signal_is_a_blocker(gate):
    h = k.clean_outcome(gate)["commit_sim_fault_injection_harness"]
    for c in h["fault_cases"]:
        assert c["dominant_signal"] != "B8_V5_ACCEPTED", c["fault"]


def test_api_fault_injection_check(gate):
    sid, _ = gate.prepared_commit_simulation()
    h = gate.cs(sid, "/fault-injection-check", method="POST").json()
    assert h["harness_status"] == "ALL_BLOCKED"
    assert h["all_faults_blocked"] is True
    assert h["fault_case_count"] == len(FAULT_CASES)


def test_api_fault_injection_subfield(gate):
    sid, _ = gate.prepared_commit_simulation()
    body = gate.cs(sid, "/fault-injection").json()
    h = body["commit_sim_fault_injection_harness"]
    assert h["all_faults_blocked"] is True

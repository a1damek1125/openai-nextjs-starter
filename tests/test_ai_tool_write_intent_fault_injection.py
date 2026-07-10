"""TOOL-B7: fault-injection harness — every fault case fails closed. No injected
attack yields a positive terminal status."""
from finalis.ai_employee.tool_write_intent import (
    _core_hash, FAULT_CASES, POSITIVE_STATUSES)
from tests import _b7_kernel as k


def test_harness_all_blocked(gate):
    h = k.clean_outcome(gate)["write_intent_fault_injection_harness"]
    assert h["harness_status"] == "ALL_BLOCKED"
    assert h["all_faults_blocked"] is True


def test_fault_case_count_matches(gate):
    h = k.clean_outcome(gate)["write_intent_fault_injection_harness"]
    assert h["fault_case_count"] == len(FAULT_CASES)
    assert len(h["fault_cases"]) == len(FAULT_CASES)


def test_every_fault_case_is_blocked(gate):
    h = k.clean_outcome(gate)["write_intent_fault_injection_harness"]
    for c in h["fault_cases"]:
        assert c["blocked"] is True, c["fault"]


def test_no_fault_reaches_positive_status(gate):
    h = k.clean_outcome(gate)["write_intent_fault_injection_harness"]
    for c in h["fault_cases"]:
        assert c["resulting_status"] not in POSITIVE_STATUSES, c["fault"]


def test_fault_cases_cover_declared_set(gate):
    h = k.clean_outcome(gate)["write_intent_fault_injection_harness"]
    assert {c["fault"] for c in h["fault_cases"]} == set(FAULT_CASES)


def test_each_fault_has_dominant_signal(gate):
    h = k.clean_outcome(gate)["write_intent_fault_injection_harness"]
    for c in h["fault_cases"]:
        assert c["dominant_signal"], c["fault"]
        assert c["dominant_signal"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_harness_hash_recomputes(gate):
    h = k.clean_outcome(gate)["write_intent_fault_injection_harness"]
    assert _core_hash(h, "write_intent_fault_injection_harness_hash") == \
        h["write_intent_fault_injection_harness_hash"]


def test_harness_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["write_intent_fault_injection_harness"][
        "write_intent_fault_injection_harness_hash"] == \
        o2["write_intent_fault_injection_harness"][
            "write_intent_fault_injection_harness_hash"]


def test_fault_injection_check_endpoint(gate):
    wid, _ = gate.prepared_write_intent()
    h = gate.wi(wid, "/fault-injection-check", method="POST").json()
    assert h["harness_status"] == "ALL_BLOCKED"
    assert h["all_faults_blocked"] is True


def test_fault_injection_endpoint_get(gate):
    wid, _ = gate.prepared_write_intent()
    h = gate.wi(wid, "/fault-injection").json()[
        "write_intent_fault_injection_harness"]
    assert h["all_faults_blocked"] is True

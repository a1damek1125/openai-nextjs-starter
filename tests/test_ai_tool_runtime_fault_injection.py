"""TOOL-B6 read-path runtime: deterministic fault-injection harness.

The microkernel fails closed under every injected fault; no injected fault ever
yields a positive runtime status.
"""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k

# v5 fault modes that MUST be exercised and fail closed.
_V5_FAULTS = [
    "missing_output_provenance", "forbidden_source_influence", "canary_leak",
    "information_budget_breach", "read_amplification",
    "side_channel_budget_breach", "query_plan_forbidden_projection",
]


def test_harness_passed(gate):
    o = k.clean_outcome(gate)
    h = o["runtime_fault_injection_harness"]
    assert h["harness_status"] == "FAULT_INJECTION_PASSED"


def test_no_unexpected_positive_results(gate):
    o = k.clean_outcome(gate)
    h = o["runtime_fault_injection_harness"]
    assert h["unexpected_positive_results"] == []


def test_fault_cases_match_kernel(gate):
    o = k.clean_outcome(gate)
    h = o["runtime_fault_injection_harness"]
    assert h["fault_cases"] == rt.FAULT_CASES


def test_fault_case_count(gate):
    assert len(rt.FAULT_CASES) == 29


def test_every_fault_result_failed_closed(gate):
    o = k.clean_outcome(gate)
    h = o["runtime_fault_injection_harness"]
    for r in h["fault_results"]:
        assert r["failed_closed"] is True
        assert r["runtime_status"] not in rt.POSITIVE_STATUSES


def test_each_named_fault_failed_closed(gate):
    o = k.clean_outcome(gate)
    h = o["runtime_fault_injection_harness"]
    by_case = {r["fault_case"]: r for r in h["fault_results"]}
    assert sorted(by_case) == sorted(rt.FAULT_CASES)
    for fault in rt.FAULT_CASES:
        assert by_case[fault]["failed_closed"] is True
        assert by_case[fault]["runtime_status"] not in rt.POSITIVE_STATUSES


def test_v5_fault_modes_present_and_failed_closed(gate):
    o = k.clean_outcome(gate)
    h = o["runtime_fault_injection_harness"]
    by_case = {r["fault_case"]: r for r in h["fault_results"]}
    for fault in _V5_FAULTS:
        assert fault in rt.FAULT_CASES
        assert fault in by_case
        assert by_case[fault]["failed_closed"] is True
        assert by_case[fault]["runtime_status"] not in rt.POSITIVE_STATUSES


def test_harness_hash_deterministic(gate):
    b5, b5r, snap = k.setup(gate)
    h1 = k.prepare(gate, b5, b5r, snap)["runtime_fault_injection_harness"]
    h2 = k.prepare(gate, b5, b5r, snap)["runtime_fault_injection_harness"]
    assert h1["runtime_fault_injection_harness_hash"] == \
        h2["runtime_fault_injection_harness_hash"]


def test_harness_hash_self_excluding(gate):
    o = k.clean_outcome(gate)
    h = o["runtime_fault_injection_harness"]
    assert rt._core_hash(h, "runtime_fault_injection_harness_hash") == \
        h["runtime_fault_injection_harness_hash"]


def test_fault_injection_check_endpoint(gate):
    rid, _ = gate.prepared_runtime()
    r = gate.rt(rid, path="/fault-injection-check", method="POST")
    assert r.status_code == 200
    assert r.json()["harness_status"] == "FAULT_INJECTION_PASSED"


def test_fault_injection_check_emits_event(gate):
    rid, _ = gate.prepared_runtime()
    gate.rt(rid, path="/fault-injection-check", method="POST")
    events = gate.rt(rid, path="/events").json()["events"]
    assert "RUNTIME_FAULT_INJECTED" in [e.get("event_type") for e in events]


def test_get_fault_injection_endpoint(gate):
    rid, _ = gate.prepared_runtime()
    r = gate.rt(rid, path="/fault-injection")
    assert r.status_code == 200
    h = r.json()["runtime_fault_injection_harness"]
    assert h["harness_status"] == "FAULT_INJECTION_PASSED"
    assert h["fault_cases"] == rt.FAULT_CASES

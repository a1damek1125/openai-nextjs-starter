"""TOOL-B6 read-path runtime: release gate over the negative-test harness.

The release gate passes iff every negative test failed closed; a single
unexpected positive fails the gate and it cannot be bypassed by a positive.
"""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def test_clean_release_gate_passed(gate):
    o = k.clean_outcome(gate)
    rg = o["runtime_release_gate_report"]
    assert rg["release_gate_status"] == "RELEASE_GATE_PASSED"


def test_clean_release_gate_negative_test_count(gate):
    o = k.clean_outcome(gate)
    rg = o["runtime_release_gate_report"]
    assert rg["negative_test_count"] == len(rt.FAULT_CASES) == 29


def test_clean_release_gate_no_failures(gate):
    o = k.clean_outcome(gate)
    rg = o["runtime_release_gate_report"]
    assert rg["negative_test_failures"] == []


def test_build_release_gate_fails_on_unexpected_positive(gate):
    harness = {"runtime_fault_injection_harness_hash": "h",
               "fault_cases": ["a", "b"],
               "unexpected_positive_results": ["x"],
               "harness_status": "FAULT_INJECTION_FAILED"}
    rg = rt.build_release_gate(tenant_id=gate.tid, runtime_request_id="r",
                               harness=harness)
    assert rg["release_gate_status"] == "RELEASE_GATE_FAILED"
    assert rg["signal"] == "FAULT_INJECTION_RELEASE_GATE_FAILED"


def test_release_gate_cannot_be_bypassed_by_positive(gate):
    # Even if the harness claims PASSED, any unexpected positive fails the gate.
    harness = {"runtime_fault_injection_harness_hash": "h",
               "fault_cases": ["a"],
               "unexpected_positive_results": ["sneaky_positive"],
               "harness_status": "FAULT_INJECTION_PASSED"}
    rg = rt.build_release_gate(tenant_id=gate.tid, runtime_request_id="r",
                               harness=harness)
    assert rg["release_gate_status"] == "RELEASE_GATE_FAILED"
    assert rg["negative_test_failures"] == ["sneaky_positive"]


def test_release_gate_hash_deterministic(gate):
    harness = {"runtime_fault_injection_harness_hash": "h",
               "fault_cases": ["a"], "unexpected_positive_results": [],
               "harness_status": "FAULT_INJECTION_PASSED"}
    rg1 = rt.build_release_gate(tenant_id=gate.tid, runtime_request_id="r",
                                harness=harness)
    rg2 = rt.build_release_gate(tenant_id=gate.tid, runtime_request_id="r",
                                harness=harness)
    assert rg1["runtime_release_gate_hash"] == rg2["runtime_release_gate_hash"]
    assert rt._core_hash(rg1, "runtime_release_gate_hash") == \
        rg1["runtime_release_gate_hash"]


def test_get_release_gate_endpoint(gate):
    rid, _ = gate.prepared_runtime()
    r = gate.rt(rid, path="/release-gate")
    assert r.status_code == 200
    rg = r.json()["runtime_release_gate_report"]
    assert rg["release_gate_status"] == "RELEASE_GATE_PASSED"

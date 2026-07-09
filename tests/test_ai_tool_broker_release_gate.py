"""TOOL-B5 null broker: adversarial release gate.

The release gate passes iff the fault-injection harness passed with zero
unexpected positive results. It cannot be bypassed: any harness that failed (or
carries an unexpected positive) forces RELEASE_GATE_FAILED and emits the
FAULT_INJECTION_RELEASE_GATE_FAILED signal.
"""
from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k


def test_clean_release_gate_passed(gate):
    rg = k.clean_outcome(gate)["broker_release_gate_report"]
    assert rg["release_gate_status"] == "RELEASE_GATE_PASSED"
    assert rg["signal"] is None


def test_clean_negative_test_count_nineteen(gate):
    rg = k.clean_outcome(gate)["broker_release_gate_report"]
    assert rg["negative_test_count"] == 19


def test_clean_no_negative_test_failures(gate):
    rg = k.clean_outcome(gate)["broker_release_gate_report"]
    assert rg["negative_test_failures"] == []


def test_release_gate_fails_on_unexpected_positive(gate):
    """A harness carrying a non-empty unexpected_positive_results forces the
    release gate to FAILED with the release-gate signal."""
    harness = dict(k.clean_outcome(gate)["fault_injection_harness"])
    harness["unexpected_positive_results"] = ["x"]
    harness["harness_status"] = "FAULT_INJECTION_FAILED"
    rg = b.build_release_gate(tenant_id=gate.tid, broker_request_id="br1",
                              harness=harness)
    assert rg["release_gate_status"] == "RELEASE_GATE_FAILED"
    assert rg["signal"] == "FAULT_INJECTION_RELEASE_GATE_FAILED"
    assert rg["negative_test_failures"] == ["x"]


def test_release_gate_cannot_be_bypassed_by_failed_harness(gate):
    """Even if harness_status is passed-looking but a positive slipped through,
    the presence of unexpected positives forces FAILED (no bypass)."""
    harness = dict(k.clean_outcome(gate)["fault_injection_harness"])
    harness["harness_status"] = "FAULT_INJECTION_PASSED"
    harness["unexpected_positive_results"] = ["mutated_payload"]
    rg = b.build_release_gate(tenant_id=gate.tid, broker_request_id="br1",
                              harness=harness)
    assert rg["release_gate_status"] == "RELEASE_GATE_FAILED"
    assert rg["signal"] == "FAULT_INJECTION_RELEASE_GATE_FAILED"


def test_release_gate_signal_maps_to_dominant(gate):
    assert b.dominant_signal(["FAULT_INJECTION_RELEASE_GATE_FAILED"]) == \
        "FAULT_INJECTION_RELEASE_GATE_FAILED"


def test_release_gate_hash_deterministic(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o1 = k.prepare(gate, d, pobj, head, quality, contract, cert,
                   actor_id="a", created_at="T1")
    o2 = k.prepare(gate, d, pobj, head, quality, contract, cert,
                   actor_id="b", created_at="T2")
    assert (o1["broker_release_gate_report"]["broker_release_gate_hash"] ==
            o2["broker_release_gate_report"]["broker_release_gate_hash"])


def test_endpoint_release_gate_passed(gate):
    rid, _ = gate.prepared_broker()
    r = gate.br(rid, "/release-gate")
    assert r.status_code == 200
    rg = r.json()["broker_release_gate_report"]
    assert rg["release_gate_status"] == "RELEASE_GATE_PASSED"
    assert rg["negative_test_count"] == 19
    assert rg["negative_test_failures"] == []

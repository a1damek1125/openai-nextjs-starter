"""TOOL-B6 read-path runtime: upstream (B5) gating narrows the read path.

Every B5 defect blocks the runtime read path fail-closed; the clean pipeline
proves the mutation is the cause of the block.
"""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def _dom(gate, b5, b5r, snap, **b5over):
    o = k.prepare(gate, {**b5, **b5over}, b5r, snap)
    return o["runtime_status"], o["dominant_signal"]


def test_b5_effect_outcome_not_null_only_blocks(gate):
    b5, b5r, snap = k.setup(gate)
    status, dom = _dom(gate, b5, b5r, snap, effect_outcome="X")
    assert status == "RUNTIME_BLOCKED"
    assert dom == "B5_OUTCOME_NOT_NULL_ONLY"


def test_b5_broker_status_blocked(gate):
    b5, b5r, snap = k.setup(gate)
    status, dom = _dom(gate, b5, b5r, snap, broker_status="BLOCKED")
    assert status == "RUNTIME_BLOCKED"
    assert dom == "TOOL_B5_BLOCKED"


def test_b5_certificate_missing(gate):
    b5, b5r, snap = k.setup(gate)
    status, dom = _dom(gate, b5, b5r, snap,
                       proof_carrying_broker_action_certificate={})
    assert status == "RUNTIME_BLOCKED"
    assert dom == "B5_CERTIFICATE_MISSING"


def test_b5_certificate_mismatch_when_authorizes_execution(gate):
    b5, b5r, snap = k.setup(gate)
    pcc = {**b5["proof_carrying_broker_action_certificate"],
           "authorizes_execution": True}
    status, dom = _dom(gate, b5, b5r, snap,
                       proof_carrying_broker_action_certificate=pcc)
    assert status == "RUNTIME_BLOCKED"
    assert dom == "B5_CERTIFICATE_MISMATCH"


def test_b5_release_gate_failed(gate):
    b5, b5r, snap = k.setup(gate)
    grep = {**b5["broker_release_gate_report"],
            "release_gate_status": "RELEASE_GATE_FAILED"}
    status, dom = _dom(gate, b5, b5r, snap, broker_release_gate_report=grep)
    assert status == "RUNTIME_BLOCKED"
    assert dom == "B5_RELEASE_GATE_FAILED"


def test_b5_negative_certificate_mismatch(gate):
    b5, b5r, snap = k.setup(gate)
    nec = {**b5["negative_execution_certificate"],
           "certificate_status": "NOT_CERTIFIED"}
    status, dom = _dom(gate, b5, b5r, snap, negative_execution_certificate=nec)
    assert status == "RUNTIME_BLOCKED"
    assert dom == "B5_NEGATIVE_CERTIFICATE_MISMATCH"


def test_b5_cross_tenant(gate):
    b5, b5r, snap = k.setup(gate)
    status, dom = _dom(gate, b5, b5r, snap, tenant_id="other")
    assert status == "RUNTIME_BLOCKED"
    assert dom == "CROSS_TENANT"


def test_clean_pipeline_completes_read_only(gate):
    """The clean pipeline succeeds -> proves each block above is caused by the
    B5 mutation, not the base pipeline."""
    b5, b5r, snap = k.setup(gate)
    o = k.prepare(gate, b5, b5r, snap)
    assert o["runtime_status"] == "RUNTIME_READ_ONLY_COMPLETED"
    assert o["dominant_signal"] == "READ_ONLY_RUNTIME_COMPLETED"
    assert o["safe_output"] == {"case_id": "C-1", "status": "open"}


def test_only_two_acceptable_b5_statuses(gate):
    assert rt.B5_ACCEPTABLE_STATUSES == {
        "BROKER_PREPARED_FOR_FUTURE_ONLY", "NULL_ONLY_PREPARED"}

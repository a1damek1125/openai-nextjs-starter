"""TOOL-B7 dual control: when required, a single approval is insufficient; two
independent, server-verified approvals are needed. HIGH risk implies dual
control."""
from tests import _b7_kernel as k


def _two_approvals(probe):
    a1 = k.approval_for(probe)[0]
    a2 = dict(a1)
    a2["approver_id"] = "reviewer3"
    return [a1, a2]


def test_single_approval_with_dual_control_required_blocks(gate):
    b6 = k.b6_outcome(gate)
    probe = k.prepare(gate, b6, approve=False)
    one = k.approval_for(probe)
    o = k.prepare(gate, b6, approve=False, approvals=one,
                  dual_control_required=True)
    assert o["dominant_signal"] == "DUAL_CONTROL_MISSING"
    assert o["write_intent_status"] == "WRITE_INTENT_NEEDS_DUAL_CONTROL"


def test_single_approval_binding_flags_dual_control_missing(gate):
    b6 = k.b6_outcome(gate)
    probe = k.prepare(gate, b6, approve=False)
    o = k.prepare(gate, b6, approve=False, approvals=k.approval_for(probe),
                  dual_control_required=True)
    assert o["approval_binding"]["signal"] == "DUAL_CONTROL_MISSING"
    assert o["approval_binding"]["dual_control_required"] is True


def test_two_independent_approvals_clear_dual_control(gate):
    b6 = k.b6_outcome(gate)
    probe = k.prepare(gate, b6, approve=False)
    o = k.prepare(gate, b6, approve=False, approvals=_two_approvals(probe),
                  dual_control_required=True)
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["approval_binding"]["binding_status"] == "BOUND"


def test_two_approvals_count_two_independent(gate):
    b6 = k.b6_outcome(gate)
    probe = k.prepare(gate, b6, approve=False)
    o = k.prepare(gate, b6, approve=False, approvals=_two_approvals(probe),
                  dual_control_required=True)
    assert o["approval_binding"]["valid_independent_approvals"] == 2


def test_high_risk_requires_dual_control_in_requirement(gate):
    o = k.prepare(gate, k.b6_outcome(gate), approve=False, risk_tier="HIGH")
    assert o["approval_requirement"]["dual_control_required"] is True


def test_high_risk_binding_marks_dual_control_required(gate):
    o = k.prepare(gate, k.b6_outcome(gate), approve=False, risk_tier="HIGH")
    assert o["approval_binding"]["dual_control_required"] is True


def test_low_risk_default_no_dual_control(gate):
    o = k.clean_outcome(gate)
    assert o["approval_binding"]["dual_control_required"] is False
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_dual_control_block_keeps_non_execution(gate):
    b6 = k.b6_outcome(gate)
    probe = k.prepare(gate, b6, approve=False)
    o = k.prepare(gate, b6, approve=False, approvals=k.approval_for(probe),
                  dual_control_required=True)
    assert o["commit_executable_now"] is False
    assert o["ready_for_future_commit_only"] is False

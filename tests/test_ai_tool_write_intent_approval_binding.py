"""TOOL-B7 approval binding: binds one independent, server-verified approval;
fails closed on missing or unverified approvals; binding never executes."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_clean_binding_is_bound(gate):
    b = k.clean_outcome(gate)["approval_binding"]
    assert b["binding_status"] == "BOUND"
    assert b["signal"] is None


def test_clean_binding_has_one_independent_approval(gate):
    b = k.clean_outcome(gate)["approval_binding"]
    assert b["valid_independent_approvals"] == 1


def test_no_approvals_blocks(gate):
    o = k.prepare(gate, k.b6_outcome(gate), approve=False)
    b = o["approval_binding"]
    assert b["signal"] == "APPROVAL_MISSING"
    assert o["dominant_signal"] == "APPROVAL_MISSING"


def test_unverified_approval_blocks(gate):
    o = k.prepare(gate, k.b6_outcome(gate), approve=False, approvals=[{
        "approver_id": "reviewer2", "approver_role": "owner",
        "server_verified": False, "challenge_passed": True}])
    b = o["approval_binding"]
    assert b["signal"] == "APPROVAL_NOT_SERVER_VERIFIED"
    assert o["dominant_signal"] == "APPROVAL_NOT_SERVER_VERIFIED"


def test_binding_binds_future_commit_only(gate):
    b = k.clean_outcome(gate)["approval_binding"]
    assert b["approval_binds_future_commit_only"] is True


def test_binding_does_not_execute(gate):
    b = k.clean_outcome(gate)["approval_binding"]
    assert b["approval_does_not_execute"] is True


def test_binding_records_requirement_hash(gate):
    o = k.clean_outcome(gate)
    assert o["approval_binding"]["approval_requirement_hash"] == \
        o["approval_requirement"]["approval_requirement_hash"]


def test_binding_records_requester_id(gate):
    b = k.clean_outcome(gate)["approval_binding"]
    assert b["requester_id"] == "mgr"


def test_valid_independent_approvals_counts_only_independent(gate):
    # Two independent, server-verified approvals both count.
    b6 = k.b6_outcome(gate)
    probe = k.prepare(gate, b6, approve=False)
    a1 = k.approval_for(probe)[0]
    a2 = dict(a1)
    a2["approver_id"] = "reviewer3"
    o = k.prepare(gate, b6, approve=False, approvals=[a1, a2])
    assert o["approval_binding"]["valid_independent_approvals"] == 2


def test_binding_hash_recomputes(gate):
    b = k.clean_outcome(gate)["approval_binding"]
    assert _core_hash(b, "approval_binding_hash", "signal") == \
        b["approval_binding_hash"]

"""TOOL-B7 no self-approval: the requester cannot approve their own write-intent;
an independent approver is required."""
from tests import _b7_kernel as k


def _self_approval(digest):
    return {"approver_id": "mgr", "approver_role": "owner",
            "server_verified": True, "challenge_passed": True,
            "viewed_package_hash": digest,
            "acknowledgements": {"ACK_DRAFT_ONLY_NO_EXECUTION": True,
                                 "ACK_FUTURE_COMMIT_SEPARATE": True,
                                 "ACK_ESCROW_NON_EXECUTING": True,
                                 "ACK_REVIEWED_SHADOW_DELTAS": True}}


def test_self_approval_detected(gate):
    b6 = k.b6_outcome(gate)
    probe = k.prepare(gate, b6, approve=False)
    digest = probe["review_package"]["review_content_digest"]
    o = k.prepare(gate, b6, approve=False, approvals=[_self_approval(digest)])
    assert o["dominant_signal"] == "SELF_APPROVAL_DETECTED"
    assert o["write_intent_status"] == "WRITE_INTENT_NEEDS_HUMAN_APPROVAL"


def test_self_approval_binding_signal(gate):
    b6 = k.b6_outcome(gate)
    probe = k.prepare(gate, b6, approve=False)
    digest = probe["review_package"]["review_content_digest"]
    o = k.prepare(gate, b6, approve=False, approvals=[_self_approval(digest)])
    assert o["approval_binding"]["signal"] == "SELF_APPROVAL_DETECTED"


def test_self_approval_marked_is_requester(gate):
    b6 = k.b6_outcome(gate)
    probe = k.prepare(gate, b6, approve=False)
    digest = probe["review_package"]["review_content_digest"]
    o = k.prepare(gate, b6, approve=False, approvals=[_self_approval(digest)])
    apprs = o["approval_binding"]["approvals"]
    assert apprs[0]["is_requester"] is True


def test_self_approval_not_counted_as_independent(gate):
    b6 = k.b6_outcome(gate)
    probe = k.prepare(gate, b6, approve=False)
    digest = probe["review_package"]["review_content_digest"]
    o = k.prepare(gate, b6, approve=False, approvals=[_self_approval(digest)])
    assert o["approval_binding"]["valid_independent_approvals"] == 0


def test_independent_approver_clears_self_approval(gate):
    b6 = k.b6_outcome(gate)
    probe = k.prepare(gate, b6, approve=False)
    digest = probe["review_package"]["review_content_digest"]
    independent = k.approval_for(probe)[0]
    o = k.prepare(gate, b6, approve=False,
                  approvals=[_self_approval(digest), independent])
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["approval_binding"]["binding_status"] == "BOUND"


def test_independent_approver_counted(gate):
    b6 = k.b6_outcome(gate)
    probe = k.prepare(gate, b6, approve=False)
    digest = probe["review_package"]["review_content_digest"]
    independent = k.approval_for(probe)[0]
    o = k.prepare(gate, b6, approve=False,
                  approvals=[_self_approval(digest), independent])
    b = o["approval_binding"]
    assert b["valid_independent_approvals"] == 1
    assert any(a["is_requester"] for a in b["approvals"])


def test_only_independent_approver_is_clean(gate):
    # The default clean path uses an independent approver ("reviewer2").
    o = k.clean_outcome(gate)
    apprs = o["approval_binding"]["approvals"]
    assert all(a["is_requester"] is False for a in apprs)
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_DRAFT_CREATED"

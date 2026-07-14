"""TOOL-B7 meaningful human judgment: binds the content-addressed review digest;
a server-verified approval that did not view the exact content is a rubber
stamp and fails closed."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


_STALE_APPROVAL = [{
    "approver_id": "reviewer2", "approver_role": "owner",
    "server_verified": True, "challenge_passed": True,
    "viewed_package_hash": "STALE",
    "acknowledgements": {"ACK_DRAFT_ONLY_NO_EXECUTION": True,
                         "ACK_FUTURE_COMMIT_SEPARATE": True,
                         "ACK_ESCROW_NON_EXECUTING": True,
                         "ACK_REVIEWED_SHADOW_DELTAS": True}}]


def test_clean_judgment_is_meaningful(gate):
    m = k.clean_outcome(gate)["meaningful_judgment"]
    assert m["meaningful_judgment_present"] is True
    assert m["judgment_status"] == "MEANINGFUL"
    assert m["rubber_stamp_detected"] is False


def test_clean_judgment_binds_review_package_hash(gate):
    o = k.clean_outcome(gate)
    assert o["meaningful_judgment"]["review_package_hash"] == \
        o["review_package"]["review_package_hash"]


def test_stale_digest_fails_meaningful_judgment(gate):
    o = k.prepare(gate, k.b6_outcome(gate), approve=False,
                  approvals=_STALE_APPROVAL)
    m = o["meaningful_judgment"]
    assert m["meaningful_judgment_present"] is False
    assert m["signal"] == "MEANINGFUL_JUDGMENT_FAILED"
    assert m["rubber_stamp_detected"] is True


def test_stale_digest_status_needs_meaningful_review(gate):
    o = k.prepare(gate, k.b6_outcome(gate), approve=False,
                  approvals=_STALE_APPROVAL)
    assert o["dominant_signal"] == "MEANINGFUL_JUDGMENT_FAILED"
    assert o["write_intent_status"] == "WRITE_INTENT_NEEDS_MEANINGFUL_REVIEW"


def test_rubber_stamp_status_is_insufficient(gate):
    m = k.prepare(gate, k.b6_outcome(gate), approve=False,
                  approvals=_STALE_APPROVAL)["meaningful_judgment"]
    assert m["judgment_status"] == "INSUFFICIENT"


def test_reuse_old_approval_after_payload_change_fails(gate):
    b6 = k.b6_outcome(gate)
    # Approval viewed the ORIGINAL draft content.
    probe = k.prepare(gate, b6, approve=False)
    old_approval = k.approval_for(probe)
    # Payload then changes -> the review digest changes -> stale approval.
    o = k.prepare(gate, b6, approve=False, approvals=old_approval,
                  proposed_deltas=[{"field_path": "amount", "from_value": "1",
                                    "to_value": "2", "data_class": "INTERNAL"}])
    assert o["meaningful_judgment"]["meaningful_judgment_present"] is False
    assert o["dominant_signal"] == "MEANINGFUL_JUDGMENT_FAILED"


def test_same_payload_reused_approval_still_meaningful(gate):
    b6 = k.b6_outcome(gate)
    probe = k.prepare(gate, b6, approve=False)
    approval = k.approval_for(probe)
    o = k.prepare(gate, b6, approve=False, approvals=approval)
    assert o["meaningful_judgment"]["meaningful_judgment_present"] is True
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_no_candidate_approval_does_not_flag_rubber_stamp(gate):
    # No independent server-verified approval at all -> approval signals
    # dominate; meaningful judgment is not spuriously flagged.
    m = k.prepare(gate, k.b6_outcome(gate), approve=False)["meaningful_judgment"]
    assert m["rubber_stamp_detected"] is False
    assert m["signal"] is None


def test_meaningful_judgment_hash_recomputes(gate):
    m = k.clean_outcome(gate)["meaningful_judgment"]
    assert _core_hash(m, "meaningful_judgment_hash", "signal") == \
        m["meaningful_judgment_hash"]

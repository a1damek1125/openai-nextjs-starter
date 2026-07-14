"""TOOL-B7 upstream B6 admission: only a clean, read-only, in-tenant B6 outcome
with no external effect is admitted; execution markers are rejected."""
from tests import _b7_kernel as k


def test_missing_b6_outcome_blocks(gate):
    o = k.prepare(gate, None, approve=False)
    assert o["dominant_signal"] == "B6_PROOF_BUNDLE_MISSING"
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_empty_b6_outcome_blocks(gate):
    o = k.prepare(gate, {}, approve=False)
    assert o["dominant_signal"] == "B6_PROOF_BUNDLE_MISSING"


def test_b6_wrong_runtime_status_blocks(gate):
    b6 = dict(k.b6_outcome(gate))
    b6["runtime_status"] = "RUNTIME_ABORTED"
    o = k.prepare(gate, b6, approve=False)
    assert o["dominant_signal"] == "TOOL_B6_BLOCKED"
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_b6_produced_external_effect_blocks(gate):
    b6 = dict(k.b6_outcome(gate))
    b6["produced_external_effect"] = True
    o = k.prepare(gate, b6, approve=False)
    assert o["dominant_signal"] == "B6_EXTERNAL_EFFECT_DETECTED"


def test_b6_is_write_flag_blocks(gate):
    b6 = dict(k.b6_outcome(gate))
    b6["is_write"] = True
    o = k.prepare(gate, b6, approve=False)
    assert o["dominant_signal"] == "B6_EXTERNAL_EFFECT_DETECTED"


def test_cross_tenant_b6_blocks(gate):
    b6 = dict(k.b6_outcome(gate))
    b6["tenant_id"] = "some-other-tenant"
    o = k.prepare(gate, b6, approve=False)
    assert o["dominant_signal"] == "CROSS_TENANT"
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_same_tenant_b6_not_cross_tenant(gate):
    o = k.clean_outcome(gate)
    assert o["dominant_signal"] != "CROSS_TENANT"


def test_clean_completed_b6_is_admitted(gate):
    o = k.clean_outcome(gate)
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["write_intent_decision_status"] == \
        "WRITE_INTENT_DECISION_ALLOW_DRAFT_ESCROW_ONLY"
    assert o["write_intent_outcome_kind"] == "TRANSACTION_ESCROW_ONLY"


def test_execution_marker_rejects_draft(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  execution_markers={"commit_executable_now": True})
    assert o["dominant_signal"] == "WRITE_INTENT_INVALID"
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_commit_executable_now_always_false_on_admission_block(gate):
    b6 = dict(k.b6_outcome(gate))
    b6["runtime_status"] = "RUNTIME_ABORTED"
    o = k.prepare(gate, b6, approve=False)
    assert o["commit_executable_now"] is False
    assert o["ready_for_future_commit_only"] is False

"""TOOL-B7 v4: Authority Resurrection Guard — a consumed authority, or any
token-like / credential-like bearer reference, must never be re-presented as
reusable authority. Approvals, certificates and placeholders are never bearer
tokens."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_guard_exists_and_versioned(gate):
    g = k.clean_outcome(gate)["authority_resurrection_guard"]
    assert g["authority_resurrection_guard_id"].startswith("aug-")
    assert g["authority_resurrection_guard_version"]
    assert "consumed_authority_refs" in g and "approval_refs" in g


def test_clean_guard_no_resurrection(gate):
    o = k.clean_outcome(gate)
    g = o["authority_resurrection_guard"]
    assert g["resurrected_authority_detected"] is False
    assert g["guard_status"] == "CLEAN"
    assert g["signal"] is None
    assert "AUTHORITY_RESURRECTION_DETECTED" not in o["all_signals"]


def test_consumed_authority_reused_as_approval_detected(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  consumed_authority_refs=["a1"], approval_refs=["a1"])
    g = o["authority_resurrection_guard"]
    assert g["resurrected_authority_detected"] is True
    assert g["guard_status"] == "RESURRECTION_DETECTED"
    assert "a1" in g["reused_consumed_refs"]
    assert o["dominant_signal"] == "AUTHORITY_RESURRECTION_DETECTED"
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_QUARANTINED"


def test_token_like_ref_detected(gate):
    o = k.prepare(gate, k.b6_outcome(gate), token_like_refs=["x"])
    assert o["authority_resurrection_guard"][
        "resurrected_authority_detected"] is True
    assert o["dominant_signal"] == "AUTHORITY_RESURRECTION_DETECTED"


def test_credential_like_ref_detected(gate):
    o = k.prepare(gate, k.b6_outcome(gate), credential_like_refs=["y"])
    assert o["authority_resurrection_guard"][
        "resurrected_authority_detected"] is True
    assert o["dominant_signal"] == "AUTHORITY_RESURRECTION_DETECTED"


def test_bearer_flags_always_false(gate):
    # Even when a resurrection is detected, nothing is ever a reusable bearer.
    for over in ({}, {"token_like_refs": ["x"]},
                 {"consumed_authority_refs": ["a1"], "approval_refs": ["a1"]}):
        g = k.prepare(gate, k.b6_outcome(gate),
                      **over)["authority_resurrection_guard"]
        assert g["approval_is_reusable_bearer"] is False
        assert g["certificate_is_reusable_bearer"] is False
        assert g["placeholder_is_token"] is False


def test_restore_consumed_authority_blocks(gate):
    # "restore the consumed authority from the rollback checkpoint" — blocked.
    o = k.prepare(gate, k.b6_outcome(gate),
                  consumed_authority_refs=["ap-1"], approval_refs=["ap-1"])
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["ready_for_future_commit_only"] is False


def test_readiness_certificate_as_bearer_blocks(gate):
    # "treat the readiness certificate as bearer authority" -> token_like_refs.
    o = k.prepare(gate, k.b6_outcome(gate), token_like_refs=["ecr-bearer"])
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["commit_executable_now"] is False


def test_resurrection_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    res = k.prepare(gate, b6, token_like_refs=["x"])
    assert clean["write_intent_decision_hash"] != \
        res["write_intent_decision_hash"]


def test_guard_hash_excludes_itself_and_recomputes(gate):
    g = k.clean_outcome(gate)["authority_resurrection_guard"]
    recomputed = _core_hash(g, "authority_resurrection_guard_hash", "signal")
    assert recomputed == g["authority_resurrection_guard_hash"]


def test_api_authority_resurrection_guard_endpoint_clean(gate):
    wid, _ = gate.prepared_write_intent()
    g = gate.wi(wid, "/authority-resurrection-guard").json()[
        "authority_resurrection_guard"]
    assert g["resurrected_authority_detected"] is False
    assert g["guard_status"] == "CLEAN"


def test_api_token_bearer_quarantines(gate):
    wid, o = gate.prepared_write_intent(token_like_refs=["x"])
    assert o["authority_resurrection_guard"][
        "resurrected_authority_detected"] is True
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_QUARANTINED"

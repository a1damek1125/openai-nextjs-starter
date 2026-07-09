"""TOOL-B5: safe-output projection (b.build_safe_output_projection) + safe view.

The safe projection deterministically reduces a raw outcome to non-sensitive
fields only (ids/status/hashes/labels). Every asserted value confirmed by run.
"""
from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k
from tests.conftest import VIEWER

TID = "tenant-b5"
_FORBIDDEN_KEYS = ("payload", "raw_payload", "email", "phone", "provider_result",
                   "approval_ref", "consent_ref", "execution_authority",
                   "secret", "access_token", "credential")


def _proj(raw=None, rp_hash="rp-1"):
    return b.build_safe_output_projection(
        tenant_id=TID, broker_request_id="br1",
        raw_outcome=raw or {"broker_status": "BROKER_PREPARED_FOR_FUTURE_ONLY",
                            "dominant_reason_code": "OK"},
        redaction_policy_hash=rp_hash)


def test_clean_projection_is_matched():
    proj = _proj()
    assert proj["projection_status"] == "SAFE_PROJECTION_MATCHED"
    assert proj["projection_mismatch_fields"] == []
    assert proj["signal"] is None


def test_safe_outcome_contains_only_ids_status_hashes_labels():
    safe = _proj()["safe_outcome"]
    for key in _FORBIDDEN_KEYS:
        assert key not in safe, key
    assert set(safe.keys()) == {
        "broker_request_id", "tenant_id", "broker_status", "effect_outcome",
        "dominant_reason_code", "null_effect_only", "honesty_labels"}
    assert safe["effect_outcome"] == "NO_EFFECT_OUTCOME"
    assert safe["null_effect_only"] is True


def test_safe_outcome_hash_is_deterministic():
    assert _proj()["safe_outcome_hash"] == _proj()["safe_outcome_hash"]


def test_changing_redaction_policy_hash_changes_projection_hash():
    a = _proj(rp_hash="policy-A")
    b_ = _proj(rp_hash="policy-B")
    assert a["safe_output_projection_hash"] != b_["safe_output_projection_hash"]
    # The safe outcome itself does not embed the redaction policy, so it is equal.
    assert a["safe_outcome_hash"] == b_["safe_outcome_hash"]


def test_clean_outcome_has_matched_safe_projection(gate):
    o = k.clean_outcome(gate)
    assert (o["safe_output_projection"]["projection_status"] ==
            "SAFE_PROJECTION_MATCHED")


def test_safe_endpoint_view_has_no_forbidden_leak_keys(gate):
    rid, _ = gate.prepared_broker()
    r = gate.br(rid, path="/safe")
    assert r.status_code == 200
    view = r.json()
    for key in _FORBIDDEN_KEYS:
        assert key not in view, key
    assert "safe_output_projection" in view
    assert view["honesty_labels"] == b.HONESTY_LABELS
    # The projected safe outcome nested in the view is itself leak-free.
    for key in _FORBIDDEN_KEYS:
        assert key not in view["safe_output_projection"], key


def test_safe_endpoint_shows_signals_to_owner(gate):
    rid, o = gate.prepared_broker()
    view = gate.br(rid, path="/safe").json()
    assert view["all_signals"] == o["all_signals"]


def test_safe_endpoint_restricted_viewer_gets_empty_signals(gate):
    rid, _ = gate.prepared_broker()
    view = gate.br(rid, path="/safe", actor=VIEWER).json()
    assert view["all_signals"] == []

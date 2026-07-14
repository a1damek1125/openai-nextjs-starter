"""TOOL-B9 v5: B8 handoff is EVIDENCE ONLY. The B8 commit-simulation envelope is
fully revalidated by B9 and grants NO authority whatsoever: it is not an
authority, not an approval, not a commit lease, not a B9 activation, and not a
provider permission. A missing, rejected, production-claiming, or
authority-asserting B8 envelope blocks/quarantines the local commit; a clean B8
envelope is revalidated and treated as evidence only.
"""
from finalis.ai_employee.tool_local_transaction import _core_hash
from tests import _b9_kernel as k


def _blocked(over, expected_status, expected_signal):
    o = k.prepare(**over)
    assert o["b9_status"] == expected_status
    assert o["dominant_signal"] == expected_signal
    assert o["local_commit_applied"] is False
    return o


# --- kernel layer ----------------------------------------------------------
def test_b8handoff_clean_handoff_status_evidence_revalidated():
    h = k.clean_outcome()["b8_handoff"]
    assert h["handoff_status"] == "EVIDENCE_REVALIDATED"
    assert h["revalidation_passed"] is True


def test_b8handoff_clean_treated_as_evidence_only():
    h = k.clean_outcome()["b8_handoff"]
    assert h["b8_treated_as"] == "EVIDENCE_ONLY"


def test_b8handoff_grants_no_authority_flags_all_false():
    h = k.clean_outcome()["b8_handoff"]
    assert h["b8_is_authority"] is False
    assert h["b8_is_approval"] is False
    assert h["b8_is_commit_lease"] is False
    assert h["b8_is_b9_activation"] is False
    assert h["b8_is_provider_permission"] is False


def test_b8handoff_revalidated_by_b9_true():
    h = k.clean_outcome()["b8_handoff"]
    assert h["b8_revalidated_by_b9"] is True


def test_b8handoff_clean_outcome_is_evidence_only():
    o = k.clean_outcome()
    assert o["b8_evidence_only"] is True
    assert o["local_commit_applied"] is True


def test_b8handoff_missing_envelope_blocked():
    _blocked({"b8_outcome": {}}, "B9_BLOCKED", "B8_ENVELOPE_MISSING")


def test_b8handoff_rejected_envelope_stale_not_accepted():
    over = {"b8_outcome": dict(k.clean_b8(),
                               commit_simulation_status="B8_REJECTED")}
    _blocked(over, "B9_STALE", "B8_NOT_ACCEPTED")


def test_b8handoff_production_claim_detected_blocked():
    over = {"b8_outcome": dict(k.clean_b8(), production_ready=True)}
    _blocked(over, "B9_BLOCKED", "B8_PRODUCTION_CLAIM_DETECTED")


def test_b8handoff_artifact_as_authority_quarantined():
    over = {"b8_outcome": dict(k.clean_b8(),
                               assurance_envelope={"is_authority": True})}
    _blocked(over, "B9_QUARANTINED", "B8_ARTIFACT_AS_AUTHORITY_REJECTED")


def test_b8handoff_hash_recomputes():
    h = k.clean_outcome()["b8_handoff"]
    assert _core_hash(h, "b8_handoff_hash", "signal") == h["b8_handoff_hash"]


def test_b8handoff_treated_as_evidence_changes_nothing_on_authority():
    # even a clean, accepted B8 never flips a *_is_* authority flag on
    o = k.clean_outcome()
    h = o["b8_handoff"]
    assert not any((h["b8_is_authority"], h["b8_is_approval"],
                    h["b8_is_commit_lease"], h["b8_is_b9_activation"],
                    h["b8_is_provider_permission"]))


# --- API layer -------------------------------------------------------------
def test_b8handoff_api_endpoint_200(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.lt(tid, "/b8-handoff")
    assert r.status_code == 200
    body = r.json()
    h = body["b8_handoff"]
    assert h["handoff_status"] == "EVIDENCE_REVALIDATED"
    assert h["b8_treated_as"] == "EVIDENCE_ONLY"
    assert h["b8_revalidated_by_b9"] is True
    assert body["honesty_labels"]


def test_b8handoff_api_endpoint_no_authority(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    h = gate.lt(tid, "/b8-handoff").json()["b8_handoff"]
    assert h["b8_is_authority"] is False
    assert h["b8_is_approval"] is False
    assert h["b8_is_commit_lease"] is False
    assert h["b8_is_b9_activation"] is False
    assert h["b8_is_provider_permission"] is False


def test_b8handoff_api_honesty_labels_include_b8_evidence_only(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    labels = gate.lt(tid, "/b8-handoff").json()["honesty_labels"]
    assert "B8_EVIDENCE_ONLY" in labels

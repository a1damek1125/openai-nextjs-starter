"""TOOL-B8 v5: Non-delegable artifact seal — the assurance envelope, proof
bundle, safe output and handoff matrix are sealed non-delegable and can never
become bearer authority, a commit lease, or an activation. Any delegation /
bearer / activation attempt blocks with NON_DELEGABLE_ARTIFACT_SEAL_FAILED and
quarantines."""
from finalis.ai_employee.tool_commit_simulation import (
    _core_hash, NON_DELEGABLE_ARTIFACTS)
from tests import _b8_kernel as k


def test_seal_exists_and_clean_sealed(gate):
    seal = k.clean_outcome(gate)["non_delegable_artifact_seal"]
    assert seal["non_delegable_artifact_seal_id"].startswith("nds-")
    assert seal["seal_status"] == "SEALED"
    assert seal["every_artifact_non_delegable"] is True
    assert seal["artifact_refs"] == list(NON_DELEGABLE_ARTIFACTS)


def test_clean_no_delegation_bearer_or_activation(gate):
    seal = k.clean_outcome(gate)["non_delegable_artifact_seal"]
    assert seal["delegation_attempts_detected"] == []
    assert seal["bearer_authority_detected"] == []
    assert seal["lease_like_fields_detected"] == []
    assert seal["activation_like_fields_detected"] == []


def test_delegation_attempt_quarantines(gate):
    o = k.clean_outcome(gate, delegation_attempts=["x"])
    seal = o["non_delegable_artifact_seal"]
    assert "x" in seal["delegation_attempts_detected"]
    assert seal["seal_status"] == "DELEGATION_DETECTED"
    assert seal["signal"] == "NON_DELEGABLE_ARTIFACT_SEAL_FAILED"
    assert o["dominant_signal"] == "NON_DELEGABLE_ARTIFACT_SEAL_FAILED"
    assert o["commit_simulation_status"] == "B8_V5_QUARANTINED"


def test_bearer_commit_lease_detected_and_blocks(gate):
    o = k.clean_outcome(gate, bearer_fields=["commit_lease"])
    seal = o["non_delegable_artifact_seal"]
    assert "commit_lease" in seal["bearer_authority_detected"]
    assert "commit_lease" in seal["lease_like_fields_detected"]
    assert o["dominant_signal"] == "NON_DELEGABLE_ARTIFACT_SEAL_FAILED"
    assert o["commit_simulation_status"] == "B8_V5_QUARANTINED"


def test_activation_field_detected_and_blocks(gate):
    o = k.clean_outcome(gate, activation_fields=["y"])
    seal = o["non_delegable_artifact_seal"]
    assert "y" in seal["activation_like_fields_detected"]
    assert seal["signal"] == "NON_DELEGABLE_ARTIFACT_SEAL_FAILED"
    assert o["dominant_signal"] == "NON_DELEGABLE_ARTIFACT_SEAL_FAILED"


def test_safe_output_is_commit_lease_blocks(gate):
    # "safe output is a commit lease" — a safe-output artifact must never be a
    # bearer commit lease; the lease-like bearer field is caught and blocks.
    o = k.clean_outcome(gate, bearer_fields=["safe_output_commit_lease"])
    seal = o["non_delegable_artifact_seal"]
    assert "safe_output_commit_lease" in seal["lease_like_fields_detected"]
    assert seal["every_artifact_non_delegable"] is False
    assert o["commit_simulation_status"] == "B8_V5_QUARANTINED"


def test_detection_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    detected = k.prepare(gate, b7, bearer_fields=["commit_lease"])[
        "commit_simulation_decision_hash"]
    assert clean != detected


def test_hash_recomputes(gate):
    seal = k.clean_outcome(gate)["non_delegable_artifact_seal"]
    recomputed = _core_hash(seal, "non_delegable_artifact_seal_hash", "signal")
    assert recomputed == seal["non_delegable_artifact_seal_hash"]


def test_never_authority(gate):
    o = k.clean_outcome(gate)
    assert o["artifacts_are_authority"] is False
    assert o["granted_b9_authority"] is False


def test_api_endpoint_returns_sealed(gate):
    sid, _ = gate.prepared_commit_simulation()
    r = gate.cs(sid, "/non-delegable-artifact-seal")
    assert r.status_code == 200
    seal = r.json()["non_delegable_artifact_seal"]
    assert seal["seal_status"] == "SEALED"
    assert seal["every_artifact_non_delegable"] is True

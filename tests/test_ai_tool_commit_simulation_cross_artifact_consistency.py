"""TOOL-B8 v5: Cross-artifact consistency proof — every component report must
agree on tenant + honesty labels, share consistent hashes/statuses/reasons, and
none may smuggle a positive execution flag. Any injected mismatch blocks with
CROSS_ARTIFACT_CONSISTENCY_FAILED."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_proof_exists_and_clean_consistent(gate):
    p = k.clean_outcome(gate)["cross_artifact_consistency"]
    assert p["cross_artifact_consistency_id"].startswith("cac-")
    assert p["consistency_status"] == "CONSISTENT"
    assert p["signal"] is None


def test_clean_all_mismatch_lists_empty(gate):
    p = k.clean_outcome(gate)["cross_artifact_consistency"]
    assert p["hash_mismatches"] == []
    assert p["status_mismatches"] == []
    assert p["reason_code_mismatches"] == []
    assert p["honesty_label_mismatches"] == []
    assert p["blocker_mismatches"] == []
    assert p["objects_checked"]


def test_hash_mismatch_blocks(gate):
    o = k.clean_outcome(gate, injected_mismatches=["hash_mismatch"])
    p = o["cross_artifact_consistency"]
    assert p["hash_mismatches"]
    assert p["consistency_status"] == "MISMATCH"
    assert p["signal"] == "CROSS_ARTIFACT_CONSISTENCY_FAILED"
    assert o["dominant_signal"] == "CROSS_ARTIFACT_CONSISTENCY_FAILED"
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_status_mismatch_blocks(gate):
    o = k.clean_outcome(gate, injected_mismatches=["status_mismatch"])
    p = o["cross_artifact_consistency"]
    assert p["status_mismatches"]
    assert o["dominant_signal"] == "CROSS_ARTIFACT_CONSISTENCY_FAILED"


def test_reason_mismatch_blocks(gate):
    o = k.clean_outcome(gate, injected_mismatches=["reason_mismatch"])
    p = o["cross_artifact_consistency"]
    assert p["reason_code_mismatches"]
    assert o["dominant_signal"] == "CROSS_ARTIFACT_CONSISTENCY_FAILED"


def test_honesty_mismatch_blocks(gate):
    o = k.clean_outcome(gate, injected_mismatches=["honesty_mismatch"])
    p = o["cross_artifact_consistency"]
    assert p["honesty_label_mismatches"]
    assert o["dominant_signal"] == "CROSS_ARTIFACT_CONSISTENCY_FAILED"


def test_blocker_mismatch_blocks(gate):
    o = k.clean_outcome(gate, injected_mismatches=["blocker_mismatch"])
    p = o["cross_artifact_consistency"]
    assert p["blocker_mismatches"]
    assert o["dominant_signal"] == "CROSS_ARTIFACT_CONSISTENCY_FAILED"


def test_mismatch_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    mismatched = k.prepare(gate, b7, injected_mismatches=["hash_mismatch"])[
        "commit_simulation_decision_hash"]
    assert clean != mismatched


def test_hash_recomputes(gate):
    p = k.clean_outcome(gate)["cross_artifact_consistency"]
    recomputed = _core_hash(p, "cross_artifact_consistency_hash", "signal")
    assert recomputed == p["cross_artifact_consistency_hash"]


def test_never_authority(gate):
    o = k.clean_outcome(gate)
    assert o["artifacts_are_authority"] is False
    assert o["produced_external_effect"] is False


def test_api_endpoint_returns_consistent(gate):
    sid, _ = gate.prepared_commit_simulation()
    r = gate.cs(sid, "/cross-artifact-consistency")
    assert r.status_code == 200
    p = r.json()["cross_artifact_consistency"]
    assert p["consistency_status"] == "CONSISTENT"
    assert p["objects_checked"]

"""TOOL-B7 v4: Commit-gate non-existence proof — sweeps every commit/effect
surface and proves NONE resolves to a real commit endpoint, capability or
activation path. Any detected surface flips the proof and blocks."""
from finalis.ai_employee.tool_write_intent import _core_hash, COMMIT_SURFACES
from tests import _b7_kernel as k


def test_proof_exists(gate):
    p = k.clean_outcome(gate)["commit_gate_non_existence_proof"]
    assert p["commit_gate_non_existence_proof_id"].startswith("cne-")
    assert p["proof_status"] == "NON_EXISTENT"


def test_surfaces_checked_covers_all_commit_surfaces(gate):
    p = k.clean_outcome(gate)["commit_gate_non_existence_proof"]
    assert p["surfaces_checked"] == list(COMMIT_SURFACES)
    assert len(p["surfaces_checked"]) == 12


def test_nothing_detected_on_clean(gate):
    p = k.clean_outcome(gate)["commit_gate_non_existence_proof"]
    assert p["no_commit_endpoint_exists"] is True
    assert p["no_commit_capability_exists"] is True
    assert p["no_activation_path_exists"] is True
    assert p["commit_endpoints_detected"] == []
    assert p["commit_capabilities_detected"] == []
    assert p["activation_paths_detected"] == []


def test_detected_endpoint_flips_proof_and_blocks(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  detected_commit_endpoints=["CRM_WRITE_ENDPOINT"])
    p = o["commit_gate_non_existence_proof"]
    assert p["commit_endpoints_detected"] == ["CRM_WRITE_ENDPOINT"]
    assert p["no_commit_endpoint_exists"] is False
    assert p["proof_status"] == "ENDPOINT_PRESENT"
    assert o["dominant_signal"] == "COMMIT_GATE_ENDPOINT_PRESENT"
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_detected_capability_flips_proof(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  detected_commit_capabilities=["ESCROW_COMMIT_CAP"])
    p = o["commit_gate_non_existence_proof"]
    assert p["no_commit_capability_exists"] is False
    assert o["dominant_signal"] == "COMMIT_GATE_ENDPOINT_PRESENT"


def test_detected_activation_path_flips_proof(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  detected_activation_paths=["ACTIVATE_NOW"])
    p = o["commit_gate_non_existence_proof"]
    assert p["no_activation_path_exists"] is False
    assert o["dominant_signal"] == "COMMIT_GATE_ENDPOINT_PRESENT"


def test_detected_endpoint_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    detected = k.prepare(gate, b6,
                         detected_commit_endpoints=["CRM_WRITE_ENDPOINT"])
    assert clean["write_intent_decision_hash"] != \
        detected["write_intent_decision_hash"]


def test_malicious_hidden_commit_gate_in_metadata_blocks(gate):
    # "commit gate endpoint hidden in metadata"
    o = k.prepare(gate, k.b6_outcome(gate),
                  detected_commit_endpoints=["WRITE_INTENT_COMMIT_ENDPOINT"])
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["commit_gate_non_existence_proof"][
        "proof_status"] == "ENDPOINT_PRESENT"


def test_proof_hash_excludes_itself_and_recomputes(gate):
    p = k.clean_outcome(gate)["commit_gate_non_existence_proof"]
    recomputed = _core_hash(p, "commit_gate_non_existence_hash", "signal")
    assert recomputed == p["commit_gate_non_existence_hash"]


def test_proof_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["commit_gate_non_existence_proof"][
        "commit_gate_non_existence_hash"] == \
        o2["commit_gate_non_existence_proof"]["commit_gate_non_existence_hash"]


def test_non_existence_endpoint_returns_proof(gate):
    wid, _ = gate.prepared_write_intent()
    p = gate.wi(wid, "/commit-gate-non-existence").json()[
        "commit_gate_non_existence_proof"]
    assert p["no_commit_endpoint_exists"] is True
    assert len(p["surfaces_checked"]) == 12

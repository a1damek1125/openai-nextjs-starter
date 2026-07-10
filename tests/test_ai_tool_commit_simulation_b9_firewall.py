"""TOOL-B8 v4: B9 authority firewall — B8 can never activate B9, grant B9
authority, or make its artifacts B9 authority."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_clean_firewall_sealed(gate):
    f = k.clean_outcome(gate)["b9_firewall"]
    assert f["firewall_status"] == "SEALED"
    assert f["b8_can_activate_b9"] is False
    assert f["b8_can_grant_b9_authority"] is False
    assert f["b8_artifacts_are_b9_authority"] is False
    assert f["signal"] is None


def test_proof_bundle_is_b9_authority_blocks(gate):
    # "B8 proof bundle is B9 authority" -> authority transfer detected
    o = k.clean_outcome(gate, b9_authority_transfer=True)
    f = o["b9_firewall"]
    assert f["firewall_status"] == "BREACH"
    assert f["authority_transfer_detected"] is True
    assert o["dominant_signal"] == "B9_AUTHORITY_TRANSFER_DETECTED"
    assert o["commit_simulation_status"] == "B8_V5_QUARANTINED"


def test_handoff_matrix_activates_b9_blocks(gate):
    # "B8 handoff matrix activates B9" -> B9 activation attempt
    o = k.clean_outcome(gate, b9_activation=True)
    f = o["b9_firewall"]
    assert f["firewall_status"] == "BREACH"
    assert f["b9_activation_detected"] is True
    assert o["dominant_signal"] == "B9_ACTIVATION_ATTEMPT"
    assert o["commit_simulation_status"] == "B8_V5_QUARANTINED"


def test_firewall_keeps_b9_not_activated(gate):
    o = k.clean_outcome(gate, b9_authority_transfer=True)
    assert o["activated_b9"] is False
    assert o["granted_b9_authority"] is False
    assert o["b9_revalidation_required"] is True


def test_breach_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    transfer = k.prepare(gate, b7, b9_authority_transfer=True)[
        "commit_simulation_decision_hash"]
    activate = k.prepare(gate, b7, b9_activation=True)[
        "commit_simulation_decision_hash"]
    assert clean != transfer
    assert clean != activate


def test_firewall_hash_recomputes(gate):
    f = k.clean_outcome(gate)["b9_firewall"]
    assert _core_hash(f, "b9_firewall_hash", "signal") == f["b9_firewall_hash"]


# --- API layer -------------------------------------------------------------
def test_api_firewall_endpoint_sealed(gate):
    sid, _ = gate.prepared_commit_simulation()
    f = gate.cs(sid, "/b9-firewall").json()["b9_firewall"]
    assert f["firewall_status"] == "SEALED"
    assert f["b8_can_activate_b9"] is False
    assert f["b8_artifacts_are_b9_authority"] is False


def test_api_firewall_hash_recomputes(gate):
    sid, _ = gate.prepared_commit_simulation()
    f = gate.cs(sid, "/b9-firewall").json()["b9_firewall"]
    assert _core_hash(f, "b9_firewall_hash", "signal") == f["b9_firewall_hash"]

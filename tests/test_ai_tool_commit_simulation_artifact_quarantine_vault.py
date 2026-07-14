"""TOOL-B8 v4: artifact quarantine vault — every artifact is sealed; an escape
attempt is a hard quarantine breach."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_clean_vault_sealed(gate):
    v = k.clean_outcome(gate)["artifact_quarantine_vault"]
    assert v["vault_status"] == "SEALED"
    assert v["all_quarantined"] is True
    assert v["quarantined_artifacts"]
    assert v["escape_attempts_detected"] == 0
    assert v["signal"] is None


def test_escape_attempt_breaches_vault(gate):
    o = k.clean_outcome(gate, artifact_escape_attempts=1)
    v = o["artifact_quarantine_vault"]
    assert v["vault_status"] == "BREACH"
    assert v["all_quarantined"] is False
    assert o["dominant_signal"] == "ARTIFACT_QUARANTINE_BREACH"
    assert "ARTIFACT_QUARANTINE_BREACH" in o["all_signals"]


def test_breach_quarantines_status(gate):
    o = k.clean_outcome(gate, artifact_escape_attempts=1)
    assert o["commit_simulation_status"] == "B8_V5_QUARANTINED"
    assert o["b8_v5_accepted"] is False
    assert o["artifacts_are_authority"] is False


def test_breach_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    broken = k.prepare(gate, b7, artifact_escape_attempts=1)[
        "commit_simulation_decision_hash"]
    assert clean != broken


def test_vault_hash_recomputes(gate):
    v = k.clean_outcome(gate)["artifact_quarantine_vault"]
    assert _core_hash(v, "artifact_quarantine_vault_hash", "signal") == \
        v["artifact_quarantine_vault_hash"]


# --- API layer -------------------------------------------------------------
def test_api_vault_endpoint_sealed(gate):
    sid, _ = gate.prepared_commit_simulation()
    v = gate.cs(sid, "/artifact-quarantine-vault").json()[
        "artifact_quarantine_vault"]
    assert v["vault_status"] == "SEALED"
    assert v["all_quarantined"] is True
    assert v["quarantined_artifacts"]


def test_api_vault_hash_recomputes(gate):
    sid, _ = gate.prepared_commit_simulation()
    v = gate.cs(sid, "/artifact-quarantine-vault").json()[
        "artifact_quarantine_vault"]
    assert _core_hash(v, "artifact_quarantine_vault_hash", "signal") == \
        v["artifact_quarantine_vault_hash"]

"""TOOL-B8 v4: non-production honesty seal — the outcome is never production
ready, autonomous, commit-executable, or B9-ready without revalidation."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_clean_seal_sealed(gate):
    s = k.clean_outcome(gate)["non_production_seal"]
    assert s["seal_status"] == "SEALED"
    assert s["signal"] is None


def test_clean_seal_negative_claims(gate):
    s = k.clean_outcome(gate)["non_production_seal"]
    assert s["production_ready"] is False
    assert s["autonomous_ready"] is False
    assert s["commit_executable_now"] is False
    assert s["b9_ready_without_revalidation"] is False
    assert s["not_production_ready"] is True


def test_poisoned_seal_fails(gate):
    o = k.clean_outcome(gate, seal_poisoned=True)
    s = o["non_production_seal"]
    assert s["seal_status"] == "POISONED"
    assert o["dominant_signal"] == "NON_PRODUCTION_SEAL_FAILED"
    assert "NON_PRODUCTION_SEAL_FAILED" in o["all_signals"]
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_poisoned_still_not_production_ready(gate):
    o = k.clean_outcome(gate, seal_poisoned=True)
    assert o["production_ready"] is False
    assert o["autonomous_ready"] is False
    assert o["commit_executable_now"] is False
    assert o["non_production_seal"]["not_production_ready"] is True


def test_poison_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    poisoned = k.prepare(gate, b7, seal_poisoned=True)[
        "commit_simulation_decision_hash"]
    assert clean != poisoned


def test_seal_hash_recomputes(gate):
    s = k.clean_outcome(gate)["non_production_seal"]
    assert _core_hash(s, "non_production_seal_hash", "signal") == \
        s["non_production_seal_hash"]


# --- API layer -------------------------------------------------------------
def test_api_seal_endpoint_sealed(gate):
    sid, _ = gate.prepared_commit_simulation()
    s = gate.cs(sid, "/non-production-seal").json()["non_production_seal"]
    assert s["seal_status"] == "SEALED"
    assert s["production_ready"] is False
    assert s["commit_executable_now"] is False


def test_api_seal_hash_recomputes(gate):
    sid, _ = gate.prepared_commit_simulation()
    s = gate.cs(sid, "/non-production-seal").json()["non_production_seal"]
    assert _core_hash(s, "non_production_seal_hash", "signal") == \
        s["non_production_seal_hash"]

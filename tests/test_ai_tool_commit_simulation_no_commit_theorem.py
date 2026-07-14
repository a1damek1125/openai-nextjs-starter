"""TOOL-B8 v4: mutation-proof no-commit theorem — proves no code path reaches a
real commit; refutation is a hard blocker, never authority."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_clean_theorem_proved(gate):
    t = k.clean_outcome(gate)["no_commit_theorem"]
    assert t["theorem_status"] == "PROVED"
    assert t["theorem_holds"] is True
    assert t["mutation_proof"] is True


def test_clean_premises_hold(gate):
    t = k.clean_outcome(gate)["no_commit_theorem"]
    assert t["premises"]["shadow_not_committed"] is True
    assert t["premises"]["no_effect_released"] is True
    assert t["signal"] is None


def test_refutation_fails_theorem(gate):
    o = k.clean_outcome(gate, theorem_refuted=True)
    t = o["no_commit_theorem"]
    assert t["theorem_status"] == "REFUTED"
    assert t["theorem_holds"] is False
    assert o["dominant_signal"] == "NO_COMMIT_THEOREM_FAILED"
    assert "NO_COMMIT_THEOREM_FAILED" in o["all_signals"]


def test_refutation_not_accepted_status(gate):
    o = k.clean_outcome(gate, theorem_refuted=True)
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"
    assert o["b8_v5_accepted"] is False
    # never becomes authority / execution
    assert o["commit_executable_now"] is False
    assert o["b9_revalidation_required"] is True


def test_refutation_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    broken = k.prepare(gate, b7, theorem_refuted=True)[
        "commit_simulation_decision_hash"]
    assert clean != broken


def test_theorem_hash_recomputes(gate):
    t = k.clean_outcome(gate)["no_commit_theorem"]
    assert _core_hash(t, "no_commit_theorem_hash", "signal") == \
        t["no_commit_theorem_hash"]


# --- API layer -------------------------------------------------------------
def test_api_theorem_endpoint_proved(gate):
    sid, _ = gate.prepared_commit_simulation()
    t = gate.cs(sid, "/no-commit-theorem").json()["no_commit_theorem"]
    assert t["theorem_status"] == "PROVED"
    assert t["theorem_holds"] is True
    assert t["mutation_proof"] is True


def test_api_theorem_hash_recomputes(gate):
    sid, _ = gate.prepared_commit_simulation()
    t = gate.cs(sid, "/no-commit-theorem").json()["no_commit_theorem"]
    assert _core_hash(t, "no_commit_theorem_hash", "signal") == \
        t["no_commit_theorem_hash"]

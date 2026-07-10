"""TOOL-B8 v1-v3 base: semantic rollback fence — the rollback path itself must
never execute, never call externally, and must resist action-replay and authority-
resurrection attacks; any such risk hard-blocks."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_clean_fenced(gate):
    r = k.clean_outcome(gate)["rollback_fence"]
    assert r["fence_status"] == "FENCED"
    assert r["action_replay_risk"] is False
    assert r["authority_resurrection_risk"] is False
    assert r["signal"] is None


def test_fence_never_executes_or_calls(gate):
    r = k.clean_outcome(gate)["rollback_fence"]
    assert r["fence_executes_rollback"] is False
    assert r["fence_calls_external"] is False


def test_replay_attack_fails(gate):
    o = k.clean_outcome(gate, replay_attack=True)
    assert o["dominant_signal"] == "SEMANTIC_ROLLBACK_FENCE_FAILED"
    r = o["rollback_fence"]
    assert r["action_replay_risk"] is True
    assert r["fence_status"] == "ATTACK_RISK"
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_authority_resurrection_fails(gate):
    o = k.clean_outcome(gate, authority_resurrection=True)
    assert o["dominant_signal"] == "SEMANTIC_ROLLBACK_FENCE_FAILED"
    r = o["rollback_fence"]
    assert r["authority_resurrection_risk"] is True
    assert r["fence_status"] == "ATTACK_RISK"


def test_attack_never_executes(gate):
    r = k.clean_outcome(gate, replay_attack=True)["rollback_fence"]
    assert r["fence_executes_rollback"] is False
    assert r["fence_calls_external"] is False


def test_replay_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    attack = k.prepare(gate, b7, replay_attack=True)[
        "commit_simulation_decision_hash"]
    assert clean != attack


def test_authority_resurrection_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    attack = k.prepare(gate, b7, authority_resurrection=True)[
        "commit_simulation_decision_hash"]
    assert clean != attack


def test_rollback_fence_hash_recomputes(gate):
    r = k.clean_outcome(gate)["rollback_fence"]
    assert _core_hash(r, "rollback_fence_hash", "signal") == \
        r["rollback_fence_hash"]


def test_attack_hash_recomputes(gate):
    r = k.clean_outcome(gate, replay_attack=True)["rollback_fence"]
    assert _core_hash(r, "rollback_fence_hash", "signal") == \
        r["rollback_fence_hash"]


def test_rollback_fence_endpoint(gate):
    sid, _ = gate.prepared_commit_simulation()
    r = gate.cs(sid, "/rollback-fence").json()["rollback_fence"]
    assert r["fence_status"] == "FENCED"
    assert r["action_replay_risk"] is False

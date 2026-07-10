"""TOOL-B8 v1-v3 base: differential replay — two independent replays of the same
simulation must produce the identical decision hash, else a mismatch blocks."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_clean_consistent(gate):
    r = k.clean_outcome(gate)["differential_replay"]
    assert r["replay_status"] == "CONSISTENT"
    assert r["replay_consistent"] is True
    assert r["signal"] is None


def test_clean_replay_hashes_match(gate):
    r = k.clean_outcome(gate)["differential_replay"]
    assert r["replay_a_hash"]
    assert r["replay_a_hash"] == r["replay_b_hash"]


def test_inconsistent_mismatch(gate):
    o = k.clean_outcome(gate, replay_consistent=False)
    assert o["dominant_signal"] == "DIFFERENTIAL_REPLAY_MISMATCH"
    r = o["differential_replay"]
    assert r["replay_status"] == "MISMATCH"
    assert r["replay_consistent"] is False


def test_mismatch_replay_hashes_differ(gate):
    r = k.clean_outcome(gate, replay_consistent=False)["differential_replay"]
    assert r["replay_a_hash"] != r["replay_b_hash"]


def test_mismatch_blocks(gate):
    o = k.clean_outcome(gate, replay_consistent=False)
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_mismatch_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    mismatch = k.prepare(gate, b7, replay_consistent=False)[
        "commit_simulation_decision_hash"]
    assert clean != mismatch


def test_differential_replay_hash_recomputes(gate):
    r = k.clean_outcome(gate)["differential_replay"]
    assert _core_hash(r, "differential_replay_hash", "signal") == \
        r["differential_replay_hash"]


def test_mismatch_hash_recomputes(gate):
    r = k.clean_outcome(gate, replay_consistent=False)["differential_replay"]
    assert _core_hash(r, "differential_replay_hash", "signal") == \
        r["differential_replay_hash"]


def test_differential_replay_endpoint(gate):
    sid, _ = gate.prepared_commit_simulation()
    r = gate.cs(sid, "/differential-replay").json()["differential_replay"]
    assert r["replay_status"] == "CONSISTENT"
    assert r["replay_consistent"] is True

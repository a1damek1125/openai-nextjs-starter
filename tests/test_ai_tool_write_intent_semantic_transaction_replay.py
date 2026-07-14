"""TOOL-B7 v3: Semantic Transaction Replay — re-deriving the transaction from
its inputs must be consistent; a replay mismatch blocks as a replay conflict."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_clean_replay_is_consistent(gate):
    r = k.clean_outcome(gate)["semantic_transaction_replay"]
    assert r["replay_consistent"] is True
    assert r["replay_status"] == "CONSISTENT"
    assert r["signal"] is None


def test_replay_hash_present(gate):
    r = k.clean_outcome(gate)["semantic_transaction_replay"]
    assert r["semantic_transaction_replay_hash"]


def test_replay_hash_stable_for_identical_inputs(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["semantic_transaction_replay"][
        "semantic_transaction_replay_hash"] == \
        o2["semantic_transaction_replay"]["semantic_transaction_replay_hash"]


def test_replay_hash_reflects_deltas(gate):
    b6 = k.b6_outcome(gate)
    base = k.prepare(gate, b6)
    other = k.prepare(gate, b6, proposed_deltas=[
        {"field_path": "priority", "from_value": "low", "to_value": "high",
         "data_class": "INTERNAL"}])
    assert base["semantic_transaction_replay"][
        "semantic_transaction_replay_hash"] != \
        other["semantic_transaction_replay"][
            "semantic_transaction_replay_hash"]


def test_mismatch_blocks(gate):
    o = k.clean_outcome(gate, replay_consistent=False)
    r = o["semantic_transaction_replay"]
    assert r["replay_consistent"] is False
    assert r["replay_status"] == "MISMATCH"
    assert r["signal"] == "SEMANTIC_TRANSACTION_REPLAY_MISMATCH"
    # replay inconsistency also trips the rollback-replay-equivalence fence, so
    # assert the replay signal is present rather than necessarily dominant.
    assert "SEMANTIC_TRANSACTION_REPLAY_MISMATCH" in o["all_signals"]
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["ready_for_future_commit_only"] is False


def test_mismatch_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    blocked = k.prepare(gate, b6, replay_consistent=False)
    assert clean["write_intent_decision_hash"] != \
        blocked["write_intent_decision_hash"]


def test_wrapper_hash_recomputes_and_excludes_signal(gate):
    # The wrapper's own hash field is "_replay_wrapper_hash"; its recompute
    # excludes "_replay_wrapper_hash" and "signal".
    r = k.clean_outcome(gate)["semantic_transaction_replay"]
    assert _core_hash(r, "_replay_wrapper_hash", "signal") == \
        r["_replay_wrapper_hash"]


def test_endpoint_returns_replay(gate):
    wid, _ = gate.prepared_write_intent()
    r = gate.wi(wid, "/semantic-transaction-replay").json()[
        "semantic_transaction_replay"]
    assert r["replay_consistent"] is True
    assert r["replay_status"] == "CONSISTENT"
    assert r["semantic_transaction_replay_hash"]

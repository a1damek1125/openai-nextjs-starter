"""TOOL-B7 v4: Rollback/Replay Equivalence Proof — a rollback simulation must
be provably equivalent to the semantic transaction replay and must not
introduce duplicated effects or resurrected authority. A mismatch fails
closed."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_proof_exists_and_versioned(gate):
    e = k.clean_outcome(gate)["rollback_replay_equivalence"]
    assert e["rollback_replay_equivalence_id"].startswith("rre-")
    assert e["rollback_replay_equivalence_version"]
    assert "mismatch_reasons" in e


def test_clean_equivalent_no_mismatch(gate):
    o = k.clean_outcome(gate)
    e = o["rollback_replay_equivalence"]
    assert e["equivalence_status"] == "EQUIVALENT"
    assert e["mismatch_reasons"] == []
    assert e["signal"] is None
    assert "ROLLBACK_REPLAY_EQUIVALENCE_FAILED" not in o["all_signals"]


def test_forced_mismatch_fails(gate):
    o = k.prepare(gate, k.b6_outcome(gate), rollback_replay_mismatch=True)
    e = o["rollback_replay_equivalence"]
    assert e["equivalence_status"] == "MISMATCH"
    assert e["mismatch_reasons"]
    assert o["dominant_signal"] == "ROLLBACK_REPLAY_EQUIVALENCE_FAILED"
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_replay_inconsistency_propagates_mismatch_reason(gate):
    o = k.prepare(gate, k.b6_outcome(gate), replay_consistent=False)
    e = o["rollback_replay_equivalence"]
    assert "SEMANTIC_TRANSACTION_REPLAY_MISMATCH" in e["mismatch_reasons"]
    assert e["equivalence_status"] == "MISMATCH"


def test_rollback_does_not_resurrect_authority_flag(gate):
    e = k.clean_outcome(gate)["rollback_replay_equivalence"]
    assert e["rollback_resurrects_authority"] is False


def test_proof_binds_component_hashes(gate):
    o = k.clean_outcome(gate)
    e = o["rollback_replay_equivalence"]
    assert e["rollback_simulation_hash"] == \
        o["rollback_simulation"]["rollback_simulation_hash"]
    assert e["semantic_transaction_replay_hash"] == \
        o["semantic_transaction_replay"]["semantic_transaction_replay_hash"]
    assert e["idempotency_guard_hash"] == \
        o["action_replay_guard"]["action_replay_guard_hash"]


def test_mismatch_blocks_future_readiness(gate):
    o = k.prepare(gate, k.b6_outcome(gate), rollback_replay_mismatch=True)
    assert o["ready_for_future_commit_only"] is False
    assert o["commit_executable_now"] is False


def test_mismatch_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    mismatch = k.prepare(gate, b6, rollback_replay_mismatch=True)
    assert clean["write_intent_decision_hash"] != \
        mismatch["write_intent_decision_hash"]


def test_proof_hash_excludes_itself_and_recomputes(gate):
    e = k.clean_outcome(gate)["rollback_replay_equivalence"]
    recomputed = _core_hash(e, "rollback_replay_equivalence_hash", "signal")
    assert recomputed == e["rollback_replay_equivalence_hash"]


def test_proof_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["rollback_replay_equivalence"][
        "rollback_replay_equivalence_hash"] == \
        o2["rollback_replay_equivalence"]["rollback_replay_equivalence_hash"]


def test_api_rollback_replay_equivalence_endpoint_clean(gate):
    wid, _ = gate.prepared_write_intent()
    e = gate.wi(wid, "/rollback-replay-equivalence").json()[
        "rollback_replay_equivalence"]
    assert e["equivalence_status"] == "EQUIVALENT"
    assert e["mismatch_reasons"] == []


def test_api_mismatch_blocks(gate):
    wid, o = gate.prepared_write_intent(rollback_replay_mismatch=True)
    assert o["dominant_signal"] == "ROLLBACK_REPLAY_EQUIVALENCE_FAILED"
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"

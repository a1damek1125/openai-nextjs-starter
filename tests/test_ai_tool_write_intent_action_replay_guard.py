"""TOOL-B7 v4: Action Replay Guard — detects a proposed action whose hash
matches a prior action (idempotency / semantic-duplicate replay). A detected
duplicate is escalated by the rollback fence, so the overall draft is never
created."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def _replay(gate, b6, **over):
    # Same proposed_action_hash as a prior action -> semantic duplicate.
    return k.prepare(gate, b6, proposed_action_hash="H",
                     prior_action_hashes=["H"], **over)


def test_guard_exists_and_versioned(gate):
    g = k.clean_outcome(gate)["action_replay_guard"]
    assert g["action_replay_guard_id"].startswith("arg-")
    assert g["action_replay_guard_version"]
    assert "prior_action_hashes" in g and "proposed_action_hash" in g


def test_clean_guard_unique_no_duplicate(gate):
    o = k.clean_outcome(gate)
    g = o["action_replay_guard"]
    assert g["semantic_duplicate_detected"] is False
    assert g["replay_status"] == "UNIQUE"
    assert g["signal"] is None
    assert "ACTION_REPLAY_DETECTED" not in o["all_signals"]


def test_duplicate_action_hash_detected(gate):
    g = _replay(gate, k.b6_outcome(gate))["action_replay_guard"]
    assert g["semantic_duplicate_detected"] is True
    assert g["replay_status"] == "REPLAY_DETECTED"


def test_duplicate_action_does_not_reach_escrow_draft(gate):
    # The fence escalates the duplicate to SEMANTIC_ROLLBACK_ATTACK_DETECTED
    # (which dominates). Assert on the guard sub-object + non-terminal status.
    o = _replay(gate, k.b6_outcome(gate))
    assert o["action_replay_guard"]["semantic_duplicate_detected"] is True
    assert o["dominant_signal"] == "SEMANTIC_ROLLBACK_ATTACK_DETECTED"
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_QUARANTINED"


def test_duplicate_blocks_future_readiness(gate):
    o = _replay(gate, k.b6_outcome(gate))
    assert o["ready_for_future_commit_only"] is False
    assert o["commit_executable_now"] is False


def test_idempotency_key_recorded(gate):
    g = _replay(gate, k.b6_outcome(gate),
                idempotency_key="idem-xyz")["action_replay_guard"]
    assert g["idempotency_key"] == "idem-xyz"


def test_replay_prior_payment_action_as_draft_blocks(gate):
    # "replay this prior payment-like action as a draft" — a duplicate action.
    o = _replay(gate, k.b6_outcome(gate))
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["write_intent_decision_status"] != \
        "WRITE_INTENT_DECISION_ALLOW_DRAFT_ESCROW_ONLY"


def test_duplicate_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    dup = _replay(gate, b6)
    assert clean["write_intent_decision_hash"] != \
        dup["write_intent_decision_hash"]


def test_guard_hash_excludes_itself_and_recomputes(gate):
    g = k.clean_outcome(gate)["action_replay_guard"]
    recomputed = _core_hash(g, "action_replay_guard_hash", "signal")
    assert recomputed == g["action_replay_guard_hash"]


def test_guard_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["action_replay_guard"]["action_replay_guard_hash"] == \
        o2["action_replay_guard"]["action_replay_guard_hash"]


def test_api_action_replay_guard_endpoint_clean(gate):
    wid, _ = gate.prepared_write_intent()
    g = gate.wi(wid, "/action-replay-guard").json()["action_replay_guard"]
    assert g["semantic_duplicate_detected"] is False
    assert g["replay_status"] == "UNIQUE"


def test_api_duplicate_quarantines(gate):
    wid, o = gate.prepared_write_intent(proposed_action_hash="H",
                                        prior_action_hashes=["H"])
    assert o["action_replay_guard"]["semantic_duplicate_detected"] is True
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_QUARANTINED"

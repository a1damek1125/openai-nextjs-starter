"""TOOL-B7 v4: Semantic Rollback Fence — fences rollback/restore semantics so a
rollback cannot be weaponised into an action replay or an authority
resurrection. The fence is evidence-only: it never executes a rollback and
never calls anything external."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_fence_exists_and_versioned(gate):
    f = k.clean_outcome(gate)["semantic_rollback_fence"]
    assert f["semantic_rollback_fence_id"].startswith("src-")
    assert f["semantic_rollback_fence_version"]
    assert "semantic_equivalence_hash" in f


def test_clean_fence_fenced_no_risk(gate):
    o = k.clean_outcome(gate)
    f = o["semantic_rollback_fence"]
    assert f["fence_status"] == "FENCED"
    assert f["action_replay_risk"] is False
    assert f["authority_resurrection_risk"] is False
    assert f["signal"] is None


def test_fence_never_executes_or_calls_external(gate):
    # True on the clean path AND under attack inputs.
    for over in ({}, {"proposed_action_hash": "H", "prior_action_hashes": ["H"]},
                 {"token_like_refs": ["x"]}):
        f = k.prepare(gate, k.b6_outcome(gate),
                      **over)["semantic_rollback_fence"]
        assert f["fence_executes_rollback"] is False
        assert f["fence_calls_external"] is False


def test_action_replay_raises_attack_risk(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  proposed_action_hash="H", prior_action_hashes=["H"])
    f = o["semantic_rollback_fence"]
    assert f["action_replay_risk"] is True
    assert f["signal"] == "SEMANTIC_ROLLBACK_ATTACK_DETECTED"
    assert f["fence_status"] == "ATTACK_RISK"
    assert o["dominant_signal"] == "SEMANTIC_ROLLBACK_ATTACK_DETECTED"
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_authority_resurrection_raises_risk(gate):
    o = k.prepare(gate, k.b6_outcome(gate), token_like_refs=["x"])
    f = o["semantic_rollback_fence"]
    assert f["authority_resurrection_risk"] is True
    assert f["fence_status"] == "ATTACK_RISK"


def test_semantic_equivalence_hash_present(gate):
    f = k.clean_outcome(gate)["semantic_rollback_fence"]
    assert f["semantic_equivalence_hash"]
    assert isinstance(f["semantic_equivalence_hash"], str)


def test_attack_blocks_future_readiness(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  proposed_action_hash="H", prior_action_hashes=["H"])
    assert o["ready_for_future_commit_only"] is False
    assert o["commit_executable_now"] is False


def test_fence_failure_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    attack = k.prepare(gate, b6, proposed_action_hash="H",
                       prior_action_hashes=["H"])
    assert clean["write_intent_decision_hash"] != \
        attack["write_intent_decision_hash"]


def test_fence_hash_excludes_itself_and_recomputes(gate):
    f = k.clean_outcome(gate)["semantic_rollback_fence"]
    recomputed = _core_hash(f, "semantic_rollback_fence_hash", "signal")
    assert recomputed == f["semantic_rollback_fence_hash"]


def test_fence_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["semantic_rollback_fence"]["semantic_rollback_fence_hash"] == \
        o2["semantic_rollback_fence"]["semantic_rollback_fence_hash"]


def test_api_semantic_rollback_fence_endpoint_clean(gate):
    wid, _ = gate.prepared_write_intent()
    f = gate.wi(wid, "/semantic-rollback-fence").json()[
        "semantic_rollback_fence"]
    assert f["fence_status"] == "FENCED"
    assert f["fence_executes_rollback"] is False
    assert f["fence_calls_external"] is False


def test_api_action_replay_raises_attack(gate):
    wid, o = gate.prepared_write_intent(proposed_action_hash="H",
                                        prior_action_hashes=["H"])
    assert o["semantic_rollback_fence"]["action_replay_risk"] is True
    assert o["dominant_signal"] == "SEMANTIC_ROLLBACK_ATTACK_DETECTED"

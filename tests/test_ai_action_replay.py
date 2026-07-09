"""TOOL-B4: idempotent replay + replay-conflict detection."""


def test_identical_resubmit_is_replay(gate):
    tool_id, contract = gate.preaction_tool()
    body = gate.clean_proposal_body(tool_id, contract, idempotency_key="k")
    r1 = gate.propose(tool_id, contract, body=dict(body)).json()
    assert r1["is_replay"] is False
    r2 = gate.propose(tool_id, contract, body=dict(body)).json()
    assert r2["is_replay"] is True
    assert r2["replay_verifier"]["replay_result"] == "IDEMPOTENT_REPLAY"


def test_same_key_different_payload_conflict(gate):
    tool_id, contract = gate.preaction_tool()
    gate.propose(tool_id, contract, idempotency_key="k")
    conflict = gate.clean_proposal_body(tool_id, contract, idempotency_key="k",
                                        payload={"query": "different"})
    r = gate.propose(tool_id, contract, body=conflict).json()
    assert r["decision_status"] == "PREACTION_REPLAY_CONFLICT"
    assert r["dominant_signal"] == "REPLAY_CONFLICT"
    assert r["replay_verifier"]["replay_result"] == "CONFLICT"


def test_different_key_is_fresh(gate):
    tool_id, contract = gate.preaction_tool()
    gate.propose(tool_id, contract, idempotency_key="k")
    r = gate.propose(tool_id, contract, idempotency_key="other").json()
    assert r["is_replay"] is False
    assert r["replay_verifier"]["replay_result"] == "FRESH"
    assert r["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"


def test_replay_subread(gate):
    tool_id, contract = gate.preaction_tool()
    body = gate.clean_proposal_body(tool_id, contract, idempotency_key="k")
    gate.propose(tool_id, contract, body=dict(body))
    r2 = gate.propose(tool_id, contract, body=dict(body)).json()
    sub = gate.pa(r2["proposal_id"], "/replay").json()
    assert sub["replay_verifier"]["replay_result"] == "IDEMPOTENT_REPLAY"
    assert sub["replay_verifier"]["prior_proposal_hash"] == \
        sub["replay_verifier"]["current_proposal_hash"]


def test_conflict_subread(gate):
    tool_id, contract = gate.preaction_tool()
    gate.propose(tool_id, contract, idempotency_key="k")
    conflict = gate.clean_proposal_body(tool_id, contract, idempotency_key="k",
                                        payload={"query": "different"})
    r = gate.propose(tool_id, contract, body=conflict).json()
    sub = gate.pa(r["proposal_id"], "/replay").json()
    assert sub["replay_verifier"]["replay_result"] == "CONFLICT"
    assert sub["replay_verifier"]["prior_proposal_hash"] != \
        sub["replay_verifier"]["current_proposal_hash"]

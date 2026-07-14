"""TOOL-B4 pre-action reference monitor: decision determinism / hashing.

Verifies that a decision is a deterministic function of proposal CONTENT plus
the authoritative source snapshot -- independent of instance metadata
(decision_id / deciding actor). Also pins down decision_state_hash binding and
the fail-closed rejection of non-finite JSON numbers. All expected values were
confirmed by running the kernel first.
"""
import pytest

from finalis.ai_employee import tool_guardrails as g
from finalis.ai_employee.tool_contracts import _sha

from tests.conftest import OWNER


# A minimal, authoritative source snapshot that yields a clean ALLOW for the
# default pure-read tool. Held constant so only the varied field moves.
def _head(gate):
    return {"tenant_id": gate.tid, "status": "ADMITTED", "admitted": True,
            "category": "DATA_SEARCH", "side_effect_class": "PURE_READ",
            "risk_class": "TRIVIAL"}


def _proposal(gate, tool_id, contract, proposal_id="pid-fixed", **over):
    raw = gate.clean_proposal_body(tool_id, contract, **over)
    return g.build_action_proposal(
        proposal_id=proposal_id, tenant_id=gate.tid, tool_id=tool_id,
        contract_id=contract["contract_id"], raw=raw, actor_id="a1",
        actor_type="human", created_at="2020-01-01T00:00:00Z")


def _evaluate(gate, contract, proposal, **over):
    kw = dict(
        proposal=proposal, head=_head(gate),
        quality_report={"quality_status": "QUALITY_PASS"}, contract=contract,
        broker_readiness=None, circuit_breaker=None, prior_decision=None,
        role_authority=["READ"], policy=None, usage=None, decision_id="dec-1",
        tenant_id=gate.tid, actor_id="a1", actor_type="human",
        created_at="2020-01-01T00:00:00Z", allowed_purposes=["CASE_TRIAGE"])
    kw.update(over)
    return g.evaluate_proposal(**kw)


def test_two_evaluations_same_inputs_identical_decision_hash(gate):
    tool_id, contract = gate.preaction_tool()
    prop = _proposal(gate, tool_id, contract)
    d1 = _evaluate(gate, contract, prop)
    d2 = _evaluate(gate, contract, prop)
    assert d1["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"
    assert d1["decision_hash"] == d2["decision_hash"]


def test_decision_hash_excludes_decision_id_and_deciding_actor(gate):
    tool_id, contract = gate.preaction_tool()
    prop = _proposal(gate, tool_id, contract)
    d1 = _evaluate(gate, contract, prop, decision_id="D1", actor_id="alice")
    d2 = _evaluate(gate, contract, prop, decision_id="D2", actor_id="bob")
    # Different decision_id + deciding actor_id -> SAME content decision_hash.
    assert d1["decision_id"] != d2["decision_id"]
    assert d1["decision_hash"] == d2["decision_hash"]
    # ...but decision_state_hash BINDS the decision_id, so it differs.
    assert d1["decision_state_hash"] != d2["decision_state_hash"]


def test_decision_state_hash_binds_status_and_proposal_hash(gate):
    tool_id, contract = gate.preaction_tool()
    prop = _proposal(gate, tool_id, contract)
    d = _evaluate(gate, contract, prop, decision_id="D1")
    # The state hash is exactly sha(decision_id, decision_hash, status,
    # dominant_signal, proposal_hash, epoch).
    recomputed = _sha({
        "decision_id": "D1", "decision_hash": d["decision_hash"],
        "decision_status": d["decision_status"],
        "dominant_signal": d["dominant_signal"],
        "proposal_hash": prop["proposal_hash"],
        "source_freshness_epoch": d["source_freshness_epoch"]})
    assert d["decision_state_hash"] == recomputed
    # A different proposal (different status + proposal_hash) -> different state.
    bad = _proposal(gate, tool_id, contract, intent="not-a-purpose")
    d_bad = _evaluate(gate, contract, bad, decision_id="D1")
    assert d_bad["decision_status"] == "PREACTION_DENIED"
    assert d_bad["decision_state_hash"] != d["decision_state_hash"]


def test_decision_hash_changes_with_proposal_content(gate):
    tool_id, contract = gate.preaction_tool()
    good = _evaluate(gate, contract, _proposal(gate, tool_id, contract))
    bad = _evaluate(gate, contract,
                    _proposal(gate, tool_id, contract, intent="wrong"))
    assert good["decision_hash"] != bad["decision_hash"]


def test_post_proposal_hash_is_content_deterministic(gate):
    tool_id, contract = gate.preaction_tool()
    # Two independent submissions (empty idempotency key -> neither is a replay)
    # of byte-identical content produce the SAME content-bound proposal_hash and
    # the SAME content-determined decision outcome.
    a = gate.decide(tool_id, contract, idempotency_key="")
    b = gate.decide(tool_id, contract, idempotency_key="")
    assert a["is_replay"] is False and b["is_replay"] is False
    assert a["proposal_hash"] == b["proposal_hash"]
    assert a["decision_status"] == b["decision_status"]
    assert a["dominant_signal"] == b["dominant_signal"]


def test_post_same_key_identical_content_is_idempotent_replay(gate):
    tool_id, contract = gate.preaction_tool()
    a = gate.decide(tool_id, contract, idempotency_key="dup")
    b = gate.decide(tool_id, contract, idempotency_key="dup")
    # Same key + identical content -> benign idempotent replay, same proposal.
    assert a["is_replay"] is False and b["is_replay"] is True
    assert a["proposal_hash"] == b["proposal_hash"]
    assert b["dominant_signal"] != "REPLAY_CONFLICT"


def test_canonical_json_rejects_non_finite_numbers(gate):
    tool_id, contract = gate.preaction_tool()
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            g.build_action_proposal(
                proposal_id="x", tenant_id=gate.tid, tool_id=tool_id,
                contract_id=contract["contract_id"],
                raw={"payload": {"query": bad}}, actor_id="a1",
                actor_type="human", created_at="2020-01-01T00:00:00Z")

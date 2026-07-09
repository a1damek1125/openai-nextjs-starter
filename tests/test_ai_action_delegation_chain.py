"""TOOL-B4 direct-kernel tests for the delegation chain check. Each link must
stay in-tenant, be complete and unexpired, form an unbroken grantor->grantee
sequence, and terminate at the proposing actor. Nothing executes."""
from finalis.ai_employee import tool_guardrails as g

ACTOR = "a1"


def _real(gate):
    tool_id, contract = gate.preaction_tool()
    head = gate.app.state.tool_store.payload(tool_id, tenant_id=gate.tid)
    quality = gate.app.state.quality_store.latest(tool_id, tenant_id=gate.tid)
    projs = gate.app.state.contract_store.projections_for(
        contract["contract_id"], tenant_id=gate.tid)
    cert = projs[-1].get("broker_readiness_certificate") if projs else None
    return tool_id, contract, head, quality, cert


def _prop(gate, tool_id, contract, **over):
    raw = gate.clean_proposal_body(tool_id, contract, **over)
    return g.build_action_proposal(
        proposal_id="p1", tenant_id=gate.tid, tool_id=tool_id,
        contract_id=contract["contract_id"], raw=raw, actor_id=ACTOR,
        actor_type="human", created_at="t")


def _check(gate, prop):
    return g.build_delegation_chain_check(
        proposal=prop, tenant_id=gate.tid, actor_id=ACTOR)


def test_empty_chain_valid(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract)
    chk = _check(gate, p)
    assert chk["delegation_valid"] is True
    assert chk["signal"] is None
    assert chk["chain_length"] == 0


def test_single_valid_link_terminating_at_actor(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract, delegation_chain=[
        {"grantor_id": "boss", "grantee_id": ACTOR}])
    chk = _check(gate, p)
    assert chk["delegation_valid"] is True
    assert chk["delegation_problems"] == []


def test_broken_link(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract, delegation_chain=[
        {"grantor_id": "boss", "grantee_id": "mid"},
        {"grantor_id": "other", "grantee_id": ACTOR}])
    chk = _check(gate, p)
    assert chk["delegation_valid"] is False
    assert chk["signal"] == "DELEGATION_CHAIN_INVALID"
    assert any("BROKEN" in prob for prob in chk["delegation_problems"])


def test_cross_tenant_link(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract, delegation_chain=[
        {"grantor_id": "boss", "grantee_id": ACTOR, "tenant_id": "other-t"}])
    chk = _check(gate, p)
    assert chk["delegation_valid"] is False
    assert any("CROSS_TENANT" in prob for prob in chk["delegation_problems"])


def test_expired_link(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract, logical_clock=5, delegation_chain=[
        {"grantor_id": "boss", "grantee_id": ACTOR, "expires_clock": 2}])
    chk = _check(gate, p)
    assert chk["delegation_valid"] is False
    assert any("EXPIRED" in prob for prob in chk["delegation_problems"])


def test_terminus_not_actor_and_incomplete(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p_term = _prop(gate, tool_id, contract, delegation_chain=[
        {"grantor_id": "boss", "grantee_id": "someoneelse"}])
    chk = _check(gate, p_term)
    assert "TERMINUS:NOT_ACTOR" in chk["delegation_problems"]

    p_inc = _prop(gate, tool_id, contract, delegation_chain=[
        {"grantor_id": "boss"}])
    chk2 = _check(gate, p_inc)
    assert any("INCOMPLETE" in prob for prob in chk2["delegation_problems"])


def test_forged_chain_via_evaluate_denied(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract, delegation_chain=[
        {"grantor_id": "boss", "grantee_id": "mid"},
        {"grantor_id": "other", "grantee_id": ACTOR}])
    d = g.evaluate_proposal(
        proposal=p, head=head, quality_report=quality, contract=contract,
        broker_readiness=cert, circuit_breaker=None, prior_decision=None,
        role_authority=["READ"], policy=None, usage=None, decision_id="d1",
        tenant_id=gate.tid, actor_id=ACTOR, actor_type="human", created_at="t")
    assert d["decision_status"] == "PREACTION_DENIED"
    assert d["dominant_signal"] == "DELEGATION_CHAIN_INVALID"

"""TOOL-B4: the attempt detector catches execution / provider / token abuse.

A proposal is only ever a request for a DECISION. Any attempt to make the
monitor execute, call a provider, or pass a bearer token is caught. We assert on
the sub-report booleans and on membership in all_signals (higher-ranked signals
such as BYPASS_PATTERN_DETECTED may dominate the final status).
"""
from finalis.ai_employee import tool_guardrails as g


def _proposal(gate, tool_id, contract, **over):
    raw = gate.clean_proposal_body(tool_id, contract, **over)
    return g.build_action_proposal(
        proposal_id="p1", tenant_id=gate.tid, tool_id=tool_id,
        contract_id=contract["contract_id"], raw=raw, actor_id="a1",
        actor_type="human", created_at="t")


def _inputs(gate, tool_id, contract):
    head = gate.app.state.tool_store.payload(tool_id, tenant_id=gate.tid)
    quality = gate.app.state.quality_store.latest(tool_id, tenant_id=gate.tid)
    projs = gate.app.state.contract_store.projections_for(
        contract["contract_id"], tenant_id=gate.tid)
    cert = projs[-1].get("broker_readiness_certificate") if projs else None
    return head, quality, cert


def _evaluate(gate, proposal, tool_id, contract):
    head, quality, cert = _inputs(gate, tool_id, contract)
    return g.evaluate_proposal(
        proposal=proposal, head=head, quality_report=quality, contract=contract,
        broker_readiness=cert, circuit_breaker=None, prior_decision=None,
        role_authority=["READ"], policy=None, usage=None, decision_id="d1",
        tenant_id=gate.tid, actor_id="a1", actor_type="human", created_at="t",
        allowed_purposes=["CASE_TRIAGE"])


def test_execution_attempt_detected(gate):
    tool_id, contract = gate.preaction_tool()
    prop = _proposal(gate, tool_id, contract, payload={"query": "execute now"})
    det = g.build_attempt_detector(proposal=prop)
    assert det["execution_attempt_detected"] is True
    assert "EXECUTION_ATTEMPT" in det["signals"]
    d = _evaluate(gate, prop, tool_id, contract)
    assert "EXECUTION_ATTEMPT" in d["all_signals"]
    assert d["decision_status"].startswith("PREACTION_")


def test_provider_call_attempt_detected(gate):
    tool_id, contract = gate.preaction_tool()
    prop = _proposal(gate, tool_id, contract,
                     payload={"query": "https://evil"})
    det = g.build_attempt_detector(proposal=prop)
    assert det["provider_call_attempt_detected"] is True
    assert "PROVIDER_CALL_ATTEMPT" in det["signals"]
    d = _evaluate(gate, prop, tool_id, contract)
    assert "PROVIDER_CALL_ATTEMPT" in d["all_signals"]


def test_token_passthrough_detected(gate):
    tool_id, contract = gate.preaction_tool()
    # bearer smuggled as a payload key.
    prop = _proposal(gate, tool_id, contract, payload={"bearer": "xyz"})
    det = g.build_attempt_detector(proposal=prop)
    assert det["token_passthrough_detected"] is True
    assert "TOKEN_PASSTHROUGH" in det["signals"]
    d = _evaluate(gate, prop, tool_id, contract)
    assert "TOKEN_PASSTHROUGH" in d["all_signals"]


def test_clean_payload_detects_nothing_and_attempts_subread(gate):
    tool_id, contract = gate.preaction_tool()
    prop = _proposal(gate, tool_id, contract)
    det = g.build_attempt_detector(proposal=prop)
    assert det["execution_attempt_detected"] is False
    assert det["provider_call_attempt_detected"] is False
    assert det["token_passthrough_detected"] is False
    assert det["signals"] == []
    # /attempts sub-read reflects a clean detector for the clean proposal.
    d = gate.propose(tool_id, contract).json()
    sub = gate.pa(d["proposal_id"], "/attempts").json()
    ad = sub["attempt_detector"]
    assert ad["execution_attempt_detected"] is False
    assert ad["provider_call_attempt_detected"] is False
    assert ad["token_passthrough_detected"] is False

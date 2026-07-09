"""TOOL-B4 — bypass attack simulator tests.

A battery of deterministic bypass patterns, each modelling a concrete way an
adversarial planner could try to launder a forbidden action past the guardrails
(intent laundering, scope smuggling, token smuggling, capability rug-pull,
consent override, ...). Any detected pattern raises BYPASS_PATTERN_DETECTED,
which may or may not be the dominant signal depending on what else fired.
"""
from finalis.ai_employee import tool_guardrails as g

_CREATED = "2026-01-01T00:00:00Z"


def _mkprop(gate, tool_id, contract, **over):
    body = gate.clean_proposal_body(tool_id, contract, **over)
    return g.build_action_proposal(
        proposal_id="p1", tenant_id=gate.tid, tool_id=tool_id,
        contract_id=contract["contract_id"], raw=body, actor_id="u1",
        actor_type="human", created_at=_CREATED)


def _ev(gate, tool_id, contract, proposal, **over):
    head = gate.app.state.tool_store.payload(tool_id, tenant_id=gate.tid)
    quality = gate.app.state.quality_store.latest(tool_id, tenant_id=gate.tid)
    kw = dict(proposal=proposal, head=head, quality_report=quality,
              contract=contract, broker_readiness=None, circuit_breaker=None,
              prior_decision=None, role_authority=["READ"], policy=None,
              usage=None, decision_id="d1", tenant_id=gate.tid, actor_id="u1",
              actor_type="human", created_at=_CREATED,
              allowed_purposes=["CASE_TRIAGE"])
    kw.update(over)
    return g.evaluate_proposal(**kw)


def test_intent_laundering_detected(gate):
    tool_id, contract = gate.preaction_tool()
    d = _ev(gate, tool_id, contract,
            _mkprop(gate, tool_id, contract, intent="NOT_A_PURPOSE"))
    bs = d["bypass_simulator"]
    assert "INTENT_LAUNDERING" in bs["detected_patterns"]
    assert bs["bypass_detected"] is True
    assert "BYPASS_PATTERN_DETECTED" in d["all_signals"]
    # INTENT_MISMATCH outranks the bypass signal in the dominance ladder.
    assert d["dominant_signal"] == "INTENT_MISMATCH"


def test_scope_smuggling_detected(gate):
    tool_id, contract = gate.preaction_tool()
    d = _ev(gate, tool_id, contract,
            _mkprop(gate, tool_id, contract,
                    requested_scope={"record_id": "zzz"}))
    bs = d["bypass_simulator"]
    assert "SCOPE_SMUGGLING" in bs["detected_patterns"]
    assert "BYPASS_PATTERN_DETECTED" in d["all_signals"]
    assert "PAYLOAD_SCOPE_MISMATCH" in d["all_signals"]


def test_token_smuggling_detected(gate):
    tool_id, contract = gate.preaction_tool()
    # 'query' is a schema-valid key; the bearer marker rides in its VALUE so it
    # is caught as a token passthrough / smuggling rather than a schema mismatch.
    d = _ev(gate, tool_id, contract,
            _mkprop(gate, tool_id, contract,
                    payload={"query": "bearer sk-secret"}))
    bs = d["bypass_simulator"]
    assert "TOKEN_SMUGGLING" in bs["detected_patterns"]
    assert d["attempt_detector"]["token_passthrough_detected"] is True
    assert "BYPASS_PATTERN_DETECTED" in d["all_signals"]
    assert "TOKEN_PASSTHROUGH" in d["all_signals"]


def test_capability_rug_pull_detected(gate):
    tool_id, contract = gate.preaction_tool()
    d = _ev(gate, tool_id, contract,
            _mkprop(gate, tool_id, contract, baseline_contract_hash="WRONG"))
    bs = d["bypass_simulator"]
    assert "CAPABILITY_RUG_PULL" in bs["detected_patterns"]
    assert "BYPASS_PATTERN_DETECTED" in d["all_signals"]
    assert "CAPABILITY_DRIFT_DETECTED" in d["all_signals"]


def test_consent_override_is_dominant_bypass(gate):
    tool_id, contract = gate.preaction_tool()
    # A consent-override flag on an otherwise-clean pure-read proposal produces
    # ONLY the bypass signal (no higher signal fires), so BYPASS is dominant.
    d = _ev(gate, tool_id, contract,
            _mkprop(gate, tool_id, contract, consent_ref={"override": True}))
    bs = d["bypass_simulator"]
    assert "CONSENT_OVERRIDE" in bs["detected_patterns"]
    assert d["all_signals"] == ["BYPASS_PATTERN_DETECTED"]
    assert d["dominant_signal"] == "BYPASS_PATTERN_DETECTED"
    assert d["decision_status"] == "PREACTION_BYPASS_PATTERN_DETECTED"
    assert d["executes_nothing"] is True


def test_clean_proposal_no_bypass_and_subread(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.decide(tool_id, contract)
    assert d["bypass_simulator"]["bypass_detected"] is False
    assert d["bypass_simulator"]["detected_patterns"] == []
    assert d["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"
    r = gate.pa(d["proposal_id"], path="/bypass")
    assert r.status_code == 200
    body = r.json()
    assert body["proposal_id"] == d["proposal_id"]
    assert body["bypass_simulator"]["bypass_detected"] is False

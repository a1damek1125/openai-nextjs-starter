"""TOOL-B4 — capability drift sentinel tests.

The sentinel detects a silent capability change (rug-pull) between the moment a
proposal was formed against a baseline contract and the moment it is evaluated.
A supplied baseline that no longer matches the authoritative contract/ABI hash
is drift -> CAPABILITY_DRIFT_DETECTED -> PREACTION_CAPABILITY_DRIFT_DETECTED.
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


def test_no_baseline_supplied_no_drift(gate):
    tool_id, contract = gate.preaction_tool()
    s = g.build_capability_drift_sentinel(
        proposal=_mkprop(gate, tool_id, contract), contract=contract)
    assert s["drift_detected"] is False
    assert s["contract_hash_drift"] is False
    assert s["abi_hash_drift"] is False
    assert s["signal"] is None


def test_matching_contract_hash_no_drift(gate):
    tool_id, contract = gate.preaction_tool()
    s = g.build_capability_drift_sentinel(
        proposal=_mkprop(gate, tool_id, contract,
                         baseline_contract_hash=contract["contract_hash"]),
        contract=contract)
    assert s["drift_detected"] is False
    assert s["contract_hash_drift"] is False


def test_contract_hash_drift_detected(gate):
    tool_id, contract = gate.preaction_tool()
    prop = _mkprop(gate, tool_id, contract, baseline_contract_hash="WRONG")
    s = g.build_capability_drift_sentinel(proposal=prop, contract=contract)
    assert s["drift_detected"] is True
    assert s["contract_hash_drift"] is True
    assert s["signal"] == "CAPABILITY_DRIFT_DETECTED"
    d = _ev(gate, tool_id, contract, prop)
    assert d["dominant_signal"] == "CAPABILITY_DRIFT_DETECTED"
    assert d["decision_status"] == "PREACTION_CAPABILITY_DRIFT_DETECTED"


def test_abi_hash_drift_detected(gate):
    tool_id, contract = gate.preaction_tool()
    s = g.build_capability_drift_sentinel(
        proposal=_mkprop(gate, tool_id, contract,
                         baseline_abi_hash="WRONG_ABI"),
        contract=contract)
    assert s["drift_detected"] is True
    assert s["abi_hash_drift"] is True
    assert s["contract_hash_drift"] is False
    assert s["signal"] == "CAPABILITY_DRIFT_DETECTED"


def test_submit_wrong_baseline_yields_drift_decision(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.decide(tool_id, contract, baseline_contract_hash="WRONG")
    assert d["decision_status"] == "PREACTION_CAPABILITY_DRIFT_DETECTED"
    assert d["dominant_signal"] == "CAPABILITY_DRIFT_DETECTED"
    assert d["capability_drift_sentinel"]["drift_detected"] is True
    assert d["executes_nothing"] is True


def test_submit_real_contract_hash_allowed(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.decide(tool_id, contract,
                    baseline_contract_hash=contract["contract_hash"])
    assert d["capability_drift_sentinel"]["drift_detected"] is False
    assert d["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"

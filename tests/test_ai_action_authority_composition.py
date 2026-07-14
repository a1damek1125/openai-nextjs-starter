"""TOOL-B4 direct-kernel tests for authority composition and the composed
frontier (role_authority INTERSECT contract_frontier). Uses a REAL PURE_READ
contract from gate.preaction_tool; nothing executes."""
from finalis.ai_employee import tool_guardrails as g


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
        contract_id=contract["contract_id"], raw=raw, actor_id="a1",
        actor_type="human", created_at="t")


def _eval(gate, prop, head, quality, contract, cert, **over):
    kw = dict(proposal=prop, head=head, quality_report=quality,
              contract=contract, broker_readiness=cert, circuit_breaker=None,
              prior_decision=None, role_authority=["READ"], policy=None,
              usage=None, decision_id="d1", tenant_id=gate.tid, actor_id="a1",
              actor_type="human", created_at="t", allowed_purposes=None)
    kw.update(over)
    return g.evaluate_proposal(**kw)


def test_pure_read_contract_frontier_is_read(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract)
    comp = g.build_authority_composition(
        proposal=p, head=head, contract=contract, broker_readiness=cert,
        actor_type="human", role_authority=["READ"], policy=None, usage=None)
    assert comp["contract_frontier"] == ["READ"]
    assert comp["required_authority"] == ["READ"]
    assert comp["authority_expansion"] == []


def test_read_role_read_required_allows(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract)
    d = _eval(gate, p, head, quality, contract, cert, role_authority=["READ"])
    assert d["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"
    assert d["dominant_signal"] == "ALLOWED_FOR_FUTURE_BROKER_ONLY"


def test_composed_frontier_is_role_intersect_contract(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract)
    # Owner holds every dimension, but a PURE_READ contract narrows the frontier
    # to READ: the composition is an intersection, never a widening.
    comp = g.build_authority_composition(
        proposal=p, head=head, contract=contract, broker_readiness=cert,
        actor_type="human", role_authority=list(g.AUTHORITY_DIMENSIONS),
        policy=None, usage=None)
    assert comp["composed_frontier"] == ["READ"]


def test_requested_payment_beyond_frontier_denied(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract, requested_authority=["PAYMENT"])
    comp = g.build_authority_composition(
        proposal=p, head=head, contract=contract, broker_readiness=cert,
        actor_type="human", role_authority=["READ"], policy=None, usage=None)
    assert "PAYMENT" in comp["authority_expansion"]
    assert comp["expansion_signal"] == "AUTHORITY_EXPANSION"
    d = _eval(gate, p, head, quality, contract, cert, role_authority=["READ"])
    assert d["decision_status"] == "PREACTION_DENIED"
    assert d["dominant_signal"] == "AUTHORITY_EXPANSION"


def test_owner_payment_still_denied_by_pure_read_contract(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    # Even an owner who holds PAYMENT authority is expanded past a pure-read
    # contract frontier: the contract, not the role, is the binding limit.
    p = _prop(gate, tool_id, contract, requested_authority=["PAYMENT"])
    d = _eval(gate, p, head, quality, contract, cert,
              role_authority=list(g.AUTHORITY_DIMENSIONS))
    assert d["decision_status"] == "PREACTION_DENIED"
    assert d["dominant_signal"] == "AUTHORITY_EXPANSION"


def test_authority_budget_zero_exceeded(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    # Keep required authority within the frontier (READ) so expansion cannot
    # dominate; a zero budget then surfaces AUTHORITY_BUDGET_EXCEEDED alone.
    p = _prop(gate, tool_id, contract)
    comp = g.build_authority_composition(
        proposal=p, head=head, contract=contract, broker_readiness=cert,
        actor_type="human", role_authority=["READ"],
        policy={"authority_budget": 0}, usage=None)
    assert comp["authority_over_budget"] is True
    assert comp["budget_signal"] == "AUTHORITY_BUDGET_EXCEEDED"
    d = _eval(gate, p, head, quality, contract, cert, role_authority=["READ"],
              policy={"authority_budget": 0})
    assert d["decision_status"] == "PREACTION_AUTHORITY_BUDGET_EXCEEDED"
    assert d["dominant_signal"] == "AUTHORITY_BUDGET_EXCEEDED"


def test_authority_vector_covers_all_dimensions_as_bools(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract)
    comp = g.build_authority_composition(
        proposal=p, head=head, contract=contract, broker_readiness=cert,
        actor_type="human", role_authority=["READ"], policy=None, usage=None)
    vec = comp["authority_vector"]
    assert set(vec.keys()) == set(g.AUTHORITY_DIMENSIONS)
    assert all(isinstance(v, bool) for v in vec.values())
    assert vec["READ"] is True
    assert vec["PAYMENT"] is False


def test_blocked_contract_yields_empty_frontier_and_expansion(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract)
    # A missing/un-admitted contract grants no authority: empty frontier means
    # even the implicit READ requirement is an expansion (fail-closed).
    comp = g.build_authority_composition(
        proposal=p, head=head, contract=None, broker_readiness=cert,
        actor_type="human", role_authority=["READ"], policy=None, usage=None)
    assert comp["contract_frontier"] == []
    assert comp["composed_frontier"] == []
    assert comp["authority_expansion"] == ["READ"]
    assert all(v is False for v in comp["authority_vector"].values())

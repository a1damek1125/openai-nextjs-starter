"""TOOL-B4 tests for the path-risk budget. The per-action path-risk weight
scales with the contract risk class (TRIVIAL=1 .. PROHIBITED=64); an unknown
risk class fails closed to the maximum weight. Nothing executes."""
from finalis.ai_employee import tool_guardrails as g
from tests.conftest import OWNER


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


def test_trivial_contract_weight_is_one(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract)
    prb = g.build_path_risk_budget(
        proposal=p, head=head, contract=contract, policy=None, usage=None)
    assert prb["risk_class"] == "TRIVIAL"
    assert prb["path_risk_weight"] == 1
    assert prb["path_risk_over_budget"] is False
    assert prb["signal"] is None


def test_weight_scales_with_risk_class(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract)
    weights = {}
    for rc in ("TRIVIAL", "LOW", "MEDIUM", "HIGH", "CRITICAL", "PROHIBITED"):
        prb = g.build_path_risk_budget(
            proposal=p, head=None, contract={"contract_risk_class": rc},
            policy=None, usage=None)
        weights[rc] = prb["path_risk_weight"]
    assert weights == {"TRIVIAL": 1, "LOW": 2, "MEDIUM": 4, "HIGH": 8,
                       "CRITICAL": 16, "PROHIBITED": 64}
    # Higher risk class strictly consumes more of the budget.
    assert weights["PROHIBITED"] > weights["HIGH"] > weights["TRIVIAL"]


def test_unknown_risk_class_fails_closed_to_max(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract)
    prb = g.build_path_risk_budget(
        proposal=p, head=None, contract={"contract_risk_class": "WACKY"},
        policy=None, usage=None)
    assert prb["path_risk_weight"] == max(g._PATH_RISK_WEIGHT.values()) == 64


def test_budget_zero_exceeded_kernel(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract)
    prb = g.build_path_risk_budget(
        proposal=p, head=head, contract=contract,
        policy={"path_risk_budget": 0}, usage=None)
    assert prb["path_risk_over_budget"] is True
    assert prb["signal"] == "PATH_RISK_BUDGET_EXCEEDED"


def test_budget_zero_evaluate_status(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract)
    d = _eval(gate, p, head, quality, contract, cert,
              policy={"path_risk_budget": 0})
    assert d["decision_status"] == "PREACTION_PATH_RISK_BUDGET_EXCEEDED"
    assert d["dominant_signal"] == "PATH_RISK_BUDGET_EXCEEDED"


def test_usage_spent_near_budget_goes_over(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract)
    # weight is 1 (TRIVIAL); with 1 already spent against a budget of 1 the
    # next unit tips over: (1 + 1) > 1.
    prb = g.build_path_risk_budget(
        proposal=p, head=head, contract=contract,
        policy={"path_risk_budget": 1}, usage={"path_risk_spent": 1})
    assert prb["path_risk_over_budget"] is True
    assert prb["signal"] == "PATH_RISK_BUDGET_EXCEEDED"


def test_budget_zero_via_post_endpoint(gate):
    tool_id, contract = gate.preaction_tool()
    resp = gate.propose(tool_id, contract, actor=OWNER,
                        policy={"path_risk_budget": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision_status"] == "PREACTION_PATH_RISK_BUDGET_EXCEEDED"
    assert body["dominant_signal"] == "PATH_RISK_BUDGET_EXCEEDED"
    assert body["executes_nothing"] is True

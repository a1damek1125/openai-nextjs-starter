"""TOOL-B4 — counterfactual denial twin tests.

A denial-biased twin of the evaluation. For each safety guard it confirms that
*failing* that guard flips a would-be allow into an adverse decision (proving
the allow is contingent on the guard). It then flags a would-be allow that
rests on OMISSION on a consequential (non-pure-read) action as not robust,
requiring review (COUNTERFACTUAL_REVIEW_REQUIRED).
"""
import copy

from finalis.ai_employee import tool_guardrails as g

_CREATED = "2026-01-01T00:00:00Z"
_CLEAN_BASE = ["ALLOWED_FOR_FUTURE_BROKER_ONLY"]


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


def test_pure_read_would_be_positive_is_robust(gate):
    tool_id, contract = gate.preaction_tool()
    # A pure-read allow declares no effects/authority, but a pure-read action is
    # not consequential, so omission is not a defect -> robust allow.
    twin = g.build_counterfactual_twin(
        base_signals=_CLEAN_BASE, proposal=_mkprop(gate, tool_id, contract),
        contract=contract, would_be_positive=True)
    assert twin["robust_allow"] is True
    assert twin["signal"] is None
    assert twin["counterfactual_concerns"] == []


def test_side_effecting_undeclared_effects_needs_review(gate):
    tool_id, contract = gate.preaction_tool()
    # Mutate the contract into a side-effecting one; the clean proposal declares
    # no effects, so the allow rests on omission and is not robust.
    se_contract = copy.deepcopy(contract)
    se_contract["contract_side_effect_class"] = "INTERNAL_WRITE"
    twin = g.build_counterfactual_twin(
        base_signals=_CLEAN_BASE, proposal=_mkprop(gate, tool_id, contract),
        contract=se_contract, would_be_positive=True)
    assert "UNDECLARED_EFFECTS" in twin["counterfactual_concerns"]
    assert twin["signal"] == "COUNTERFACTUAL_REVIEW_REQUIRED"
    assert twin["robust_allow"] is False


def test_every_twin_entry_flips_to_adverse(gate):
    tool_id, contract = gate.preaction_tool()
    twin = g.build_counterfactual_twin(
        base_signals=_CLEAN_BASE, proposal=_mkprop(gate, tool_id, contract),
        contract=contract, would_be_positive=True)
    # A failing guard must flip the clean positive into an adverse decision.
    assert twin["twins"]
    for t in twin["twins"]:
        assert t["twin_flips_to_adverse"] is True, t["guard"]


def test_would_be_negative_no_review_signal(gate):
    tool_id, contract = gate.preaction_tool()
    # When the decision is already not a would-be allow, the twin adds no review.
    twin = g.build_counterfactual_twin(
        base_signals=["INTENT_MISMATCH"],
        proposal=_mkprop(gate, tool_id, contract, intent="WRONG"),
        contract=contract, would_be_positive=False)
    assert twin["signal"] is None
    assert twin["robust_allow"] is False
    assert twin["counterfactual_concerns"] == []


def test_clean_pure_read_evaluate_stays_allowed(gate):
    tool_id, contract = gate.preaction_tool()
    d = _ev(gate, tool_id, contract, _mkprop(gate, tool_id, contract))
    # The counterfactual twin must NOT force a clean pure-read allow into review.
    assert d["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"
    assert d["counterfactual_twin"]["robust_allow"] is True
    assert d["counterfactual_twin"]["signal"] is None
    assert "COUNTERFACTUAL_REVIEW_REQUIRED" not in d["all_signals"]


def test_counterfactual_subread_endpoint(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.decide(tool_id, contract)
    pid = d["proposal_id"]
    r = gate.pa(pid, path="/counterfactual")
    assert r.status_code == 200
    body = r.json()
    assert body["proposal_id"] == pid
    twin = body["counterfactual_twin"]
    assert twin["robust_allow"] is True
    assert all(t["twin_flips_to_adverse"] for t in twin["twins"])

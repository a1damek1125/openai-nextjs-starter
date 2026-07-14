"""TOOL-B4 direct-kernel tests for the nondelegable guard. AI actors can never
self-authorize a nondelegable decision; a human may hold it (subject to
approval/consent elsewhere). Nothing executes."""
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


# A minimal nondelegable contract (PAYMENT category / PAYMENT_MOVEMENT effect).
ND_CONTRACT = {"contract_capability_category": "PAYMENT",
               "contract_side_effect_class": "PAYMENT_MOVEMENT"}


def test_ai_actor_nondelegable_category_blocked(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract)
    guard = g.build_nondelegable_guard(
        proposal=p, contract=ND_CONTRACT, head=None, actor_type="ai_employee")
    assert guard["is_nondelegable"] is True
    assert guard["blocked_for_ai_actor"] is True
    assert guard["signal"] == "NONDELEGABLE_DECISION"
    assert "CATEGORY:PAYMENT" in guard["nondelegable_reasons"]
    assert "SIDE_EFFECT:PAYMENT_MOVEMENT" in guard["nondelegable_reasons"]


def test_human_actor_may_hold_nondelegable(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract)
    guard = g.build_nondelegable_guard(
        proposal=p, contract=ND_CONTRACT, head=None, actor_type="human")
    assert guard["is_nondelegable"] is True
    assert guard["blocked_for_ai_actor"] is False
    assert guard["signal"] is None


def test_verb_markers_trigger_nondelegable(gate):
    for verb in ("delete", "pay", "send", "export", "grant"):
        reasons = g.nondelegable_reasons(
            category="DATA_SEARCH", side_effect_class="PURE_READ",
            declared_effects=[], action_path=verb, requested_scope={})
        assert reasons == [f"VERB:{verb}"], (verb, reasons)


def test_scope_markers_trigger_nondelegable(gate):
    for marker, scope in (("cross_tenant", {"cross_tenant": "x"}),
                          ("secret", {"secret": "y"})):
        reasons = g.nondelegable_reasons(
            category="DATA_SEARCH", side_effect_class="PURE_READ",
            declared_effects=[], action_path="search", requested_scope=scope)
        assert reasons == [f"SCOPE:{marker}"], (marker, reasons)


def test_declared_effects_trigger_nondelegable(gate):
    reasons = g.nondelegable_reasons(
        category="DATA_SEARCH", side_effect_class="PURE_READ",
        declared_effects=["PAYMENT_MOVEMENT"], action_path="search",
        requested_scope={})
    assert reasons == ["EFFECT:NONDELEGABLE"]


def test_evaluate_ai_actor_nondelegable_needs_human_approval(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    # 'delete' is a nondelegable verb marker on an otherwise-clean pure-read
    # action; an AI actor is routed to human approval, never self-authorized.
    p = _prop(gate, tool_id, contract, action_path="delete")
    d = _eval(gate, p, head, quality, contract, cert, actor_type="ai_employee")
    assert d["decision_status"] == "PREACTION_NEEDS_HUMAN_APPROVAL"
    assert d["dominant_signal"] == "NONDELEGABLE_DECISION"
    assert d["nondelegable_guard"]["blocked_for_ai_actor"] is True


def test_evaluate_human_not_forced_by_nondelegable_alone(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    # Same nondelegable verb, but a human actor is NOT forced to human approval
    # by nondelegable alone (this low-risk contract needs no approval/consent).
    p = _prop(gate, tool_id, contract, action_path="delete")
    d = _eval(gate, p, head, quality, contract, cert, actor_type="human")
    assert d["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"
    assert d["nondelegable_guard"]["is_nondelegable"] is True
    assert d["nondelegable_guard"]["blocked_for_ai_actor"] is False
    assert "NONDELEGABLE_DECISION" not in d["all_signals"]


def test_clean_read_is_not_nondelegable_for_ai(gate):
    tool_id, contract, head, quality, cert = _real(gate)
    p = _prop(gate, tool_id, contract)
    guard = g.build_nondelegable_guard(
        proposal=p, contract=contract, head=head, actor_type="ai_employee")
    assert guard["is_nondelegable"] is False
    assert guard["blocked_for_ai_actor"] is False
    assert guard["signal"] is None

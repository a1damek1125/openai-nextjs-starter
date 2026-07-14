"""TOOL-B4 — temporal policy automaton tests.

A deterministic finite automaton over the decision history for an idempotency
key. It enforces monotone logical time (no clock regression) and forbids
resurrecting a terminally-denied proposal without a fresh source epoch.
"""
from finalis.ai_employee import tool_guardrails as g

_CREATED = "2026-01-01T00:00:00Z"
_TERMINAL = ["PREACTION_REVOKED", "PREACTION_BLOCKED", "PREACTION_QUARANTINED",
             "PREACTION_BYPASS_PATTERN_DETECTED"]


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


def test_no_prior_decision_temporal_ok(gate):
    tool_id, contract = gate.preaction_tool()
    a = g.build_temporal_policy_automaton(
        proposal=_mkprop(gate, tool_id, contract, logical_clock=1),
        prior_decision=None, contract=contract)
    assert a["temporal_ok"] is True
    assert a["signal"] is None
    assert a["temporal_problems"] == []


def test_clock_regression_rejected(gate):
    tool_id, contract = gate.preaction_tool()
    prior = {"decision_status": "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY",
             "logical_clock": 5,
             "source_freshness_epoch": contract["source_freshness_epoch"]}
    a = g.build_temporal_policy_automaton(
        proposal=_mkprop(gate, tool_id, contract, logical_clock=1),
        prior_decision=prior, contract=contract)
    assert a["temporal_ok"] is False
    assert "CLOCK_REGRESSION" in a["temporal_problems"]
    assert a["signal"] == "TEMPORAL_POLICY_REJECTED"


def test_terminal_resurrection_same_epoch_rejected(gate):
    tool_id, contract = gate.preaction_tool()
    for status in _TERMINAL:
        prior = {"decision_status": status, "logical_clock": 1,
                 "source_freshness_epoch": contract["source_freshness_epoch"]}
        a = g.build_temporal_policy_automaton(
            proposal=_mkprop(gate, tool_id, contract, logical_clock=2),
            prior_decision=prior, contract=contract)
        assert "TERMINAL_RESURRECTION" in a["temporal_problems"], status
        assert a["signal"] == "TEMPORAL_POLICY_REJECTED", status


def test_terminal_prior_new_epoch_allowed(gate):
    tool_id, contract = gate.preaction_tool()
    # A terminal-deny prior against a DIFFERENT (older) source epoch is not a
    # resurrection: the world changed, so a fresh decision is permitted.
    prior = {"decision_status": "PREACTION_BLOCKED", "logical_clock": 1,
             "source_freshness_epoch": "STALE_EPOCH_XYZ"}
    a = g.build_temporal_policy_automaton(
        proposal=_mkprop(gate, tool_id, contract, logical_clock=2),
        prior_decision=prior, contract=contract)
    assert a["temporal_ok"] is True
    assert a["signal"] is None
    assert "TERMINAL_RESURRECTION" not in a["temporal_problems"]


def test_non_terminal_prior_same_epoch_ok(gate):
    tool_id, contract = gate.preaction_tool()
    # A prior positive decision at the same epoch, with a forward clock, is a
    # legitimate transition — neither regression nor resurrection.
    prior = {"decision_status": "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY",
             "logical_clock": 2,
             "source_freshness_epoch": contract["source_freshness_epoch"]}
    a = g.build_temporal_policy_automaton(
        proposal=_mkprop(gate, tool_id, contract, logical_clock=3),
        prior_decision=prior, contract=contract)
    assert a["temporal_ok"] is True
    assert a["signal"] is None


def test_evaluate_temporal_rejection_denies(gate):
    tool_id, contract = gate.preaction_tool()
    prior = {"decision_status": "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY",
             "logical_clock": 9,
             "source_freshness_epoch": contract["source_freshness_epoch"]}
    d = _ev(gate, tool_id, contract,
            _mkprop(gate, tool_id, contract, logical_clock=1),
            prior_decision=prior)
    assert d["dominant_signal"] == "TEMPORAL_POLICY_REJECTED"
    assert d["decision_status"] == "PREACTION_DENIED"
    assert d["temporal_policy_automaton"]["signal"] == \
        "TEMPORAL_POLICY_REJECTED"


def test_temporal_subread_endpoint(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.decide(tool_id, contract)
    pid = d["proposal_id"]
    r = gate.pa(pid, path="/temporal")
    assert r.status_code == 200
    body = r.json()
    assert body["proposal_id"] == pid
    ta = body["temporal_policy_automaton"]
    assert ta["temporal_ok"] is True
    assert ta["signal"] is None

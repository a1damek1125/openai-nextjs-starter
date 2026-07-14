"""TOOL-B4 Causal Pre-Action Reference Monitor: core endpoint / read surface.

Every test drives the real HTTP surface via the `gate` fixture and asserts on
ACTUAL behavior (verified by running the kernel, not guessed).
"""
from finalis.ai_employee import tool_guardrails as g

# slug -> the decision sub-report key the endpoint surfaces.
SUBREADS = {
    "causal-graph": "causal_action_graph",
    "temporal": "temporal_policy_automaton",
    "drift": "capability_drift_sentinel",
    "counterfactual": "counterfactual_twin",
    "bypass": "bypass_simulator",
    "authority": "authority_composition",
    "path-risk": "path_risk_budget",
    "delegation": "delegation_chain_check",
    "nondelegable": "nondelegable_guard",
    "approval": "approval_guard",
    "consent": "consent_guard",
    "state-witness": "state_witness_guard",
    "intent": "intent_check",
    "schema": "schema_check",
    "scope": "scope_check",
    "effect": "effect_check",
    "attempts": "attempt_detector",
    "rate-quota": "rate_quota_check",
    "replay": "replay_verifier",
    "passport": "action_passport",
    "receipt": "governance_receipt",
    "lease": "future_execution_lease",
    "no-execution": "no_execution_proof",
    "proof-bundle": "preaction_proof_bundle",
}


def test_submit_returns_decision_envelope(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.propose(tool_id, contract).json()
    for k in ("proposal_id", "decision_status", "dominant_signal",
              "all_signals", "decision_hash"):
        assert k in d, k
    assert d["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"
    assert d["dominant_signal"] == "ALLOWED_FOR_FUTURE_BROKER_ONLY"
    assert d["all_signals"] == ["ALLOWED_FOR_FUTURE_BROKER_ONLY"]
    # Honesty invariants surfaced on every decision.
    assert d["executes_nothing"] is True
    assert d["is_execution"] is False
    assert d["requires_future_tool_broker"] is True
    assert d["action_passport"]["is_token"] is False
    assert d["action_passport"]["confers_authority"] is False
    assert d["action_passport"]["grants_execution"] is False
    assert d["governance_receipt"]["is_authority"] is False
    assert d["governance_receipt"]["authorizes_execution"] is False
    assert d["future_execution_lease"]["lease_status"] == "NOT_IMPLEMENTED"
    assert d["future_execution_lease"]["grants_execution"] is False
    assert d["no_execution_proof"]["all_hold"] is True


def test_list_proposals(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.propose(tool_id, contract).json()
    lst = gate.c.get("/ai-tools/actions/proposals", headers=gate.h()).json()
    assert isinstance(lst, list) and len(lst) == 1
    assert lst[0]["proposal_envelope_id"] == d["proposal_id"]


def test_get_proposal_envelope(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.propose(tool_id, contract).json()
    env = gate.pa(d["proposal_id"]).json()
    assert env["proposal_envelope_id"] == d["proposal_id"]
    assert env["tool_id"] == tool_id
    assert env["action_path"] == "search"


def test_get_decision(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.propose(tool_id, contract).json()
    dec = gate.pa(d["proposal_id"], "/decision").json()
    assert dec["decision_status"] == d["decision_status"]
    assert dec["decision_hash"] == d["decision_hash"]


def test_safe_view_redacts_for_restricted_roles(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.propose(tool_id, contract).json()
    pid = d["proposal_id"]
    safe = gate.pa(pid, "/safe").json()
    assert safe["all_signals"] == ["ALLOWED_FOR_FUTURE_BROKER_ONLY"]
    assert safe["executes_nothing"] is True
    assert safe["requires_future_tool_broker"] is True
    # viewer is a restricted role -> all_signals redacted to empty.
    safe_v = gate.pa(pid, "/safe", actor="viewer@demo.finalis").json()
    assert safe_v["all_signals"] == []
    # but the decision status itself is still visible.
    assert safe_v["decision_status"] == d["decision_status"]


def test_unknown_proposal_404(gate):
    assert gate.pa("does-not-exist").status_code == 404
    assert gate.pa("does-not-exist", "/decision").status_code == 404
    assert gate.pa("does-not-exist", "/safe").status_code == 404


def test_all_24_subreads(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.propose(tool_id, contract).json()
    pid = d["proposal_id"]
    assert len(SUBREADS) == 24
    for slug, field in SUBREADS.items():
        r = gate.pa(pid, "/" + slug)
        assert r.status_code == 200, (slug, r.status_code)
        body = r.json()
        assert field in body, (slug, field)
        assert body["proposal_id"] == pid


def test_registry(gate):
    tool_id, contract = gate.preaction_tool()
    gate.propose(tool_id, contract)
    gate.propose(tool_id, contract, idempotency_key="idem-2")
    reg = gate.c.get("/ai-tools/actions/registry", headers=gate.h()).json()
    assert reg["proposal_count"] == 2
    assert reg["decision_count"] == 2
    assert reg["decisions_by_status"][
        "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"] == 2


def test_policy_data_and_route(gate):
    # The literal /ai-tools/actions/policy route is hoisted ahead of the
    # parametrized /ai-tools/{tool_id}/policy route, so it is reachable and
    # surfaces the statuses / failure_dominance / reason_codes.
    r = gate.c.get("/ai-tools/actions/policy", headers=gate.h())
    assert r.status_code == 200
    p = r.json()
    assert isinstance(p["failure_dominance"], list)
    assert "ALLOWED_FOR_FUTURE_BROKER_ONLY" in p["failure_dominance"]
    assert "CIRCUIT_BREAKER_ACTIVE" in p["failure_dominance"]
    assert "ALLOWED_FOR_FUTURE_BROKER_ONLY" in p["reason_codes"]
    assert "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY" in p["decision_statuses"]
    # Kernel is authoritative and matches.
    assert isinstance(g.FAILURE_DOMINANCE, list)
    assert "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY" in g.DECISION_STATUSES
    assert len(g.DECISION_STATUSES) == 25

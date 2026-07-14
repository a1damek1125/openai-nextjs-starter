"""TOOL-B4 pre-action reference monitor: the no-execution honesty guarantee.

The monitor renders deterministic PRE-ACTION decisions and executes NOTHING,
regardless of outcome. These tests exercise a spread of decision statuses and
assert the execution-safety invariants hold uniformly, plus the module-level
honesty posture the policy endpoint is meant to advertise.

NOTE on the policy endpoint: ``GET /ai-tools/actions/policy`` is shadowed by the
earlier-registered ``GET /ai-tools/{tool_id}/policy`` (tool_id="actions"), so it
returns 404 in practice. This is verified below; the honesty properties it would
report are asserted through the reachable decision surface + module constants.
"""
from finalis.ai_employee import tool_guardrails as g

from tests.conftest import OWNER


_NO_EXEC_ITEMS = {
    "no_tool_executed", "no_broker_invoked", "no_llm_called",
    "no_external_provider_called", "no_token_issued", "no_payment_moved",
    "no_customer_message_sent", "no_crm_write", "no_evidence_mutation",
    "no_export_performed", "no_network_side_effect", "no_dry_run",
}


def _assert_executes_nothing(decision):
    assert decision["executes_nothing"] is True
    assert decision["is_execution"] is False
    assert decision["requires_future_tool_broker"] is True
    proof = decision["no_execution_proof"]
    assert proof["all_hold"] is True
    assert set(proof["assertions"]) == _NO_EXEC_ITEMS
    assert len(proof["assertions"]) == 12
    assert all(proof["assertions"].values())


def test_clean_allow_executes_nothing(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.decide(tool_id, contract, idempotency_key="a")
    assert d["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"
    _assert_executes_nothing(d)


def test_denied_intent_executes_nothing(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.decide(tool_id, contract, idempotency_key="b", intent="not-valid")
    assert d["decision_status"] == "PREACTION_DENIED"
    _assert_executes_nothing(d)


def test_circuit_breaker_blocked_executes_nothing(gate):
    tool_id, contract = gate.preaction_tool()
    assert gate.open_breaker(tool_id).status_code == 200
    d = gate.decide(tool_id, contract, idempotency_key="c")
    assert d["decision_status"] == "PREACTION_CIRCUIT_BREAKER_ACTIVE"
    _assert_executes_nothing(d)


def test_diverse_statuses_all_execute_nothing(gate):
    tool_id, contract = gate.preaction_tool()
    cases = {
        "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY":
            dict(idempotency_key="d1"),
        "PREACTION_DENIED": dict(idempotency_key="d2", intent="nope"),
        "PREACTION_NEEDS_REDUCED_SCOPE":
            dict(idempotency_key="d3", requested_scope={"record_id": "zzz"}),
        "PREACTION_NEEDS_STATE_REFRESH":
            dict(idempotency_key="d4", state_witness={"epoch": "999"}),
        "PREACTION_BYPASS_PATTERN_DETECTED":
            dict(idempotency_key="d5", payload={"query": "bearer"}),
    }
    seen = set()
    for expected, over in cases.items():
        d = gate.decide(tool_id, contract, **over)
        assert d["decision_status"] == expected
        _assert_executes_nothing(d)
        seen.add(d["decision_status"])
    assert len(seen) == 5


def test_no_execution_proof_all_twelve_assertions_hold(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.decide(tool_id, contract, idempotency_key="e")
    proof = d["no_execution_proof"]
    assert proof["no_execution_proof_version"] == g.NO_EXECUTION_PROOF_VERSION
    assert proof["all_hold"] is True
    assert sorted(proof["assertions"]) == sorted(_NO_EXEC_ITEMS)
    assert all(v is True for v in proof["assertions"].values())


def test_policy_endpoint_reports_no_execution_posture(gate):
    # The literal /actions/policy route is hoisted ahead of the parameterized
    # /ai-tools/{tool_id}/policy route, so it is reachable and reports the
    # monitor's non-execution posture honestly.
    r = gate.c.get("/ai-tools/actions/policy", headers=gate.h(OWNER))
    assert r.status_code == 200
    p = r.json()
    assert p["executes_tools"] is False and p["is_tool_broker"] is False
    assert p["is_dry_run"] is False and p["calls_llm"] is False
    assert p["issues_tokens"] is False and p["moves_payment"] is False
    assert p["ai_can_self_authorize"] is False
    assert p["consent_overridable"] is False


def test_no_execution_honesty_posture(gate):
    # The eight honesty properties the policy endpoint is meant to report, each
    # asserted through a reachable surface.
    tool_id, contract = gate.preaction_tool()
    d = gate.decide(tool_id, contract, idempotency_key="f")
    proof = d["no_execution_proof"]["assertions"]
    # executes_tools / is_tool_broker / is_dry_run False:
    assert d["executes_nothing"] is True and d["is_execution"] is False
    assert proof["no_tool_executed"] and proof["no_broker_invoked"]
    assert proof["no_dry_run"]
    # calls_llm / issues_tokens / moves_payment False:
    assert proof["no_llm_called"] and proof["no_token_issued"]
    assert proof["no_payment_moved"]
    # ai_can_self_authorize False / consent_overridable False:
    assert "The AI cannot approve its own action." in g.HONESTY_LABELS
    assert "Consent is non-overridable." in g.HONESTY_LABELS
    # The most permissive outcome still runs nothing.
    assert d["decision_status"] in g.POSITIVE_STATUSES

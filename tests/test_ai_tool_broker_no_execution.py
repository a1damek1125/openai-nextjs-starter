"""TOOL-B5 null broker: executes nothing across clean + adverse outcomes."""
from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k


def _outcomes(gate):
    """A clean outcome plus several adverse ones. All must be null-effect."""
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    outs = [k.prepare(gate, d, pobj, head, quality, contract, cert,
                      broker_request_id="brne_clean")]
    # B4 not ALLOWED.
    outs.append(k.prepare(gate, {**d, "decision_status": "PREACTION_DENIED"},
                          pobj, head, quality, contract, cert,
                          broker_request_id="brne_b4"))
    # Contract revoked.
    outs.append(k.prepare(gate, d, pobj, head, quality,
                          {**contract, "contract_status": "REVOKED"}, cert,
                          broker_request_id="brne_rev"))
    # Circuit breaker open.
    outs.append(k.prepare(gate, d, pobj, head, quality, contract, cert,
                          broker_request_id="brne_cb",
                          circuit_breaker={"breaker_state": "OPEN"}))
    return outs


def test_all_outcomes_execute_nothing(gate):
    for o in _outcomes(gate):
        assert o["executes_nothing"] is True
        assert o["is_execution"] is False
        assert o["effect_outcome"] == "NO_EFFECT_OUTCOME"
        assert o["requires_future_runtime"] is True
        assert o["null_effect_only"] is True


def test_null_effector_invokes_nothing(gate):
    o = k.clean_outcome(gate, broker_request_id="brne_eff")
    eff = o["null_effector"]
    assert eff["effect_outcome"] == "NO_EFFECT_OUTCOME"
    assert eff["invoked_external_system"] is False
    assert eff["produced_real_output"] is False


def test_non_execution_proof_all_hold_eighteen_assertions(gate):
    o = k.clean_outcome(gate, broker_request_id="brne_proof")
    proof = o["broker_non_execution_proof"]
    assert proof["all_hold"] is True
    assert len(proof["assertions"]) == 18
    assert all(v is True for v in proof["assertions"].values())


def test_policy_endpoint_reports_no_execution_surface(gate):
    r = gate.c.get("/ai-tools/broker/policy", headers=gate.h())
    assert r.status_code == 200
    p = r.json()
    for field in ("executes_tools", "has_execute_endpoint", "issues_tokens",
                  "derives_tokens", "reads_credentials",
                  "calls_external_provider", "resolves_real_adapter"):
        assert p[field] is False


def test_no_execute_endpoint_exists(gate):
    r = gate.c.post("/ai-tools/broker/execute", json={}, headers=gate.h())
    assert r.status_code in (404, 405)


def test_honesty_labels_include_all_eight_required(gate):
    required = {
        "NULL_EFFECT_ONLY", "NO_REAL_EXECUTION", "VALIDATION_ONLY",
        "FUTURE_RUNTIME_PLACEHOLDER", "PROOF_CARRYING_NULL_BROKER_ONLY",
        "FOUR_PLANE_BROKER_INTEGRITY_ONLY", "CREDENTIAL_FREE_CORRIDOR_ONLY",
        "ADVERSARIALLY_VERIFIED_NULL_ONLY"}
    assert required.issubset(set(b.HONESTY_LABELS))
    o = k.clean_outcome(gate, broker_request_id="brne_labels")
    assert required.issubset(set(o["honesty_labels"]))

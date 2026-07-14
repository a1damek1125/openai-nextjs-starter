"""TOOL-B5 null broker: side-effect zero & absence proofs.

The broker performs no side effect, reads no credential, calls no provider, and
issues no token. side_effect_zero proves zero attempts; the absence proofs
attest NO_CREDENTIAL / NO_PROVIDER_CALL / NO_TOKEN. A detected runtime surface
flips side_effect_zero to SIDE_EFFECT_DETECTED (a SIDE_EFFECT_ATTEMPT signal).
"""
from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k


def test_side_effect_zero_clean(gate):
    sz = k.clean_outcome(gate)["side_effect_zero"]
    assert sz["side_effect_zero_status"] == "SIDE_EFFECT_ZERO"
    assert sz["side_effect_count"] == 0
    assert sz["side_effect_attempts"] == []
    assert sz["signal"] is None


def test_absence_proofs_clean(gate):
    ap = k.clean_outcome(gate)["absence_proofs"]
    assert ap["credential_absence_proof"]["status"] == "NO_CREDENTIAL"
    assert ap["no_provider_proof"]["status"] == "NO_PROVIDER_CALL"
    assert ap["no_token_proof"]["status"] == "NO_TOKEN"
    assert ap["credential_absence_proof"]["credential_present"] is False
    assert ap["no_provider_proof"]["provider_called"] is False
    assert ap["no_token_proof"]["token_issued"] is False


def test_side_effect_zero_detects_runtime_surface(gate):
    """Building side_effect_zero directly with a runtime_surface_diff that
    reports a detected surface flips it to SIDE_EFFECT_DETECTED."""
    sz = b.build_side_effect_zero(
        tenant_id=gate.tid, broker_request_id="br1",
        null_effector={"invoked_external_system": False,
                       "produced_real_output": False},
        runtime_surface_diff={"detected_runtime_surface": ["execute_endpoint"]},
        adapter_freeze={"callable_adapter_detected": False})
    assert sz["side_effect_zero_status"] == "SIDE_EFFECT_DETECTED"
    assert sz["signal"] == "SIDE_EFFECT_ATTEMPT"
    assert sz["side_effect_count"] == 1
    assert sz["side_effect_attempts"] == ["RUNTIME_SURFACE"]


def test_side_effect_zero_hash_deterministic(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o1 = k.prepare(gate, d, pobj, head, quality, contract, cert,
                   actor_id="a", created_at="T1")
    o2 = k.prepare(gate, d, pobj, head, quality, contract, cert,
                   actor_id="b", created_at="T2")
    assert (o1["side_effect_zero"]["side_effect_zero_hash"] ==
            o2["side_effect_zero"]["side_effect_zero_hash"])


def test_endpoints_side_effect_zero_and_absence(gate):
    rid, _ = gate.prepared_broker()

    r = gate.br(rid, "/side-effect-zero")
    assert r.status_code == 200
    sz = r.json()["side_effect_zero"]
    assert sz["side_effect_zero_status"] == "SIDE_EFFECT_ZERO"
    assert sz["side_effect_count"] == 0
    assert sz["side_effect_attempts"] == []

    r = gate.br(rid, "/absence-proofs")
    assert r.status_code == 200
    ap = r.json()["absence_proofs"]
    assert ap["credential_absence_proof"]["status"] == "NO_CREDENTIAL"
    assert ap["no_provider_proof"]["status"] == "NO_PROVIDER_CALL"
    assert ap["no_token_proof"]["status"] == "NO_TOKEN"


def test_endpoint_broker_non_execution(gate):
    rid, _ = gate.prepared_broker()
    r = gate.br(rid, "/broker-non-execution")
    assert r.status_code == 200
    proof = r.json()["broker_non_execution_proof"]
    assert proof["all_hold"] is True
    assert all(v is True for v in proof["assertions"].values())

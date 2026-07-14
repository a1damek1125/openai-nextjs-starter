"""TOOL-B5 null broker: negative execution certificate & proof-carrying cert.

The negative execution certificate is local, replay-verifiable evidence of what
did NOT happen. It is not a token and cannot authorize execution. The proof-
carrying certificate likewise is neither token nor credential nor authority.
The outcome closes NULL (equivalent to no state changed).
"""
from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k


def test_negative_execution_certified(gate):
    nec = k.clean_outcome(gate)["negative_execution_certificate"]
    assert nec["certificate_status"] == "NEGATIVE_EXECUTION_CERTIFIED"
    assert nec["signal"] is None


def test_negative_certificate_is_not_token_no_authority(gate):
    nec = k.clean_outcome(gate)["negative_execution_certificate"]
    assert nec["is_token"] is False
    assert nec["authorizes_execution"] is False
    assert nec["replay_verifiable"] is True


def test_negative_certificate_states_that_did_not_happen(gate):
    nec = k.clean_outcome(gate)["negative_execution_certificate"]
    assert nec["states_that_did_not_happen"]
    assert "no_tool_executed" in nec["states_that_did_not_happen"]


def test_negative_certificate_fails_on_side_effect(gate):
    """Building the certificate with a side_effect_zero that reports a detected
    side effect forces NEGATIVE_EXECUTION_CERTIFICATE_FAILED."""
    o = k.clean_outcome(gate)
    bad_sz = dict(o["side_effect_zero"])
    bad_sz["side_effect_zero_status"] = "SIDE_EFFECT_DETECTED"
    nec = b.build_negative_execution_certificate(
        tenant_id=gate.tid, broker_request_id="br1",
        non_execution_proof=o["broker_non_execution_proof"],
        side_effect_zero=bad_sz, absence_proofs=o["absence_proofs"])
    assert nec["certificate_status"] == "NEGATIVE_EXECUTION_CERTIFICATE_FAILED"
    assert nec["signal"] == "NEGATIVE_EXECUTION_CERTIFICATE_FAILED"


def test_proof_carrying_certificate_not_token_credential_authority(gate):
    pcc = k.clean_outcome(gate)["proof_carrying_broker_action_certificate"]
    assert pcc["is_token"] is False
    assert pcc["is_credential"] is False
    assert pcc["authorizes_execution"] is False


def test_outcome_closure_null(gate):
    oc = k.clean_outcome(gate)["outcome_closure_checkpoint"]
    assert oc["closure_status"] == "OUTCOME_CLOSED_NULL"
    assert oc["outcome_equivalent_to_no_state_changed"] is True


def test_endpoints_negative_and_proof_and_closure(gate):
    rid, _ = gate.prepared_broker()

    r = gate.br(rid, "/negative-execution-certificate")
    assert r.status_code == 200
    nec = r.json()["negative_execution_certificate"]
    assert nec["certificate_status"] == "NEGATIVE_EXECUTION_CERTIFIED"
    assert nec["is_token"] is False
    assert nec["authorizes_execution"] is False
    assert nec["replay_verifiable"] is True

    r = gate.br(rid, "/proof-carrying-certificate")
    assert r.status_code == 200
    pcc = r.json()["proof_carrying_broker_action_certificate"]
    assert pcc["is_token"] is False
    assert pcc["is_credential"] is False
    assert pcc["authorizes_execution"] is False

    r = gate.br(rid, "/outcome-closure")
    assert r.status_code == 200
    assert r.json()["outcome_closure_checkpoint"]["closure_status"] == \
        "OUTCOME_CLOSED_NULL"


def test_negative_certificate_hash_deterministic(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o1 = k.prepare(gate, d, pobj, head, quality, contract, cert,
                   actor_id="a", created_at="T1")
    o2 = k.prepare(gate, d, pobj, head, quality, contract, cert,
                   actor_id="b", created_at="T2")
    assert (o1["negative_execution_certificate"][
                "negative_execution_certificate_hash"] ==
            o2["negative_execution_certificate"][
                "negative_execution_certificate_hash"])

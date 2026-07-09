"""TOOL-B5: token non-derivation (b.build_token_non_derivation).

No token may be minted, accepted, inferred, derived or simulated from B4/B5
evidence. Passport/receipt/lease and every broker certificate are evidence, NOT
tokens. A passport that claims is_token=True is a derivation attempt ->
QUARANTINED. Every asserted status confirmed by running the kernel.
"""
import copy

from tests import _b5_kernel as k


def test_clean_outcome_derives_no_token(gate):
    o = k.clean_outcome(gate)
    tnd = o["token_non_derivation"]
    assert tnd["token_non_derivation_status"] == "NO_TOKEN_DERIVED"
    assert tnd["signal"] is None
    assert tnd["token_minted"] is False
    assert tnd["token_accepted"] is False
    assert tnd["token_derived"] is False
    assert tnd["token_derivation_findings"] == []
    assert o["broker_status"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"


def test_clean_passport_receipt_lease_are_not_tokens(gate):
    # The real B4 decision's passport/receipt/lease all carry
    # is_token/is_bearer/confers_authority/grants_execution = False, so no
    # finding is raised.
    o = k.clean_outcome(gate)
    assert o["token_non_derivation"]["token_derivation_findings"] == []


def test_broker_certificates_are_not_tokens(gate):
    o = k.clean_outcome(gate)
    pcc = o["proof_carrying_broker_action_certificate"]
    assert pcc["is_token"] is False
    assert pcc["authorizes_execution"] is False
    neg = o["negative_execution_certificate"]
    assert neg["is_token"] is False
    assert neg["authorizes_execution"] is False


def test_passport_claiming_is_token_is_a_derivation_attempt(gate):
    # Drive the token-non-derivation proof DIRECTLY with a passport that claims
    # is_token=True: the proof detects the derivation attempt.
    import finalis.ai_employee.tool_broker as b
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    d2 = copy.deepcopy(d)
    d2["action_passport"]["is_token"] = True
    env = k.make_env(gate, d2, pobj)
    tnd = b.build_token_non_derivation(
        tenant_id=gate.tid, broker_request_id="br1", b4_decision=d2, envelope=env)
    assert tnd["token_non_derivation_status"] == "TOKEN_DERIVATION_DETECTED"
    assert tnd["signal"] == "TOKEN_DERIVATION_ATTEMPT"
    assert "ACTION_PASSPORT_IS_TOKEN_LIKE" in tnd["token_derivation_findings"]
    # Through the full pipeline the same tampered passport still raises the
    # attempt signal (it is dominated here by the upstream receipt-drift block,
    # which correctly fails closed).
    o = k.prepare(gate, d2, pobj, head, quality, contract, cert)
    assert "TOKEN_DERIVATION_ATTEMPT" in o["all_signals"]
    assert o["broker_status"] == "BLOCKED"


def test_receipt_confers_authority_quarantines_with_token_attempt(gate):
    # A governance receipt that claims to confer authority is a token-like
    # derivation attempt; here TOKEN_DERIVATION_ATTEMPT dominates -> QUARANTINED.
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    d2 = copy.deepcopy(d)
    d2["governance_receipt"]["confers_authority"] = True
    o = k.prepare(gate, d2, pobj, head, quality, contract, cert)
    tnd = o["token_non_derivation"]
    assert tnd["token_non_derivation_status"] == "TOKEN_DERIVATION_DETECTED"
    assert "GOVERNANCE_RECEIPT_IS_TOKEN_LIKE" in tnd["token_derivation_findings"]
    assert o["dominant_signal"] == "TOKEN_DERIVATION_ATTEMPT"
    assert o["broker_status"] == "QUARANTINED"


def test_token_non_derivation_hash_is_deterministic(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o1 = k.prepare(gate, d, pobj, head, quality, contract, cert)
    o2 = k.prepare(gate, d, pobj, head, quality, contract, cert)
    assert (o1["token_non_derivation"]["token_non_derivation_hash"] ==
            o2["token_non_derivation"]["token_non_derivation_hash"])


def test_negative_execution_certificate_is_replay_verifiable_null(gate):
    o = k.clean_outcome(gate)
    neg = o["negative_execution_certificate"]
    assert neg["replay_verifiable"] is True
    assert neg["certificate_status"] == "NEGATIVE_EXECUTION_CERTIFIED"

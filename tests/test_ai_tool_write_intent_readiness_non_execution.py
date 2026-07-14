"""TOOL-B7 v4: Transaction readiness non-execution certificate — a bundle of
NEGATIVE claims proving that being ready never turned into an effect: nothing
committed, released, activated, mutated, sent, exported or called. Any attempt
falsifies the relevant claim."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_certificate_exists(gate):
    r = k.clean_outcome(gate)["transaction_readiness_non_execution_certificate"]
    assert r["transaction_readiness_non_execution_certificate_id"].startswith(
        "rne-")
    assert r["certificate_status"] == "NON_EXECUTION_CERTIFIED"


def test_all_negative_claims_hold_on_clean(gate):
    r = k.clean_outcome(gate)["transaction_readiness_non_execution_certificate"]
    assert r["all_negative_claims_hold"] is True


def test_every_negative_claim_present_and_true_on_clean(gate):
    r = k.clean_outcome(gate)["transaction_readiness_non_execution_certificate"]
    claims = r["negative_claims"]
    for key in ("commit_readiness_did_not_execute", "escrow_did_not_execute",
                "future_commit_gate_did_not_execute",
                "staged_effect_outbox_did_not_release",
                "active_commitment_record_did_not_activate",
                "approval_did_not_execute", "no_crm_mutation",
                "no_evidence_mutation", "no_payment", "no_customer_message",
                "no_export", "no_provider_mcp_llm_call",
                "no_token_or_credential_use", "commit_gate_does_not_exist",
                "commit_not_executable_now"):
        assert claims[key] is True, key


def test_release_attempt_falsifies_outbox_claim(gate):
    o = k.prepare(gate, k.b6_outcome(gate), effect_release_attempts=1)
    r = o["transaction_readiness_non_execution_certificate"]
    assert r["negative_claims"]["staged_effect_outbox_did_not_release"] is False
    assert r["all_negative_claims_hold"] is False
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_crm_attempt_falsifies_crm_claim(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  attempt_markers={"crm_mutation": True})
    r = o["transaction_readiness_non_execution_certificate"]
    assert r["negative_claims"]["no_crm_mutation"] is False
    assert r["all_negative_claims_hold"] is False
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_payment_attempt_falsifies_payment_claim(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  attempt_markers={"payment": True})
    r = o["transaction_readiness_non_execution_certificate"]
    assert r["negative_claims"]["no_payment"] is False
    assert r["all_negative_claims_hold"] is False


def test_provider_call_attempt_falsifies_provider_claim(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  attempt_markers={"provider_call": True})
    r = o["transaction_readiness_non_execution_certificate"]
    assert r["negative_claims"]["no_provider_mcp_llm_call"] is False
    assert r["all_negative_claims_hold"] is False
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_certificate_cannot_execute_via_commit_marker(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  execution_markers={"commit_executable_now": True})
    assert o["commit_executable_now"] is False
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_certificate_hash_excludes_itself_and_recomputes(gate):
    r = k.clean_outcome(gate)["transaction_readiness_non_execution_certificate"]
    recomputed = _core_hash(
        r, "transaction_readiness_non_execution_certificate_hash", "signal")
    assert recomputed == r[
        "transaction_readiness_non_execution_certificate_hash"]


def test_certificate_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["transaction_readiness_non_execution_certificate"][
        "transaction_readiness_non_execution_certificate_hash"] == \
        o2["transaction_readiness_non_execution_certificate"][
            "transaction_readiness_non_execution_certificate_hash"]


def test_readiness_non_execution_endpoint(gate):
    wid, _ = gate.prepared_write_intent()
    r = gate.wi(wid, "/readiness-non-execution").json()[
        "transaction_readiness_non_execution_certificate"]
    assert r["all_negative_claims_hold"] is True
    assert r["negative_claims"]["commit_not_executable_now"] is True

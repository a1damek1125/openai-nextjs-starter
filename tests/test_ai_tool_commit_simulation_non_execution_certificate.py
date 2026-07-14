"""TOOL-B8 v4: non-execution certificate — every negative claim about real
effects must hold; any attempt marker flips its claim and quarantines."""
import pytest

from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k

# marker -> (dominant signal, negative-claim key it falsifies)
MARKER_CASES = [
    ("real_commit", "REAL_COMMIT_ATTEMPT", "no_real_commit"),
    ("effect_release", "EFFECT_RELEASE_ATTEMPT", "no_effect_release"),
    ("activate_commitment", "COMMITMENT_RECORD_ACTIVATED", "no_commit_activation"),
    ("activate_b9", "B9_ACTIVATION_ATTEMPT", "no_b9_activation"),
    ("provider_call", "PROVIDER_CALL_ATTEMPT", "no_provider"),
    ("mcp_call", "MCP_CALL_ATTEMPT", "no_mcp"),
    ("llm_call", "LLM_CALL_ATTEMPT", "no_llm"),
    ("token_issue", "TOKEN_ISSUANCE_ATTEMPT", "no_token"),
    ("credential_read", "CREDENTIAL_READ_DETECTED", "no_credential"),
    ("customer_message", "CUSTOMER_MESSAGE_ATTEMPT", "no_message"),
    ("payment", "PAYMENT_ATTEMPT", "no_payment"),
    ("crm_mutation", "CRM_MUTATION_ATTEMPT", "no_crm_mutation"),
    ("evidence_mutation", "EVIDENCE_MUTATION_ATTEMPT", "no_evidence_mutation"),
    ("data_export", "DATA_EXPORT_ATTEMPT", "no_export"),
]


def test_clean_certificate_certified(gate):
    c = k.clean_outcome(gate)["non_execution_certificate"]
    assert c["certificate_status"] == "NON_EXECUTION_CERTIFIED"
    assert c["all_negative_claims_hold"] is True
    assert c["signals_detected"] == []


def test_clean_every_negative_claim_true(gate):
    c = k.clean_outcome(gate)["non_execution_certificate"]
    assert c["negative_claims"]
    for key, val in c["negative_claims"].items():
        assert val is True, key


def test_real_commit_marker_flips_claim(gate):
    o = k.clean_outcome(gate, attempt_markers={"real_commit": True})
    c = o["non_execution_certificate"]
    assert o["dominant_signal"] == "REAL_COMMIT_ATTEMPT"
    assert c["negative_claims"]["no_real_commit"] is False
    assert c["all_negative_claims_hold"] is False
    assert c["certificate_status"] != "NON_EXECUTION_CERTIFIED"


@pytest.mark.parametrize("marker,signal,claim", MARKER_CASES)
def test_each_marker_flips_claim_and_quarantines(gate, marker, signal, claim):
    o = k.clean_outcome(gate, attempt_markers={marker: True})
    c = o["non_execution_certificate"]
    assert o["dominant_signal"] == signal
    assert signal in c["signals_detected"]
    assert c["negative_claims"][claim] is False
    assert o["commit_simulation_status"] == "B8_V5_QUARANTINED"
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_marker_keeps_no_external_effect(gate):
    o = k.clean_outcome(gate, attempt_markers={"payment": True})
    assert o["produced_external_effect"] is False
    assert o["commit_executable_now"] is False
    assert o["b9_revalidation_required"] is True


def test_certificate_hash_recomputes(gate):
    c = k.clean_outcome(gate)["non_execution_certificate"]
    assert _core_hash(c, "non_execution_certificate_hash",
                      "signals_detected") == \
        c["non_execution_certificate_hash"]


# --- API layer -------------------------------------------------------------
def test_api_certificate_endpoint_certified(gate):
    sid, _ = gate.prepared_commit_simulation()
    c = gate.cs(sid, "/non-execution-certificate").json()[
        "non_execution_certificate"]
    assert c["certificate_status"] == "NON_EXECUTION_CERTIFIED"
    assert c["all_negative_claims_hold"] is True


def test_api_certificate_hash_recomputes(gate):
    sid, _ = gate.prepared_commit_simulation()
    c = gate.cs(sid, "/non-execution-certificate").json()[
        "non_execution_certificate"]
    assert _core_hash(c, "non_execution_certificate_hash",
                      "signals_detected") == \
        c["non_execution_certificate_hash"]

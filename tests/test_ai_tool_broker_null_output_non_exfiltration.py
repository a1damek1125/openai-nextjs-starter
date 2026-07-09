"""TOOL-B5: null-output non-exfiltration (b.build_non_exfiltration) tests.

The broker must never surface payload/secret/credential/approval/consent/customer
data or hidden execution authority in its (null) output. These tests drive the
builder DIRECTLY with crafted candidate_output dicts. Every asserted status was
confirmed by running the kernel.
"""
from finalis.ai_employee import tool_broker as b

TID = "tenant-b5"


def _nx(candidate, tenant_id=TID):
    return b.build_non_exfiltration(
        tenant_id=tenant_id, broker_request_id="br1",
        candidate_output=candidate, sensitive_inputs=[{"payload": "x"}])


def test_forbidden_leak_patterns_list_has_the_10_documented_patterns():
    assert b.FORBIDDEN_LEAK_PATTERNS == [
        "SECRET_VALUE", "TOKEN_LIKE_VALUE", "CREDENTIAL_LIKE_VALUE",
        "FULL_PAYLOAD_LEAK", "FULL_APPROVAL_ARTIFACT_LEAK",
        "FULL_CONSENT_ARTIFACT_LEAK", "CUSTOMER_SENSITIVE_FIELD_LEAK",
        "CROSS_TENANT_DATA_LEAK", "EXECUTION_AUTHORITY_LEAK",
        "PROVIDER_RESULT_FABRICATION",
    ]
    assert len(b.FORBIDDEN_LEAK_PATTERNS) == 10


def test_clean_candidate_ids_status_hashes_labels_is_not_exfiltration():
    clean = {"broker_request_id": "br1", "tenant_id": TID,
             "broker_status": "BROKER_PREPARED_FOR_FUTURE_ONLY",
             "effect_outcome": "NO_EFFECT_OUTCOME", "null_effect_only": True,
             "broker_decision_hash": "deadbeefcafe",
             "honesty_labels": b.HONESTY_LABELS}
    proof = _nx(clean)
    assert proof["non_exfiltration_status"] == "NO_OUTPUT_EXFILTRATION"
    assert proof["leak_detected"] is False
    assert proof["detected_leaks"] == []
    assert proof["signal"] is None


def test_honesty_label_descriptive_text_is_not_a_leak():
    # The honesty label constant text (e.g. CREDENTIAL_FREE_CORRIDOR_ONLY) is
    # descriptive, never a credential -> the candidate stays CLEAN.
    assert "CREDENTIAL_FREE_CORRIDOR_ONLY" in b.HONESTY_LABELS
    candidate = {"broker_request_id": "br1", "tenant_id": TID,
                 "honesty_labels": ["CREDENTIAL_FREE_CORRIDOR_ONLY",
                                    "NO_REAL_EXECUTION"]}
    proof = _nx(candidate)
    assert proof["non_exfiltration_status"] == "NO_OUTPUT_EXFILTRATION"
    assert proof["leak_detected"] is False


def test_payload_key_is_full_payload_leak():
    proof = _nx({"payload": {"amount": "100"}})
    assert "FULL_PAYLOAD_LEAK" in proof["detected_leaks"]
    assert proof["non_exfiltration_status"] == "OUTPUT_EXFILTRATION_DETECTED"
    assert proof["signal"] == "NULL_OUTPUT_EXFILTRATION_DETECTED"


def test_secret_value_is_secret_and_credential_like():
    proof = _nx({"detail": "my password is here"})
    assert "SECRET_VALUE" in proof["detected_leaks"]
    assert "CREDENTIAL_LIKE_VALUE" in proof["detected_leaks"]
    assert proof["leak_detected"] is True


def test_key_with_secret_marker_is_credential_like():
    proof = _nx({"apikey": "redacted"})
    assert "CREDENTIAL_LIKE_VALUE" in proof["detected_leaks"]


def test_bearer_and_accesstoken_values_are_token_like():
    for val in ("bearer eyJabc", "here is an access_token value"):
        proof = _nx({"detail": val})
        assert "TOKEN_LIKE_VALUE" in proof["detected_leaks"], val
        assert proof["non_exfiltration_status"] == "OUTPUT_EXFILTRATION_DETECTED"


def test_approval_ref_is_full_approval_artifact_leak():
    proof = _nx({"approval_ref": "APP-1"})
    assert "FULL_APPROVAL_ARTIFACT_LEAK" in proof["detected_leaks"]


def test_consent_ref_is_full_consent_artifact_leak():
    proof = _nx({"consent_ref": "CON-1"})
    assert "FULL_CONSENT_ARTIFACT_LEAK" in proof["detected_leaks"]


def test_customer_email_or_phone_key_is_customer_sensitive_leak():
    for key in ("email", "phone"):
        proof = _nx({key: "value"})
        assert "CUSTOMER_SENSITIVE_FIELD_LEAK" in proof["detected_leaks"], key


def test_provider_result_key_is_provider_result_fabrication():
    proof = _nx({"provider_result": {"ok": True}})
    assert "PROVIDER_RESULT_FABRICATION" in proof["detected_leaks"]


def test_execution_authority_leak_via_flag_or_key():
    p1 = _nx({"grants_execution": True})
    assert "EXECUTION_AUTHORITY_LEAK" in p1["detected_leaks"]
    p2 = _nx({"execution_authority": "yes"})
    assert "EXECUTION_AUTHORITY_LEAK" in p2["detected_leaks"]


def test_cross_tenant_value_is_cross_tenant_data_leak():
    proof = b.build_non_exfiltration(
        tenant_id="THISTENANT", broker_request_id="br1",
        candidate_output={"ref": "tenant:OTHERTENANT"}, sensitive_inputs=[])
    assert "CROSS_TENANT_DATA_LEAK" in proof["detected_leaks"]
    assert proof["signal"] == "NULL_OUTPUT_EXFILTRATION_DETECTED"


def test_non_exfiltration_hash_is_deterministic():
    c = {"payload": {"a": "b"}}
    assert (_nx(c)["null_output_non_exfiltration_hash"] ==
            _nx(c)["null_output_non_exfiltration_hash"])

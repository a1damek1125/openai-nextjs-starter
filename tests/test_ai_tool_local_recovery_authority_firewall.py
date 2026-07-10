"""TOOL-B9.1 v4: recovery authority firewall — recovery/rollback/abort authority
is server-side ONLY. A channel message, mobile push, workbench/LLM/tool output,
document/OCR/artifact, context slice, B9 certificate, Proof-of-Recovery or
Recovery Safety Case can NEVER be recovery authority. Each is rejected with a
specific reason code and NO recovery is applied.
"""
from tests import _b91_kernel as k


def _rejected(source, expected_signal):
    o = k.prepare(desired_recovery_action="RECOVER",
                  recovery_authority_basis={"source": source})
    assert o["final_recovery_state"] == "QUARANTINED"
    assert o["dominant_signal"] == expected_signal
    assert o["recovery_applied"] is False
    assert o["quarantine_required"] is True
    # No external effect ever, even on a rejected recovery.
    assert o["produced_external_effect"] is False
    assert o["provider_called"] is False
    assert o["outbox_released"] is False
    return o


def test_channel_slack_rejected():
    _rejected("SLACK_MESSAGE", "CHANNEL_AS_RECOVERY_AUTHORITY_REJECTED")


def test_channel_teams_rejected():
    _rejected("TEAMS_MESSAGE", "CHANNEL_AS_RECOVERY_AUTHORITY_REJECTED")


def test_channel_email_rejected():
    _rejected("EMAIL_BODY", "CHANNEL_AS_RECOVERY_AUTHORITY_REJECTED")


def test_mobile_push_rejected():
    _rejected("MOBILE_PUSH", "MOBILE_PUSH_AS_RECOVERY_AUTHORITY_REJECTED")


def test_workbench_output_rejected():
    _rejected("WORKBENCH_OUTPUT", "WORKBENCH_OUTPUT_AS_RECOVERY_AUTHORITY_REJECTED")


def test_document_rejected():
    _rejected("DOCUMENT", "DOCUMENT_AS_RECOVERY_AUTHORITY_REJECTED")


def test_ocr_text_rejected():
    _rejected("OCR_TEXT", "DOCUMENT_AS_RECOVERY_AUTHORITY_REJECTED")


def test_artifact_rejected():
    _rejected("ARTIFACT_LABEL", "ARTIFACT_AS_RECOVERY_AUTHORITY_REJECTED")


def test_llm_output_rejected():
    _rejected("LLM_OUTPUT", "LLM_OUTPUT_AS_RECOVERY_AUTHORITY_REJECTED")


def test_tool_output_rejected():
    _rejected("TOOL_OUTPUT", "TOOL_OUTPUT_AS_RECOVERY_AUTHORITY_REJECTED")


def test_context_slice_rejected():
    _rejected("CONTEXT_SLICE", "CONTEXT_AS_RECOVERY_AUTHORITY_REJECTED")


def test_b9_certificate_rejected():
    _rejected("B9_CERTIFICATE", "B9_CERTIFICATE_AS_AUTHORITY_REJECTED")


def test_proof_of_recovery_rejected():
    _rejected("PROOF_OF_RECOVERY", "PROOF_OF_RECOVERY_AS_AUTHORITY_REJECTED")


def test_safety_case_rejected():
    _rejected("RECOVERY_SAFETY_CASE", "SAFETY_CASE_AS_AUTHORITY_REJECTED")


def test_missing_authority_fails_closed():
    o = k.prepare(desired_recovery_action="RECOVER", recovery_authority_basis={})
    assert o["final_recovery_state"] == "RECOVERY_FAILED"
    assert o["dominant_signal"] == "RECOVERY_AUTHORITY_MISSING"
    assert o["recovery_applied"] is False


def test_surface_cannot_grant_recovery_authority():
    o = k.prepare(desired_recovery_action="RECOVER",
                  surface_claims_recovery_authority=True)
    assert o["dominant_signal"] == "SOURCE_SURFACE_GRANTED_RECOVERY_AUTHORITY"
    assert o["recovery_applied"] is False


def test_server_side_authority_allowed():
    o = k.prepare(desired_recovery_action="RECOVER",
                  recovery_authority_basis={"source": "SERVER_RBAC"})
    assert o["final_recovery_state"] == "RECOVERED"
    fw = o["recovery_authority_firewall"]
    assert fw["firewall_status"] == "CLEAN"
    assert fw["grants_authority"] is False and fw["is_authority"] is False


def test_contamination_changes_decision_hash():
    clean = k.prepare()["b91_decision_hash"]
    doc = k.prepare(recovery_authority_basis={"source": "DOCUMENT"})[
        "b91_decision_hash"]
    assert clean != doc


# --- API layer -------------------------------------------------------------
def test_api_document_authority_quarantined(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="run",
                     recovery_authority_basis={"source": "DOCUMENT"}).json()
    assert o["final_recovery_state"] == "QUARANTINED"
    assert o["dominant_signal"] == "DOCUMENT_AS_RECOVERY_AUTHORITY_REJECTED"
    assert o["recovery_applied"] is False


def test_api_firewall_endpoint(gate):
    rid, _ = gate.prepared_recovery(action="run")
    fw = gate.rc(rid, "authority-firewall").json()["recovery_authority_firewall"]
    assert fw["firewall_status"] == "CLEAN"
    assert fw["server_side_only"] is True

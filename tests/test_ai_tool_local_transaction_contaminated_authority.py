"""TOOL-B9 v5: contaminated-authority firewall — a document, OCR text, channel
message, mobile push, workbench/LLM/tool output, B8 artifact, or context slice
can NEVER be the authority for a local commit. Each is quarantined with a
specific reason code and NO commit is applied.
"""
from tests import _b9_kernel as k


def _quarantined(over, expected_signal):
    o = k.prepare(**over)
    assert o["b9_status"] == "B9_QUARANTINED"
    assert o["dominant_signal"] == expected_signal
    assert o["local_commit_applied"] is False
    return o


def test_document_as_command_rejected():
    _quarantined({"authority_basis": {"source": "DOCUMENT"}},
                 "DOCUMENT_AS_COMMAND_REJECTED")


def test_ocr_text_as_command_rejected():
    _quarantined({"authority_basis": {"source": "OCR_TEXT"}},
                 "DOCUMENT_AS_COMMAND_REJECTED")


def test_channel_message_as_approval_rejected():
    _quarantined({"authority_basis": {"source": "SLACK_MESSAGE"}},
                 "CHANNEL_AS_APPROVAL_REJECTED")


def test_mobile_push_as_approval_rejected():
    _quarantined({"authority_basis": {"source": "MOBILE_PUSH"}},
                 "MOBILE_PUSH_AS_APPROVAL_REJECTED")


def test_workbench_output_as_execution_rejected():
    _quarantined({"authority_basis": {"source": "WORKBENCH_OUTPUT"}},
                 "WORKBENCH_OUTPUT_AS_EXECUTION_REJECTED")


def test_llm_output_as_authority_rejected():
    _quarantined({"authority_basis": {"source": "LLM_OUTPUT"}},
                 "LLM_OUTPUT_AS_AUTHORITY_REJECTED")


def test_tool_output_as_authority_rejected():
    _quarantined({"authority_basis": {"source": "TOOL_OUTPUT"}},
                 "TOOL_OUTPUT_AS_AUTHORITY_REJECTED")


def test_b8_artifact_as_authority_rejected():
    _quarantined({"authority_basis": {"source": "B8_ARTIFACT"}},
                 "B8_ARTIFACT_AS_AUTHORITY_REJECTED")


def test_context_slice_as_authority_rejected():
    _quarantined({"authority_basis": {"source": "CONTEXT_SLICE"}},
                 "CONTEXT_AS_AUTHORITY_REJECTED")


def test_clean_authority_firewall_is_clean():
    o = k.clean_outcome()
    fw = o["contaminated_authority_firewall"]
    assert fw["firewall_status"] == "CLEAN"
    assert o["local_commit_applied"] is True


def test_contamination_changes_decision_hash():
    clean = k.prepare()["b9_decision_hash"]
    doc = k.prepare(authority_basis={"source": "DOCUMENT"})["b9_decision_hash"]
    assert clean != doc


# --- API layer -------------------------------------------------------------
def test_api_document_authority_quarantined(gate):
    b8id, _ = gate.b8_accepted_outcome()
    o = gate.local_tx(b8id, op="commit-local",
                      authority_basis={"source": "DOCUMENT"}).json()
    assert o["b9_status"] == "B9_QUARANTINED"
    assert o["dominant_signal"] == "DOCUMENT_AS_COMMAND_REJECTED"
    assert o["local_commit_applied"] is False

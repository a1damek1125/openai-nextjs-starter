"""TOOL-B7: commit non-execution — the draft never executes; each attempt
marker is detected and surfaces its matching *_ATTEMPT/DETECTED signal that
blocks the positive terminal."""
from finalis.ai_employee.tool_write_intent import _core_hash, POSITIVE_STATUSES
from tests import _b7_kernel as k


def test_clean_non_executing(gate):
    cne = k.clean_outcome(gate)["commit_non_execution"]
    assert cne["non_execution_status"] == "NON_EXECUTING"
    assert cne["commit_executed"] is False
    assert cne["any_external_effect"] is False
    assert cne["signals_detected"] == []


def test_clean_no_attempt_markers(gate):
    cne = k.clean_outcome(gate)["commit_non_execution"]
    assert cne["detected_attempt_markers"] == []


def _report(gate, **markers):
    return k.prepare(gate, k.b6_outcome(gate),
                     attempt_markers=markers)["commit_non_execution"]


def test_commit_marker(gate):
    cne = _report(gate, commit=True)
    assert "COMMIT_ATTEMPT_DETECTED" in cne["signals_detected"]
    assert cne["non_execution_status"] == "ATTEMPT_DETECTED"


def test_payment_marker(gate):
    assert "PAYMENT_ATTEMPT" in _report(gate, payment=True)["signals_detected"]


def test_crm_mutation_marker(gate):
    assert "CRM_MUTATION_ATTEMPT" in \
        _report(gate, crm_mutation=True)["signals_detected"]


def test_evidence_mutation_marker(gate):
    assert "EVIDENCE_MUTATION_ATTEMPT" in \
        _report(gate, evidence_mutation=True)["signals_detected"]


def test_data_export_marker(gate):
    assert "DATA_EXPORT_ATTEMPT" in \
        _report(gate, data_export=True)["signals_detected"]


def test_customer_message_marker(gate):
    assert "CUSTOMER_MESSAGE_ATTEMPT" in \
        _report(gate, customer_message=True)["signals_detected"]


def test_provider_mcp_llm_markers(gate):
    assert "PROVIDER_CALL_ATTEMPT" in \
        _report(gate, provider_call=True)["signals_detected"]
    assert "MCP_CALL_ATTEMPT" in _report(gate, mcp_call=True)["signals_detected"]
    assert "LLM_CALL_ATTEMPT" in _report(gate, llm_call=True)["signals_detected"]


def test_token_and_credential_markers(gate):
    assert "TOKEN_ISSUANCE_ATTEMPT" in \
        _report(gate, token_issue=True)["signals_detected"]
    assert "CREDENTIAL_READ_DETECTED" in \
        _report(gate, credential_read=True)["signals_detected"]


def test_each_marker_blocks_positive_terminal(gate):
    for m in ("commit", "payment", "crm_mutation", "evidence_mutation",
              "data_export", "customer_message", "provider_call", "mcp_call",
              "llm_call", "token_issue", "credential_read"):
        o = k.prepare(gate, k.b6_outcome(gate), attempt_markers={m: True})
        assert o["write_intent_status"] not in POSITIVE_STATUSES, m


def test_commit_non_execution_hash_recomputes(gate):
    cne = k.clean_outcome(gate)["commit_non_execution"]
    assert _core_hash(cne, "commit_non_execution_hash", "signals_detected") == \
        cne["commit_non_execution_hash"]


def test_commit_non_execution_endpoint(gate):
    wid, _ = gate.prepared_write_intent()
    cne = gate.wi(wid, "/commit-non-execution").json()["commit_non_execution"]
    assert cne["commit_executed"] is False
    assert cne["any_external_effect"] is False

"""TOOL-B6: runtime outcome record + safe output surface. A complete outcome
surfaces PUBLIC safe output only; adverse outcomes surface no output; the /safe
endpoint and output sub-field endpoints never leak."""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k
from tests.conftest import VIEWER


def test_clean_outcome_record(gate):
    o = k.clean_outcome(gate)
    assert o["runtime_outcome_kind"] == "READ_ONLY_LOCAL_RESULT"
    assert o["safe_output"] == {"case_id": "C-1", "status": "open"}
    assert o["safe_output_hash"] == rt._sha(o["safe_output"])
    assert "ssn" not in o["safe_output"]


def test_clean_outcome_safe_projection_matched(gate):
    o = k.clean_outcome(gate)
    assert o["safe_output_projection"]["projection_status"] == \
        "SAFE_PROJECTION_MATCHED"


def test_adverse_outcome_surfaces_no_output(gate):
    """A blocked outcome surfaces safe_output {} (no output on non-complete),
    and the hash is the hash of the empty output."""
    b5, b5r, snap = k.setup(gate)
    o = k.prepare(gate, b5, b5r, snap, declared_entropy=["random"])
    assert o["runtime_status"] != "RUNTIME_READ_ONLY_COMPLETED"
    # No output is surfaced on a non-complete outcome.
    assert o["safe_output"] == {}
    assert isinstance(o["safe_output_hash"], str) and o["safe_output_hash"]


def test_outcome_honesty_flags(gate):
    o = k.clean_outcome(gate)
    assert o["read_only"] is True
    assert o["is_external"] is False
    assert o["produced_external_effect"] is False
    assert o["is_execution"] is False


_FORBIDDEN_LEAK_KEYS = {"raw_payload", "payload", "approval_ref", "consent_ref",
                        "provider_result", "execution_authority",
                        "grants_execution", "ssn", "email", "credential"}


def test_safe_endpoint_no_leak(gate):
    rid, _ = gate.prepared_runtime()
    r = gate.rt(rid, path="/safe")
    assert r.status_code == 200
    body = r.json()
    assert body["read_only"] is True
    assert body["produced_external_effect"] is False
    assert body["safe_output"] == {"case_id": "C-1", "status": "open"}
    assert not (_FORBIDDEN_LEAK_KEYS & set(body["safe_output"]))


def test_safe_endpoint_viewer_redacted(gate):
    rid, _ = gate.prepared_runtime()
    r = gate.rt(rid, path="/safe", actor=VIEWER)
    assert r.status_code == 200
    body = r.json()
    assert body["safe_output"] == {}
    assert body["all_signals"] == []


def test_output_subfield_endpoints(gate):
    rid, _ = gate.prepared_runtime()
    cases = {
        "/safe-output-projection": "safe_output_projection",
        "/output-non-exfiltration": "output_non_exfiltration_gate",
        "/output-taint": "output_taint_lattice",
        "/data-diode": "data_diode_output_gate",
    }
    for path, field in cases.items():
        r = gate.rt(rid, path=path)
        assert r.status_code == 200, path
        assert field in r.json(), path
        assert r.json()[field] is not None, path


def test_output_endpoints_report_clean_statuses(gate):
    rid, _ = gate.prepared_runtime()
    assert gate.rt(rid, path="/data-diode").json()[
        "data_diode_output_gate"]["diode_status"] == \
        "DATA_DIODE_OUTPUT_ALLOWED_SAFE_ONLY"
    assert gate.rt(rid, path="/output-non-exfiltration").json()[
        "output_non_exfiltration_gate"]["gate_status"] == "NO_OUTPUT_EXFILTRATION"
    assert gate.rt(rid, path="/safe-output-projection").json()[
        "safe_output_projection"]["projection_status"] == \
        "SAFE_PROJECTION_MATCHED"

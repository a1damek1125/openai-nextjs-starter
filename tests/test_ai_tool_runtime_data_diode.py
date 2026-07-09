"""TOOL-B6: data-diode output gate, output taint lattice, non-exfiltration and
safe-output projection. One-way, safe-only output; any leak is detected and the
diode blocks; honesty labels / descriptive text are NOT leaks."""
import pytest
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def test_clean_data_diode_one_way(gate):
    o = k.clean_outcome(gate)
    diode = o["data_diode_output_gate"]
    assert diode["diode_status"] == "DATA_DIODE_OUTPUT_ALLOWED_SAFE_ONLY"
    assert diode["one_way"] is True
    assert diode["reverse_flow_possible"] is False


def test_clean_output_taint_within_lattice(gate):
    o = k.clean_outcome(gate)
    taint = o["output_taint_lattice"]
    assert taint["lattice_status"] == "TAINT_WITHIN_LATTICE"
    assert taint["highest_taint_level"] <= 1
    assert taint["escaped_taint_classes"] == []


def test_clean_non_exfiltration(gate):
    o = k.clean_outcome(gate)
    assert o["output_non_exfiltration_gate"]["gate_status"] == \
        "NO_OUTPUT_EXFILTRATION"


@pytest.mark.parametrize("safe_output", [
    {"blob": "this holds a secret token value"},
    {"blob": "Bearer sk-abcdef"},
    {"email": "person@example.test"},
    {"approval_ref": "AP-77"},
    {"provider_result": {"ok": True}},
    {"blob": "tenant:OTHER"},
])
def test_leaky_output_detected(gate, safe_output):
    """Each dangerous value/key is detected -> exfiltration + failed projection."""
    ne = rt.build_non_exfiltration(tenant_id=gate.tid, runtime_request_id="r",
                                   safe_output=safe_output)
    assert ne["gate_status"] == "OUTPUT_EXFILTRATION_DETECTED"
    assert ne["signal"] == "OUTPUT_EXFILTRATION_DETECTED"
    assert ne["detected_leaks"]
    proj = rt.build_safe_output_projection(
        tenant_id=gate.tid, runtime_request_id="r", safe_output=safe_output,
        redaction_policy_hash="h")
    assert proj["projection_status"] == "SAFE_PROJECTION_FAILED"
    assert proj["signal"] == "SAFE_OUTPUT_PROJECTION_FAILED"


def test_honesty_labels_not_a_leak(gate):
    """Descriptive honesty-label text is NOT treated as exfiltration."""
    safe = {"honesty_labels": ["READ_ONLY_INTERNAL_RUNTIME_ONLY"],
            "case_id": "C-1"}
    ne = rt.build_non_exfiltration(tenant_id=gate.tid, runtime_request_id="r",
                                   safe_output=safe)
    assert ne["gate_status"] == "NO_OUTPUT_EXFILTRATION"
    assert ne["detected_leaks"] == []
    proj = rt.build_safe_output_projection(
        tenant_id=gate.tid, runtime_request_id="r", safe_output=safe,
        redaction_policy_hash="h")
    assert proj["projection_status"] == "SAFE_PROJECTION_MATCHED"


def test_data_diode_blocks_when_non_exfiltration_fails(gate):
    diode = rt.build_data_diode(
        tenant_id=gate.tid, runtime_request_id="r", safe_output={"email": "x"},
        non_exfiltration_ok=False, taint_ok=True)
    assert diode["diode_status"] == "DATA_DIODE_OUTPUT_BLOCKED"
    assert diode["signal"] == "DATA_DIODE_OUTPUT_GATE_FAILED"


def test_data_diode_blocks_when_taint_escapes(gate):
    diode = rt.build_data_diode(
        tenant_id=gate.tid, runtime_request_id="r", safe_output={},
        non_exfiltration_ok=True, taint_ok=False)
    assert diode["diode_status"] == "DATA_DIODE_OUTPUT_BLOCKED"
    assert diode["signal"] == "DATA_DIODE_OUTPUT_GATE_FAILED"


def test_data_diode_allows_when_both_ok(gate):
    diode = rt.build_data_diode(
        tenant_id=gate.tid, runtime_request_id="r",
        safe_output={"case_id": "C-1"}, non_exfiltration_ok=True, taint_ok=True)
    assert diode["diode_status"] == "DATA_DIODE_OUTPUT_ALLOWED_SAFE_ONLY"
    assert diode["signal"] is None


def test_diode_and_gates_deterministic(gate):
    safe = {"email": "leak@example.test"}
    a = rt.build_non_exfiltration(tenant_id=gate.tid, runtime_request_id="r",
                                  safe_output=safe)
    b = rt.build_non_exfiltration(tenant_id=gate.tid, runtime_request_id="r",
                                  safe_output=safe)
    assert a["output_non_exfiltration_gate_hash"] == \
        b["output_non_exfiltration_gate_hash"]
    d1 = rt.build_data_diode(tenant_id=gate.tid, runtime_request_id="r",
                             safe_output={}, non_exfiltration_ok=True,
                             taint_ok=True)
    d2 = rt.build_data_diode(tenant_id=gate.tid, runtime_request_id="r",
                             safe_output={}, non_exfiltration_ok=True,
                             taint_ok=True)
    assert d1["data_diode_output_gate_hash"] == d2["data_diode_output_gate_hash"]

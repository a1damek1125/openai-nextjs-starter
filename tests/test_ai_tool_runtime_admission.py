"""TOOL-B6: adapter capability calculus + capability firewall admission.

A registered local read-only adapter maps to READ_ONLY_MINIMAL and is allowed by
the firewall. Any dangerous capability (write/network/provider/mcp/llm/
credential), an unknown adapter kind, or a sealed-hash drift blocks the request.
"""
import pytest

from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def _clean_adapter():
    return rt.build_adapter_descriptor(
        adapter_id="adp", adapter_kind="field_projection",
        allowed_sources=["case_id", "status"],
        allowed_projection=["case_id", "status"])


def test_capability_calculus_clean_is_read_only_minimal():
    adapter = _clean_adapter()
    calc = rt.build_capability_calculus(
        tenant_id="t", runtime_request_id="r", adapter=adapter)
    assert calc["calculus_status"] == "READ_ONLY_MINIMAL"
    assert calc["dangerous_capabilities"] == []
    assert calc["unknown_kind"] is False


def test_adapter_firewall_clean_allows_read_only():
    adapter = _clean_adapter()
    fw = rt.build_adapter_firewall(
        tenant_id="t", runtime_request_id="r", adapter=adapter,
        sealed_adapter_hash=None)
    assert fw["firewall_status"] == "ADAPTER_ALLOWED_READ_ONLY"
    assert fw["signal"] is None
    assert fw["firewall_findings"] == []


@pytest.mark.parametrize("cap,signal", [
    ("write", "ADAPTER_WRITE_CAPABLE"),
    ("network", "ADAPTER_NETWORK_CAPABLE"),
    ("provider", "ADAPTER_PROVIDER_BACKED"),
    ("mcp", "ADAPTER_MCP_CAPABLE"),
    ("llm", "ADAPTER_LLM_CAPABLE"),
    ("credential", "ADAPTER_CREDENTIAL_REQUIRED"),
])
def test_adapter_capability_maps_to_blocking_signal(gate, cap, signal):
    b5, b5r, snap = k.setup(gate)
    o = k.prepare(gate, b5, b5r, snap, adapter_caps={cap: True})
    assert signal in o["all_signals"]
    assert o["runtime_status"] == "RUNTIME_BLOCKED"


def test_unknown_adapter_kind_is_unknown_capability(gate):
    b5, b5r, snap = k.setup(gate)
    o = k.prepare(gate, b5, b5r, snap, adapter_kind="weird")
    assert "UNKNOWN_CAPABILITY" in o["all_signals"]
    assert o["adapter_capability_firewall"]["firewall_status"] == \
        "ADAPTER_BLOCKED"


def test_sealed_adapter_hash_mismatch_is_capability_drift(gate):
    b5, b5r, snap = k.setup(gate)
    o = k.prepare(gate, b5, b5r, snap, sealed_adapter_hash="WRONG")
    assert "ADAPTER_CAPABILITY_DRIFT" in o["all_signals"]
    assert o["adapter_capability_firewall"]["capability_drift_detected"] is True


def test_forbidden_adapter_caps_cover_all_dangerous_capabilities():
    required = {"write", "network", "credential", "provider", "mcp", "llm",
                "external", "execute", "mutate", "token"}
    assert required <= rt.FORBIDDEN_ADAPTER_CAPS

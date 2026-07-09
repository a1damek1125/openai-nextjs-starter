"""TOOL-B6 read-path runtime: boundary surface diff + escape sentinel.

Any inserted runtime surface (network/execute/provider/... path or a dangerous
adapter capability) is detected and blocks the read path fail-closed.
"""
import pytest
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k

_SURFACE_FLAGS = [
    "network_path", "execute_endpoint", "provider_call_path", "mcp_path",
    "llm_path", "token_path", "credential_path", "write_endpoint",
    "mutate_capability", "external_path",
]


def test_surface_diff_clean(gate):
    sd = rt.build_surface_diff(tenant_id=gate.tid, runtime_request_id="r",
                               observed_surface={}, adapter={})
    assert sd["diff_status"] == "SURFACE_CLEAR"
    assert sd["detected_surface"] == []
    assert sd["signal"] is None


@pytest.mark.parametrize("flag", _SURFACE_FLAGS)
def test_observed_surface_detected_blocks(gate, flag):
    b5, b5r, snap = k.setup(gate)
    o = k.prepare(gate, b5, b5r, snap, observed_surface={flag: True})
    assert o["runtime_status"] == "RUNTIME_BLOCKED"
    assert o["dominant_signal"] == "RUNTIME_SURFACE_DIFF_DETECTED"
    assert flag in o["runtime_surface_diff"]["detected_surface"]


def test_escape_sentinel_clean(gate):
    o = k.clean_outcome(gate)
    esc = o["runtime_escape_sentinel"]
    assert esc["escape_detected"] is False
    assert esc["signal"] is None


def test_escape_sentinel_detects_surface(gate):
    eff = rt.build_effect_ledger(
        tenant_id=gate.tid, runtime_request_id="r",
        operations=[{"op": "READ_SNAPSHOT_FIELD",
                     "capability": "READ_SNAPSHOT_FIELD"}])
    sd = rt.build_surface_diff(tenant_id=gate.tid, runtime_request_id="r",
                               observed_surface={"network_path": True},
                               adapter={})
    esc = rt.build_escape_sentinel(
        tenant_id=gate.tid, runtime_request_id="r",
        operations=[{"capability": "READ_SNAPSHOT_FIELD"}],
        surface_diff=sd, effect_ledger=eff)
    assert esc["escape_detected"] is True
    assert esc["signal"] == "RUNTIME_ESCAPE_DETECTED"


def test_adapter_write_capability_surfaces_as_adapter_write(gate):
    adapter = rt.build_adapter_descriptor(
        adapter_id="a", adapter_kind="count", allowed_sources=[],
        allowed_projection=[], capabilities={"write": True})
    sd = rt.build_surface_diff(tenant_id=gate.tid, runtime_request_id="r",
                               observed_surface={}, adapter=adapter)
    assert "adapter_write" in sd["detected_surface"]
    assert sd["signal"] == "RUNTIME_SURFACE_DIFF_DETECTED"


def test_surface_and_escape_endpoints(gate):
    rid, _ = gate.prepared_runtime()
    sd = gate.rt(rid, path="/surface-diff")
    assert sd.status_code == 200
    assert sd.json()["runtime_surface_diff"]["diff_status"] == "SURFACE_CLEAR"
    esc = gate.rt(rid, path="/escape-sentinel")
    assert esc.status_code == 200
    assert esc.json()["runtime_escape_sentinel"]["escape_detected"] is False
    nesc = gate.rt(rid, path="/non-escalation")
    assert nesc.status_code == 200
    assert nesc.json()["runtime_non_escalation_proof"]["status"] == \
        "NON_ESCALATED"


def test_surface_diff_hash_deterministic(gate):
    sd1 = rt.build_surface_diff(tenant_id=gate.tid, runtime_request_id="r",
                                observed_surface={"network_path": True},
                                adapter={})
    sd2 = rt.build_surface_diff(tenant_id=gate.tid, runtime_request_id="r",
                                observed_surface={"network_path": True},
                                adapter={})
    assert sd1["runtime_surface_diff_hash"] == sd2["runtime_surface_diff_hash"]
    assert rt._core_hash(sd1, "runtime_surface_diff_hash") == \
        sd1["runtime_surface_diff_hash"]

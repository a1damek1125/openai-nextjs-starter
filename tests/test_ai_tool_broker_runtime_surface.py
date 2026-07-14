"""TOOL-B5 runtime-surface diff.

The null broker has NO runtime surface. If an observed surface exposes any
executable capability (execute endpoint, provider/token/network path, callable
adapter, side-effect capability, ...) the request quarantines. Executes nothing.
"""
from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k

WATCHED = [
    "provider_call_path", "token_path", "external_network_path",
    "adapter_callable", "side_effect_capability", "callable",
    "runtime_enabled", "network_enabled",
]


def test_clean_runtime_surface_is_clear(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o = k.prepare(gate, d, pobj, head, quality, contract, cert)
    assert o["broker_status"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"
    diff = o["runtime_surface_diff"]
    assert diff["diff_status"] == "SURFACE_CLEAR"
    assert diff["detected_runtime_surface"] == []
    assert diff["signal"] is None


def test_execute_endpoint_surface_quarantines(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o = k.prepare(gate, d, pobj, head, quality, contract, cert,
                  observed_surface={"execute_endpoint": True})
    assert o["broker_status"] == "QUARANTINED"
    assert o["dominant_signal"] == "RUNTIME_SURFACE_DIFF_DETECTED"
    diff = o["runtime_surface_diff"]
    assert diff["diff_status"] == "RUNTIME_SURFACE_DETECTED"
    assert "execute_endpoint" in diff["detected_runtime_surface"]


def test_provider_call_path_surface_via_prepare_quarantines(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o = k.prepare(gate, d, pobj, head, quality, contract, cert,
                  observed_surface={"provider_call_path": True})
    assert o["broker_status"] == "QUARANTINED"
    assert o["dominant_signal"] == "RUNTIME_SURFACE_DIFF_DETECTED"


def test_each_watched_flag_is_detected():
    for flag in WATCHED:
        diff = b.build_runtime_surface_diff(
            tenant_id="t", broker_request_id="r",
            observed_surface={flag: True})
        assert diff["diff_status"] == "RUNTIME_SURFACE_DETECTED", flag
        assert diff["signal"] == "RUNTIME_SURFACE_DIFF_DETECTED", flag
        assert diff["detected_runtime_surface"] == [flag], flag


def test_detected_runtime_surface_lists_the_flag():
    diff = b.build_runtime_surface_diff(
        tenant_id="t", broker_request_id="r",
        observed_surface={"token_path": True, "irrelevant_flag": True})
    # only watched flags surface; unknown keys are ignored.
    assert diff["detected_runtime_surface"] == ["token_path"]


def test_watched_flags_cover_every_known_surface():
    diff = b.build_runtime_surface_diff(
        tenant_id="t", broker_request_id="r", observed_surface={})
    assert diff["diff_status"] == "SURFACE_CLEAR"
    for flag in WATCHED + ["execute_endpoint"]:
        assert flag in diff["watched_flags"], flag


def test_runtime_surface_hash_deterministic():
    kw = dict(tenant_id="t", broker_request_id="r",
              observed_surface={"callable": True})
    a = b.build_runtime_surface_diff(**kw)
    a2 = b.build_runtime_surface_diff(**kw)
    assert a["runtime_surface_diff_hash"] == a2["runtime_surface_diff_hash"]

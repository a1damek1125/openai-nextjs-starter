"""TOOL-B6 v5 exfiltration-defense: side-channel budget seal.

Coarse deterministic buckets (duration / output size / error shape / operation /
read / branch) bound observable side channels. No wall-clock timing is used and
no OS-level side-channel enforcement is claimed: output size and error shape
cannot be used to reveal forbidden data.
"""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k

_BUCKETS = ("duration_bucket", "output_size_bucket", "error_shape_bucket",
            "operation_count_bucket", "read_count_bucket", "branch_count_bucket")


def _wide_fields():
    f = {"ssn": {"value": "999-99-9999", "data_class": "CUSTOMER_SENSITIVE"}}
    for i in range(6):
        f[f"pub{i}"] = {"value": f"value-number-{i}", "data_class": "PUBLIC"}
    return f


def test_clean_seal_is_sealed_with_coarse_buckets(gate):
    seal = rt.build_side_channel_seal(
        tenant_id=gate.tid, runtime_request_id="rt1",
        safe_output={"case_id": "C-1", "status": "open"}, operations=[],
        read_set=[], policy=None, error_shape=0)
    assert seal["seal_status"] == "SIDE_CHANNEL_SEALED"
    for b in _BUCKETS:
        assert b in seal and isinstance(seal[b], int)


def test_output_bucket_budget_exceeded_via_prepare(gate):
    fields = _wide_fields()
    sources = [f for f in fields if f != "ssn"]
    b5, b5r, snap = k.setup(gate, fields=fields)
    o = k.prepare(gate, b5, b5r, snap, adapter_kind="field_projection",
                  allowed_sources=sources, allowed_projection=sources,
                  requested_sources=sources, requested_projection=sources,
                  policy={"side_channel_output_bucket_max": 0})
    seal = o["side_channel_budget_seal"]
    assert seal["seal_status"] == "SIDE_CHANNEL_BUDGET_EXCEEDED", \
        "output size / error shape cannot reveal forbidden data"
    assert "OUTPUT_SIZE_BUCKET" in seal["side_channel_budget_violations"]
    assert o["dominant_signal"] == "SIDE_CHANNEL_BUDGET_EXCEEDED"


def test_error_shape_bucket_budget_exceeded(gate):
    seal = rt.build_side_channel_seal(
        tenant_id=gate.tid, runtime_request_id="rt1",
        safe_output={"a": 1}, operations=[], read_set=[],
        policy={"side_channel_error_bucket_max": 0}, error_shape=5)
    assert seal["seal_status"] == "SIDE_CHANNEL_BUDGET_EXCEEDED", \
        "output size / error shape cannot reveal forbidden data"
    assert "ERROR_SHAPE_BUCKET" in seal["side_channel_budget_violations"]


def test_seal_note_disclaims_wall_clock_and_os_enforcement(gate):
    seal = rt.build_side_channel_seal(
        tenant_id=gate.tid, runtime_request_id="rt1", safe_output={"a": 1},
        operations=[], read_set=[], policy=None, error_shape=0)
    assert "no wall-clock timing" in seal["note"]
    assert "no OS-level side-channel enforcement" in seal["note"]
    recomputed = rt._core_hash(seal, "side_channel_budget_seal_hash")
    assert recomputed == seal["side_channel_budget_seal_hash"]


def test_side_channel_and_read_amplification_endpoints(gate):
    rid, _ = gate.prepared_runtime()
    sc = gate.rt(rid, path="/side-channel-budget")
    ra = gate.rt(rid, path="/read-amplification")
    assert sc.status_code == 200 and ra.status_code == 200
    assert sc.json()["side_channel_budget_seal"]["seal_status"] == \
        "SIDE_CHANNEL_SEALED"
    assert ra.json()["read_amplification_guard"]["guard_status"] == \
        "READ_AMPLIFICATION_CLEAR"

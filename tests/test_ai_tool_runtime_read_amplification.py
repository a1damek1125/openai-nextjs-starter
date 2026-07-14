"""TOOL-B6 v5 exfiltration-defense: read-amplification guard.

Repeated read-only calls that reconstruct forbidden data by overlapping read
sets across many requests are detected (READ_AMPLIFICATION_DETECTED) and blocked
or flagged for review.
"""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def _read_set(*paths):
    return [{"field_path": p} for p in paths]


def test_clean_guard_is_clear(gate):
    guard = rt.build_read_amplification(
        tenant_id=gate.tid, runtime_request_id="rt1",
        read_set=_read_set("case_id", "status"), related_requests=[],
        policy=None)
    assert guard["guard_status"] == "READ_AMPLIFICATION_CLEAR"
    assert guard["amplification_detected"] is False
    assert guard["signal"] is None


def test_many_related_requests_detected_via_prepare(gate):
    b5, b5r, snap = k.setup(gate)
    related = [{"runtime_request_id": f"r{i}",
                "read_paths": ["case_id", "status"], "snapshot_id": "s"}
               for i in range(6)]
    o = k.prepare(gate, b5, b5r, snap, related_requests=related)
    assert o["read_amplification_guard"]["guard_status"] == \
        "READ_AMPLIFICATION_DETECTED", \
        "repeated read-only calls reconstructing forbidden data block or " \
        "require review"
    assert o["dominant_signal"] == "READ_AMPLIFICATION_DETECTED"
    assert o["runtime_status"] not in rt.POSITIVE_STATUSES


def test_overlapping_read_sets_detected(gate):
    # Four requests each re-reading case_id => overlap total exceeds the
    # overlap budget (3) even though the request count is under the limit.
    related = [{"runtime_request_id": f"r{i}", "read_paths": ["case_id"],
                "snapshot_id": "s"} for i in range(4)]
    guard = rt.build_read_amplification(
        tenant_id=gate.tid, runtime_request_id="rt1",
        read_set=_read_set("case_id", "status"), related_requests=related,
        policy=None)
    assert guard["overlapping_read_count"] == 4
    assert guard["guard_status"] == "READ_AMPLIFICATION_DETECTED", \
        "repeated read-only calls reconstructing forbidden data block or " \
        "require review"


def test_guard_hash_deterministic(gate):
    a = rt.build_read_amplification(
        tenant_id=gate.tid, runtime_request_id="rt1",
        read_set=_read_set("case_id", "status"), related_requests=[],
        policy=None)
    b = rt.build_read_amplification(
        tenant_id=gate.tid, runtime_request_id="rt1",
        read_set=_read_set("case_id", "status"), related_requests=[],
        policy=None)
    assert a["read_amplification_guard_hash"] == \
        b["read_amplification_guard_hash"]
    recomputed = rt._core_hash(a, "read_amplification_guard_hash")
    assert recomputed == a["read_amplification_guard_hash"]


def test_read_amplification_endpoint(gate):
    rid, _ = gate.prepared_runtime()
    resp = gate.rt(rid, path="/read-amplification")
    assert resp.status_code == 200
    assert resp.json()["read_amplification_guard"]["guard_status"] == \
        "READ_AMPLIFICATION_CLEAR"

"""TOOL-B6: frozen snapshot model + snapshot seal check."""
import copy

from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def _seal(snap, sealed=None, scopes=None):
    return rt.build_snapshot_seal_check(
        tenant_id="t", runtime_request_id="r", snapshot=snap,
        sealed_snapshot_hash=sealed if sealed is not None else (
            snap or {}).get("snapshot_hash"),
        allowed_scopes=scopes)


def test_snapshot_is_immutable_and_hashed(gate):
    _, _, snap = k.setup(gate)
    assert snap["immutable"] is True
    assert snap["snapshot_hash"]
    assert isinstance(snap["snapshot_hash"], str)


def test_snapshot_field_count_matches(gate):
    _, _, snap = k.setup(gate)
    # default clean_fields has 3 fields (case_id/status PUBLIC + ssn sensitive).
    assert snap["field_count"] == 3
    assert snap["field_count"] == len(snap["fields"])


def test_snapshot_default_provenance_dag(gate):
    _, _, snap = k.setup(gate)
    dag = snap["provenance_dag"]
    assert dag["nodes"] == ["ORIGIN"]
    assert dag["edges"] == []
    assert dag["dag_kind"] == "LOCAL_FROZEN"


def test_seal_clean_matches(gate):
    _, _, snap = k.setup(gate)
    check = _seal(snap, scopes=["case"])
    assert check["seal_status"] == "SEAL_MATCHED"
    assert check["signal"] is None


def test_seal_snapshot_missing(gate):
    check = _seal(None, sealed=None)
    assert check["signal"] == "SNAPSHOT_MISSING"
    assert check["seal_status"] == "SEAL_FAILED"


def test_seal_mutable_snapshot(gate):
    _, _, snap = k.setup(gate)
    check = _seal({**snap, "immutable": False})
    assert check["signal"] == "SNAPSHOT_MUTABLE"


def test_seal_hash_mismatch(gate):
    _, _, snap = k.setup(gate)
    check = _seal(snap, sealed="WRONG")
    assert check["signal"] == "SNAPSHOT_HASH_MISMATCH"


def test_seal_scope_denied(gate):
    _, _, snap = k.setup(gate)
    check = _seal(snap, scopes=["other"])
    assert check["signal"] == "SNAPSHOT_SCOPE_DENIED"


def test_prepare_mutable_snapshot_is_stale(gate):
    b5, b5r, snap = k.setup(gate)
    o = k.prepare(gate, b5, b5r, {**snap, "immutable": False})
    assert o["runtime_status"] == "RUNTIME_STALE"
    assert o["dominant_signal"] == "SNAPSHOT_MUTABLE"


def test_prepare_hash_mismatch_and_scope_blocked(gate):
    b5, b5r, snap = k.setup(gate)
    o1 = k.prepare(gate, b5, b5r, snap, sealed_snapshot_hash="WRONG")
    assert o1["runtime_status"] == "RUNTIME_BLOCKED"
    assert o1["dominant_signal"] == "SNAPSHOT_HASH_MISMATCH"
    o2 = k.prepare(gate, b5, b5r, snap, allowed_scopes=["other"])
    assert o2["runtime_status"] == "RUNTIME_BLOCKED"
    assert o2["dominant_signal"] == "SNAPSHOT_SCOPE_DENIED"

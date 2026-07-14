"""TOOL-B6: snapshot epoch vector + temporal snapshot isolation."""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def _vec(snap):
    return rt.build_snapshot_epoch_vector(tenant_id="t", runtime_request_id="r",
                                          snapshot=snap)


def _iso(snap, vec, requested_epoch):
    return rt.build_temporal_isolation(
        tenant_id="t", runtime_request_id="r", snapshot=snap,
        epoch_vector=vec, requested_epoch=requested_epoch)


def test_epoch_vector_single(gate):
    _, _, snap = k.setup(gate, epoch="5")
    vec = _vec(snap)
    assert vec["single_epoch"] is True
    assert vec["epoch_vector_status"] == "EPOCH_SINGLE"
    assert vec["epochs"] == ["5"]
    assert vec["signal"] is None


def test_temporal_isolated_when_epoch_matches(gate):
    _, _, snap = k.setup(gate, epoch="5")
    vec = _vec(snap)
    iso = _iso(snap, vec, "5")
    assert iso["isolation_status"] == "TEMPORAL_ISOLATED"
    assert iso["signal"] is None
    assert iso["epoch_mismatch"] is False


def test_temporal_failed_when_epoch_differs(gate):
    _, _, snap = k.setup(gate, epoch="5")
    vec = _vec(snap)
    iso = _iso(snap, vec, "9")
    assert iso["isolation_status"] == "TEMPORAL_FAILED"
    assert iso["signal"] == "TEMPORAL_SNAPSHOT_ISOLATION_FAILED"
    assert iso["epoch_mismatch"] is True


def test_prepare_requested_epoch_mismatch_fails(gate):
    b5, b5r, snap = k.setup(gate, epoch="5")
    o = k.prepare(gate, b5, b5r, snap, requested_epoch="9")
    assert o["runtime_status"] == "RUNTIME_BLOCKED"
    assert o["dominant_signal"] == "TEMPORAL_SNAPSHOT_ISOLATION_FAILED"


def test_epoch_vector_hash_deterministic(gate):
    _, _, snap = k.setup(gate, epoch="5")
    v1 = _vec(snap)
    v2 = _vec(snap)
    assert v1["snapshot_epoch_vector_hash"] == v2["snapshot_epoch_vector_hash"]
    assert v1["snapshot_epoch_vector_hash"] == rt._core_hash(
        v1, "snapshot_epoch_vector_hash")


def test_isolation_hash_deterministic(gate):
    _, _, snap = k.setup(gate, epoch="5")
    vec = _vec(snap)
    i1 = _iso(snap, vec, "5")
    i2 = _iso(snap, vec, "5")
    assert i1["temporal_snapshot_isolation_hash"] == \
        i2["temporal_snapshot_isolation_hash"]
    assert i1["temporal_snapshot_isolation_hash"] == rt._core_hash(
        i1, "temporal_snapshot_isolation_hash")


def test_isolation_hash_changes_with_requested_epoch(gate):
    _, _, snap = k.setup(gate, epoch="5")
    vec = _vec(snap)
    matched = _iso(snap, vec, "5")
    mismatched = _iso(snap, vec, "9")
    assert matched["temporal_snapshot_isolation_hash"] != \
        mismatched["temporal_snapshot_isolation_hash"]


def test_decision_hash_changes_when_snapshot_epoch_changes(gate):
    b5, b5r, snap5 = k.setup(gate, epoch="5")
    snap6 = rt.build_snapshot(snapshot_id="snap1", tenant_id=gate.tid,
                              epoch="6", scope="case", fields=k.clean_fields())
    o5 = k.prepare(gate, b5, b5r, snap5, requested_epoch="5")
    o6 = k.prepare(gate, b5, b5r, snap6, requested_epoch="6")
    assert o5["runtime_status"] == "RUNTIME_READ_ONLY_COMPLETED"
    assert o6["runtime_status"] == "RUNTIME_READ_ONLY_COMPLETED"
    assert o5["runtime_decision_hash"] != o6["runtime_decision_hash"]

"""TOOL-B6: read-set ledger, completeness, and snapshot attestation."""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def _read(snap, sources=("case_id", "status")):
    adapter = rt.build_adapter_descriptor(
        adapter_id="adp", adapter_kind="field_projection",
        allowed_sources=list(sources), allowed_projection=list(sources))
    qp = rt.build_query_plan_normal_form(
        tenant_id="t", runtime_request_id="r", adapter=adapter, snapshot=snap,
        requested_sources=list(sources), requested_projection=list(sources))
    read_set, _raw, _safe, prov, _ops = rt._execute_read_only(
        adapter=adapter, snapshot=snap, query_plan=qp)
    return read_set, prov


def _ledger(read_set, snap):
    return rt.build_read_set_ledger(tenant_id="t", runtime_request_id="r",
                                    read_set=read_set, snapshot=snap)


def test_ledger_records_read_entries(gate):
    _, _, snap = k.setup(gate)
    read_set, _ = _read(snap)
    led = _ledger(read_set, snap)
    assert led["read_count"] == 2
    assert led["signal"] is None
    entry = led["read_entries"][0]
    for key in ("field_path", "data_class", "value_hash", "snapshot_id",
                "epoch"):
        assert key in entry


def test_ledger_binds_read_entries_to_snapshot(gate):
    _, _, snap = k.setup(gate)
    read_set, _ = _read(snap)
    led = _ledger(read_set, snap)
    assert led["snapshot_id"] == snap["snapshot_id"]
    assert led["snapshot_epoch"] == snap["epoch"]
    for entry in led["read_entries"]:
        assert entry["snapshot_id"] == snap["snapshot_id"]
        assert entry["epoch"] == snap["epoch"]


def test_read_set_hash_deterministic(gate):
    _, _, snap = k.setup(gate)
    read_set, _ = _read(snap)
    l1 = _ledger(read_set, snap)
    l2 = _ledger(read_set, snap)
    assert l1["read_set_hash"] == l2["read_set_hash"]
    assert l1["read_set_ledger_hash"] == rt._core_hash(
        l1, "read_set_ledger_hash")


def test_completeness_clean(gate):
    _, _, snap = k.setup(gate)
    read_set, prov = _read(snap)
    comp = rt.build_read_set_completeness(
        tenant_id="t", runtime_request_id="r", read_set=read_set,
        provenance_edges=prov)
    assert comp["complete"] is True
    assert comp["signal"] is None


def test_completeness_incomplete_when_edge_references_unread_entry(gate):
    _, _, snap = k.setup(gate)
    read_set, prov = _read(snap)
    bad = prov + [{"output_field": "x", "read_entry_id": "r_ghost",
                   "transform": "identity"}]
    comp = rt.build_read_set_completeness(
        tenant_id="t", runtime_request_id="r", read_set=read_set,
        provenance_edges=bad)
    assert comp["complete"] is False
    assert comp["signal"] == "READ_SET_INCOMPLETE"
    assert "r_ghost" in comp["missing_entries"]


def test_attestation_bound_to_snapshot(gate):
    _, _, snap = k.setup(gate)
    read_set, _ = _read(snap)
    led = _ledger(read_set, snap)
    att = rt.build_read_set_attestation(
        tenant_id="t", runtime_request_id="r", read_set_ledger=led,
        snapshot=snap)
    assert att["bound_to_snapshot"] is True
    assert att["attestation_status"] == "READ_SET_ATTESTED"
    assert att["signal"] is None


def test_attestation_mismatch_on_wrong_snapshot(gate):
    _, _, snap = k.setup(gate)
    read_set, _ = _read(snap)
    led = _ledger(read_set, snap)
    other = rt.build_snapshot(snapshot_id="OTHER", tenant_id=gate.tid,
                              epoch="5", scope="case", fields=k.clean_fields())
    att = rt.build_read_set_attestation(
        tenant_id="t", runtime_request_id="r", read_set_ledger=led,
        snapshot=other)
    assert att["bound_to_snapshot"] is False
    assert att["signal"] == "READ_SET_SNAPSHOT_MISMATCH"


def test_attestation_hash_deterministic(gate):
    _, _, snap = k.setup(gate)
    read_set, _ = _read(snap)
    led = _ledger(read_set, snap)
    a1 = rt.build_read_set_attestation(
        tenant_id="t", runtime_request_id="r", read_set_ledger=led,
        snapshot=snap)
    a2 = rt.build_read_set_attestation(
        tenant_id="t", runtime_request_id="r", read_set_ledger=led,
        snapshot=snap)
    assert a1["read_set_attestation_capsule_hash"] == \
        a2["read_set_attestation_capsule_hash"]


def test_clean_outcome_read_set_only_public_fields(gate):
    o = k.clean_outcome(gate)
    led = o["read_set_ledger"]
    paths = [e["field_path"] for e in led["read_entries"]]
    assert sorted(paths) == ["case_id", "status"]
    assert "ssn" not in paths
    assert led["signal"] is None
    assert o["read_set_completeness_proof"]["signal"] is None
    assert o["read_set_attestation_capsule"]["attestation_status"] == \
        "READ_SET_ATTESTED"

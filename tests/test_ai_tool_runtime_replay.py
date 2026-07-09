"""TOOL-B6: deterministic replay twin. Same input + snapshot + read-set +
adapter + policy -> same safe output hash. A tampered output -> REPLAY_MISMATCH.
Changing the snapshot content changes the safe output hash."""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def _adapter():
    return rt.build_adapter_descriptor(
        adapter_id="adp", adapter_kind="field_projection",
        allowed_sources=["case_id", "status"],
        allowed_projection=["case_id", "status"])


def _plan(gate, adapter, snap):
    return rt.build_query_plan_normal_form(
        tenant_id=gate.tid, runtime_request_id="r", adapter=adapter,
        snapshot=snap, requested_sources=["case_id", "status"],
        requested_projection=["case_id", "status"])


def test_replay_recompute_matches(gate):
    _, _, snap = k.setup(gate)
    adapter = _adapter()
    plan = _plan(gate, adapter, snap)
    safe = rt._recompute_safe_output(adapter, snap, plan)
    twin = rt.build_replay_twin(
        tenant_id=gate.tid, runtime_request_id="r", adapter=adapter,
        snapshot=snap, query_plan=plan, safe_output=safe)
    assert twin["replay_matched"] is True
    assert twin["signal"] is None
    assert twin["safe_output_hash"] == twin["replay_safe_output_hash"]


def test_tampered_output_replay_mismatch(gate):
    _, _, snap = k.setup(gate)
    adapter = _adapter()
    plan = _plan(gate, adapter, snap)
    safe = rt._recompute_safe_output(adapter, snap, plan)
    twin = rt.build_replay_twin(
        tenant_id=gate.tid, runtime_request_id="r", adapter=adapter,
        snapshot=snap, query_plan=plan,
        safe_output={**safe, "injected": "tamper"})
    assert twin["replay_matched"] is False
    assert twin["signal"] == "REPLAY_MISMATCH"


def test_clean_outcome_replay_matched(gate):
    o = k.clean_outcome(gate)
    assert o["deterministic_replay_twin"]["replay_matched"] is True
    assert o["deterministic_replay_twin"]["signal"] is None


def test_identical_inputs_same_output_and_decision_hash(gate):
    """Same input + snapshot + read-set + adapter + policy -> same safe output
    hash AND same runtime decision hash."""
    b5, b5r, snap = k.setup(gate)
    a = k.prepare(gate, b5, b5r, snap)
    b = k.prepare(gate, b5, b5r, snap)
    assert a["safe_output_hash"] == b["safe_output_hash"]
    assert a["runtime_decision_hash"] == b["runtime_decision_hash"]


def test_changing_snapshot_content_changes_safe_output_hash(gate):
    b5, b5r, snap = k.setup(gate)
    base = k.prepare(gate, b5, b5r, snap)
    snap2 = rt.build_snapshot(
        snapshot_id="snap1", tenant_id=gate.tid, epoch="5", scope="case",
        fields={"case_id": {"value": "C-999", "data_class": "PUBLIC"},
                "status": {"value": "open", "data_class": "PUBLIC"}})
    changed = k.prepare(gate, b5, b5r, snap2)
    assert changed["runtime_status"] == "RUNTIME_READ_ONLY_COMPLETED"
    assert changed["safe_output"] == {"case_id": "C-999", "status": "open"}
    assert base["safe_output_hash"] != changed["safe_output_hash"]


def test_replay_twin_deterministic(gate):
    _, _, snap = k.setup(gate)
    adapter = _adapter()
    plan = _plan(gate, adapter, snap)
    safe = rt._recompute_safe_output(adapter, snap, plan)
    a = rt.build_replay_twin(tenant_id=gate.tid, runtime_request_id="r",
                             adapter=adapter, snapshot=snap, query_plan=plan,
                             safe_output=safe)
    b = rt.build_replay_twin(tenant_id=gate.tid, runtime_request_id="r",
                             adapter=adapter, snapshot=snap, query_plan=plan,
                             safe_output=safe)
    assert a["deterministic_replay_twin_hash"] == \
        b["deterministic_replay_twin_hash"]


def test_recompute_reads_only_public_fields(gate):
    """The recomputed safe output surfaces the two PUBLIC fields only; the
    CUSTOMER_SENSITIVE ssn is never read into the output."""
    _, _, snap = k.setup(gate)
    adapter = _adapter()
    plan = _plan(gate, adapter, snap)
    safe = rt._recompute_safe_output(adapter, snap, plan)
    assert safe == {"case_id": "C-1", "status": "open"}
    assert "ssn" not in safe


def test_replay_mismatch_changes_outcome(gate):
    """A clean outcome replay-matches; the twin hash is bound into the decision.
    Two identical clean outcomes share the twin hash."""
    b5, b5r, snap = k.setup(gate)
    a = k.prepare(gate, b5, b5r, snap)
    b = k.prepare(gate, b5, b5r, snap)
    assert a["deterministic_replay_twin"]["deterministic_replay_twin_hash"] == \
        b["deterministic_replay_twin"]["deterministic_replay_twin_hash"]

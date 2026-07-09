"""TOOL-B6 v5 exfiltration-defense: canary non-leakage proof.

A field_projection adapter over PUBLIC fields never reads canaries, so the safe
output is identical with or without the injected canaries -> no leak. An adapter
that reads/echoes a canary value, echoes a canary-derived marker, or whose output
correlates with canary presence -> CANARY_LEAK_DETECTED (which no positive status
can override).
"""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k

_MARKER_VALUE = "CANARY-MARKER-7F3A9C"


def _snap(gate, fields=None):
    return rt.build_snapshot(snapshot_id="snap1", tenant_id=gate.tid, epoch="5",
                             scope="case",
                             fields=fields if fields is not None else
                             k.clean_fields())


def _adapter(sources):
    return rt.build_adapter_descriptor(
        adapter_id="adp", adapter_kind="field_projection",
        allowed_sources=sources, allowed_projection=sources)


def _plan(gate, adapter, snapshot, sources):
    return rt.build_query_plan_normal_form(
        tenant_id=gate.tid, runtime_request_id="rt1", adapter=adapter,
        snapshot=snapshot, requested_sources=sources,
        requested_projection=sources)


# --- Clean (public field_projection) -------------------------------------
def test_clean_outcome_canary_non_leakage_matched(gate):
    o = k.clean_outcome(gate)
    proof = o["canary_non_leakage_proof"]
    assert proof["proof_status"] == "CANARY_NON_LEAKAGE_MATCHED"
    assert proof["leak_detected"] is False


def test_clean_adding_canaries_does_not_change_output(gate):
    o = k.clean_outcome(gate)
    proof = o["canary_non_leakage_proof"]
    # No correlation channel: injecting canaries left the output unchanged.
    assert proof["canary_correlation_signals"] == []
    assert proof["detected_leaks"] == []


def test_public_projection_never_reads_canaries(gate):
    snap = _snap(gate)
    h = rt.build_canary_harness(tenant_id=gate.tid, runtime_request_id="rt1",
                                snapshot=snap)
    sources = ["case_id", "status"]
    adapter = _adapter(sources)
    plan = _plan(gate, adapter, h["_canary_snapshot"], sources)
    safe = rt._recompute_safe_output(adapter, h["_canary_snapshot"], plan)
    proof = rt.build_canary_non_leakage(
        tenant_id=gate.tid, runtime_request_id="rt1", harness=h, adapter=adapter,
        query_plan=plan, safe_output=safe)
    assert proof["leak_detected"] is False
    assert proof["proof_status"] == "CANARY_NON_LEAKAGE_MATCHED"
    assert "__canary_secret" not in safe


# --- Leak variants -------------------------------------------------------
def test_canary_value_leak_blocks(gate):
    snap = _snap(gate, fields={"leakfield": {"value": _MARKER_VALUE,
                                             "data_class": "PUBLIC"}})
    h = rt.build_canary_harness(tenant_id=gate.tid, runtime_request_id="rt1",
                                snapshot=snap)
    adapter = _adapter(["leakfield"])
    plan = _plan(gate, adapter, h["_canary_snapshot"], ["leakfield"])
    safe = rt._recompute_safe_output(adapter, h["_canary_snapshot"], plan)
    proof = rt.build_canary_non_leakage(
        tenant_id=gate.tid, runtime_request_id="rt1", harness=h, adapter=adapter,
        query_plan=plan, safe_output=safe)
    assert proof["leak_detected"] is True, "canary value leak blocks"
    assert proof["proof_status"] == "CANARY_LEAK_DETECTED"
    assert "CANARY_VALUE" in proof["detected_leaks"]


def test_canary_derived_marker_leak_blocks(gate):
    h = rt.build_canary_harness(tenant_id=gate.tid, runtime_request_id="rt1",
                                snapshot=_snap(gate))
    # Force the canary marker field to be readable in the LOCAL twin only.
    h["_canary_snapshot"]["fields"]["__canary_secret"] = {
        "value": "zz", "data_class": "PUBLIC"}
    adapter = _adapter(["__canary_secret"])
    plan = _plan(gate, adapter, h["_canary_snapshot"], ["__canary_secret"])
    safe = rt._recompute_safe_output(adapter, h["_canary_snapshot"], plan)
    proof = rt.build_canary_non_leakage(
        tenant_id=gate.tid, runtime_request_id="rt1", harness=h, adapter=adapter,
        query_plan=plan, safe_output=safe)
    assert proof["leak_detected"] is True, "canary-derived marker leak blocks"
    assert proof["proof_status"] == "CANARY_LEAK_DETECTED"
    assert "CANARY_DERIVED_MARKER" in proof["detected_leaks"]


def test_canary_correlated_output_blocks(gate):
    snap = _snap(gate)
    h = rt.build_canary_harness(tenant_id=gate.tid, runtime_request_id="rt1",
                                snapshot=snap)
    sources = ["case_id", "status"]
    adapter = _adapter(sources)
    plan = _plan(gate, adapter, h["_canary_snapshot"], sources)
    # safe_output that differs from the recomputed canary output => the output
    # is correlated with canary presence (a correlation channel).
    proof = rt.build_canary_non_leakage(
        tenant_id=gate.tid, runtime_request_id="rt1", harness=h, adapter=adapter,
        query_plan=plan, safe_output={"case_id": "C-1"})
    assert proof["leak_detected"] is True, "canary-correlated output blocks"
    assert proof["proof_status"] == "CANARY_LEAK_DETECTED"
    assert proof["canary_correlation_signals"] == ["OUTPUT_CHANGED_WITH_CANARY"]


def test_no_positive_status_overrides_canary_leak(gate):
    # The canary-leak signal is strictly dominant over a positive completion.
    status = rt.status_for_signals(
        ["CANARY_LEAK_DETECTED", "READ_ONLY_RUNTIME_COMPLETED"])
    assert status not in rt.POSITIVE_STATUSES
    assert status == "RUNTIME_QUARANTINED"
    # And the direct proof emits the leak signal.
    snap = _snap(gate)
    h = rt.build_canary_harness(tenant_id=gate.tid, runtime_request_id="rt1",
                                snapshot=snap)
    adapter = _adapter(["case_id", "status"])
    plan = _plan(gate, adapter, h["_canary_snapshot"], ["case_id", "status"])
    proof = rt.build_canary_non_leakage(
        tenant_id=gate.tid, runtime_request_id="rt1", harness=h, adapter=adapter,
        query_plan=plan, safe_output={"case_id": "C-1"})
    assert proof["signal"] == "CANARY_LEAK_DETECTED"


def test_clean_proof_records_markers_checked_without_leaking(gate):
    o = k.clean_outcome(gate)
    proof = o["canary_non_leakage_proof"]
    # Canary markers were actively checked, yet none leaked.
    assert proof["canary_markers_checked"]
    assert proof["canary_hash_fragments_checked"] >= 1
    assert proof["signal"] is None


def test_canary_non_leakage_hash_deterministic(gate):
    o = k.clean_outcome(gate)
    proof = o["canary_non_leakage_proof"]
    recomputed = rt._core_hash(proof, "canary_non_leakage_proof_hash")
    assert recomputed == proof["canary_non_leakage_proof_hash"]

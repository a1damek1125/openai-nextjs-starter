"""TOOL-B6 read-path runtime microkernel: output-provenance bisimulation.

Core v5 guarantee: the stored safe output must be bit-identical to a fresh,
deterministic recomputation of the read-set over the frozen snapshot. Any
tampering that adds output not derivable from the read-set is caught. Verified
against ACTUAL kernel behavior.
"""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def _plan(gate, snapshot):
    """Build adapter + query plan + executed read-set for a clean snapshot."""
    adapter = rt.build_adapter_descriptor(
        adapter_id="adp", adapter_kind="field_projection",
        allowed_sources=["case_id", "status"],
        allowed_projection=["case_id", "status"])
    qp = rt.build_query_plan_normal_form(
        tenant_id=gate.tid, runtime_request_id="x", adapter=adapter,
        snapshot=snapshot, requested_sources=["case_id", "status"],
        requested_projection=["case_id", "status"])
    read_set, _raw, safe, edges, _ops = rt._execute_read_only(
        adapter, snapshot, qp)
    pmap = rt.build_provenance_map(
        tenant_id=gate.tid, runtime_request_id="x", safe_output=safe,
        read_set=read_set, provenance_edges=edges, snapshot=snapshot,
        redaction_policy_hash="h")
    return adapter, qp, read_set, safe, pmap


def _bisim(gate, adapter, qp, read_set, pmap, snapshot, safe_output):
    return rt.build_bisimulation(
        tenant_id=gate.tid, runtime_request_id="x", provenance_map=pmap,
        safe_output=safe_output, adapter=adapter, snapshot=snapshot,
        query_plan=qp, read_set=read_set)


def test_clean_bisimulation_matched(gate):
    o = k.clean_outcome(gate)
    assert o["output_provenance_bisimulation"]["bisimulation_status"] == \
        "BISIMULATION_MATCHED"
    assert o["output_provenance_bisimulation"]["signal"] is None


def test_clean_safe_hash_equals_recomputed(gate):
    o = k.clean_outcome(gate)
    bis = o["output_provenance_bisimulation"]
    assert bis["safe_output_hash"] == bis["recomputed_safe_output_hash"]


def test_clean_mismatch_fields_empty(gate):
    o = k.clean_outcome(gate)
    assert o["output_provenance_bisimulation"]["mismatch_fields"] == []


def test_tampered_safe_output_fails(gate):
    _b5, _b5r, snap = k.setup(gate)
    adapter, qp, read_set, safe, pmap = _plan(gate, snap)
    tampered = {**safe, "__extra": "not-derivable-from-read-set"}
    bis = _bisim(gate, adapter, qp, read_set, pmap, snap, tampered)
    assert bis["bisimulation_status"] == "BISIMULATION_FAILED"


def test_tampered_recomputation_mismatch_blocks(gate):
    _b5, _b5r, snap = k.setup(gate)
    adapter, qp, read_set, safe, pmap = _plan(gate, snap)
    tampered = {**safe, "__extra": "x"}
    bis = _bisim(gate, adapter, qp, read_set, pmap, snap, tampered)
    assert bis["signal"] == "OUTPUT_PROVENANCE_BISIMULATION_FAILED", \
        "output provenance recomputation mismatch blocks"


def test_tampered_mismatch_fields_nonempty(gate):
    _b5, _b5r, snap = k.setup(gate)
    adapter, qp, read_set, safe, pmap = _plan(gate, snap)
    tampered = {**safe, "__extra": "x"}
    bis = _bisim(gate, adapter, qp, read_set, pmap, snap, tampered)
    assert bis["mismatch_fields"] == ["__extra"]
    assert bis["mismatch_fields"] != []


def test_recomputation_deterministic(gate):
    _b5, _b5r, snap = k.setup(gate)
    adapter, qp, _read_set, _safe, _pmap = _plan(gate, snap)
    first = rt._recompute_safe_output(adapter, snap, qp)
    second = rt._recompute_safe_output(adapter, snap, qp)
    assert first == second


def test_bisim_hash_deterministic(gate):
    _b5, _b5r, snap = k.setup(gate)
    adapter, qp, read_set, safe, pmap = _plan(gate, snap)
    a = _bisim(gate, adapter, qp, read_set, pmap, snap, safe)
    b = _bisim(gate, adapter, qp, read_set, pmap, snap, safe)
    assert a["output_provenance_bisimulation_hash"] == \
        b["output_provenance_bisimulation_hash"]


def test_bisim_hash_self_excluding(gate):
    o = k.clean_outcome(gate)
    bis = o["output_provenance_bisimulation"]
    recomputed = rt._core_hash(bis, "output_provenance_bisimulation_hash")
    assert recomputed == bis["output_provenance_bisimulation_hash"]

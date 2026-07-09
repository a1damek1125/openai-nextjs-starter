"""TOOL-B6 read-path runtime microkernel: read-output provenance map.

Core v5 guarantee: every safe-output field is a deterministic function of an
attested read-set edge; missing provenance or a forbidden-class source feeding
an output field both block. Verified against ACTUAL kernel behavior.
"""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def test_clean_provenance_status_matched(gate):
    o = k.clean_outcome(gate)
    pmap = o["read_output_provenance_map"]
    assert pmap["provenance_status"] == "OUTPUT_PROVENANCE_MATCHED"
    assert pmap["signal"] is None


def test_clean_every_safe_output_field_has_provenance(gate):
    o = k.clean_outcome(gate)
    pmap = o["read_output_provenance_map"]
    # Every safe output field appears in the provenance field-path set.
    for field in o["safe_output"]:
        assert field in pmap["safe_output_field_paths"], \
            "every safe output field has provenance"
    assert pmap["safe_output_field_paths"] == sorted(o["safe_output"])


def test_clean_unproven_output_fields_empty(gate):
    o = k.clean_outcome(gate)
    assert o["read_output_provenance_map"]["unproven_output_fields"] == []


def test_clean_no_forbidden_source_influence(gate):
    o = k.clean_outcome(gate)
    assert o["read_output_provenance_map"][
        "forbidden_source_influence_detected"] is False


def test_clean_taint_join_only_public(gate):
    o = k.clean_outcome(gate)
    taint = o["read_output_provenance_map"]["taint_join_results"]
    for classes in taint.values():
        assert classes == ["PUBLIC"]


def test_missing_provenance_blocks(gate):
    # A safe output field with NO provenance edge is unproven and blocks.
    pmap = rt.build_provenance_map(
        tenant_id=gate.tid, runtime_request_id="x",
        safe_output={"case_id": "C-1"}, read_set=[], provenance_edges=[],
        snapshot={}, redaction_policy_hash="h")
    assert pmap["unproven_output_fields"] == ["case_id"]
    assert pmap["signal"] == "READ_TO_OUTPUT_PROVENANCE_MISSING", \
        "missing provenance blocks"
    assert pmap["provenance_status"] == "OUTPUT_PROVENANCE_MISSING"


def test_forbidden_source_influence_blocks(gate):
    # A read-set entry of FORBIDDEN class feeding an output edge is detected.
    pmap = rt.build_provenance_map(
        tenant_id=gate.tid, runtime_request_id="x",
        safe_output={"case_id": "C-1"},
        read_set=[{"read_entry_id": "r0", "data_class": "CUSTOMER_SENSITIVE"}],
        provenance_edges=[{"output_field": "case_id", "read_entry_id": "r0",
                           "transform": "identity"}],
        snapshot={}, redaction_policy_hash="h")
    assert pmap["forbidden_source_influence_detected"] is True
    assert pmap["unproven_output_fields"] == []
    assert pmap["signal"] == "READ_TO_OUTPUT_PROVENANCE_MISSING", \
        "forbidden source influence blocks"
    assert pmap["provenance_status"] == "OUTPUT_PROVENANCE_FORBIDDEN_SOURCE"


def test_provenance_hash_deterministic(gate):
    args = dict(tenant_id=gate.tid, runtime_request_id="x",
                safe_output={"case_id": "C-1"},
                read_set=[{"read_entry_id": "r0", "data_class": "PUBLIC"}],
                provenance_edges=[{"output_field": "case_id",
                                   "read_entry_id": "r0",
                                   "transform": "identity"}],
                snapshot={}, redaction_policy_hash="h")
    a = rt.build_provenance_map(**args)
    b = rt.build_provenance_map(**args)
    assert a["read_output_provenance_map_hash"] == \
        b["read_output_provenance_map_hash"]


def test_provenance_hash_self_excluding(gate):
    o = k.clean_outcome(gate)
    pmap = o["read_output_provenance_map"]
    # Recomputing the hash over the full dict (which contains the hash field)
    # yields the same value => the hash excludes itself.
    recomputed = rt._core_hash(pmap, "read_output_provenance_map_hash")
    assert recomputed == pmap["read_output_provenance_map_hash"]

"""TOOL-B6 read-path runtime microkernel: semantic non-interference.

Core v5 guarantee: no forbidden source class can influence safe output.
Perturbing every forbidden-class field while holding the allowed read-set fixed
must NOT change the safe-output hash. Verified against ACTUAL kernel behavior.
"""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k

# The forbidden source classes that can NEVER flow to safe output.
FORBIDDEN_CLASSES = {
    "SECRET_LIKE", "CREDENTIAL_LIKE", "TOKEN_LIKE", "EXECUTION_AUTHORITY",
    "CROSS_TENANT_SOURCE", "MUTABLE_PRODUCTION_STATE", "PROVIDER_RESULT",
    "MCP_RESULT", "LLM_RESULT", "CANARY_FIELD", "CUSTOMER_SENSITIVE",
    "APPROVAL_SENSITIVE", "CONSENT_SENSITIVE",
}


def _adapter(gate):
    return rt.build_adapter_descriptor(
        adapter_id="adp", adapter_kind="field_projection",
        allowed_sources=["case_id", "status"],
        allowed_projection=["case_id", "status"])


def _query_plan(gate, adapter, snapshot):
    return rt.build_query_plan_normal_form(
        tenant_id=gate.tid, runtime_request_id="x", adapter=adapter,
        snapshot=snapshot, requested_sources=["case_id", "status"],
        requested_projection=["case_id", "status"])


def test_clean_matrix_matched(gate):
    o = k.clean_outcome(gate)
    m = o["semantic_non_interference_matrix"]
    assert m["matrix_status"] == "SEMANTIC_NON_INTERFERENCE_MATCHED"
    assert m["signal"] is None


def test_clean_no_forbidden_flow(gate):
    o = k.clean_outcome(gate)
    assert o["semantic_non_interference_matrix"][
        "forbidden_flow_detected"] is False


def test_clean_base_equals_perturbed_hash(gate):
    o = k.clean_outcome(gate)
    m = o["semantic_non_interference_matrix"]
    # Perturbing forbidden sources does NOT change the safe output hash.
    assert m["base_safe_output_hash"] == m["perturbed_safe_output_hash"]


def test_matrix_rows_cover_forbidden_classes(gate):
    o = k.clean_outcome(gate)
    rows = o["semantic_non_interference_matrix"]["matrix_rows"]
    covered = {r["source_class"] for r in rows}
    assert covered == set(rt.FORBIDDEN_SOURCE_CLASSES)
    for r in rows:
        assert r["allowed_flow"] is False


def test_forbidden_source_classes_never_flow(gate):
    o = k.clean_outcome(gate)
    rows = o["semantic_non_interference_matrix"]["matrix_rows"]
    covered = {r["source_class"] for r in rows}
    # Every one of the enumerated forbidden classes is denied any flow.
    assert covered == FORBIDDEN_CLASSES
    for r in rows:
        assert r["allowed_flow"] is False
        assert r["observed_flow"] is False


def test_perturbing_customer_sensitive_does_not_change_safe_output(gate):
    # Two snapshots differing ONLY in a CUSTOMER_SENSITIVE field must produce an
    # identical safe output (and safe-output hash).
    b5, b5r, snap1 = k.setup(gate)
    fields2 = {"case_id": {"value": "C-1", "data_class": "PUBLIC"},
               "status": {"value": "open", "data_class": "PUBLIC"},
               "ssn": {"value": "111-11-1111",
                       "data_class": "CUSTOMER_SENSITIVE"}}
    snap2 = rt.build_snapshot(snapshot_id="snap1", tenant_id=gate.tid,
                              epoch="5", scope="case", fields=fields2)
    o1 = k.prepare(gate, b5, b5r, snap1)
    o2 = k.prepare(gate, b5, b5r, snap2)
    assert o1["safe_output"] == o2["safe_output"]
    assert o1["safe_output_hash"] == o2["safe_output_hash"]


def test_output_depending_on_forbidden_field_fails(gate):
    # Craft a safe output that carries a CUSTOMER_SENSITIVE value: the matrix
    # detects that it is not derivable from the allowed read-set alone.
    _b5, _b5r, snap = k.setup(gate)
    adapter = _adapter(gate)
    qp = _query_plan(gate, adapter, snap)
    m = rt.build_non_interference(
        tenant_id=gate.tid, runtime_request_id="x", adapter=adapter,
        snapshot=snap, query_plan=qp, safe_output={"ssn": "999-99-9999"})
    assert m["matrix_status"] == "SEMANTIC_NON_INTERFERENCE_FAILED"
    assert m["signal"] == "SEMANTIC_NON_INTERFERENCE_FAILED"
    assert m["forbidden_flow_detected"] is True


def test_non_interference_hash_deterministic(gate):
    _b5, _b5r, snap = k.setup(gate)
    adapter = _adapter(gate)
    qp = _query_plan(gate, adapter, snap)
    args = dict(tenant_id=gate.tid, runtime_request_id="x", adapter=adapter,
                snapshot=snap, query_plan=qp,
                safe_output={"case_id": "C-1", "status": "open"})
    a = rt.build_non_interference(**args)
    b = rt.build_non_interference(**args)
    assert a["semantic_non_interference_matrix_hash"] == \
        b["semantic_non_interference_matrix_hash"]

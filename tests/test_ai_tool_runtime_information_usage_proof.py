"""TOOL-B6 v5 exfiltration-defense: information usage proof.

Local deterministic evidence: it computes coarse actuals (field count, sensitive
count, highest taint, read->output edges, correlation risk bucket, output entropy
bucket) against the budget. Each dimension breach maps to a violation and yields
INFORMATION_BUDGET_EXCEEDED. Buckets are coarse (no high-resolution metrics).
"""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def _budget(gate, **policy):
    return rt.build_information_budget(tenant_id=gate.tid,
                                       runtime_request_id="rt1", policy=policy
                                       or None)


def _usage(gate, budget, safe_output, taint=None, edges=None,
           read_set=None, repeated=0):
    return rt.build_information_usage(
        tenant_id=gate.tid, runtime_request_id="rt1", budget=budget,
        safe_output=safe_output,
        provenance_map={"taint_join_results": taint or {},
                        "source_read_entry_ids": edges or []},
        read_set=read_set or [], repeated_query_count=repeated)


def test_clean_usage_no_violations(gate):
    proof = _usage(gate, _budget(gate),
                   {"case_id": "C-1", "status": "open"},
                   edges=["e0", "e1"])
    assert proof["budget_violations"] == []
    assert proof["proof_status"] == "INFORMATION_BUDGET_MATCHED"
    assert proof["signal"] is None


def test_usage_reports_all_metric_dimensions(gate):
    proof = _usage(gate, _budget(gate),
                   {"case_id": "C-1", "status": "open"}, edges=["e0", "e1"])
    for m in ("output_fields_count", "sensitive_field_count",
              "highest_output_taint", "read_to_output_edge_count",
              "correlation_risk_bucket", "output_entropy_bucket"):
        assert m in proof
    assert proof["output_fields_count"] == 2
    assert proof["read_to_output_edge_count"] == 2


def test_max_output_fields_breach(gate):
    proof = _usage(gate, _budget(gate, max_output_fields=1),
                   {"a": 1, "b": 2, "c": 3})
    assert "MAX_OUTPUT_FIELDS" in proof["budget_violations"]
    assert proof["proof_status"] == "INFORMATION_BUDGET_EXCEEDED"


def test_max_sensitive_fields_breach(gate):
    proof = _usage(gate, _budget(gate), {"f": "x"},
                   taint={"f": ["INTERNAL"]})
    assert "MAX_SENSITIVE_FIELDS" in proof["budget_violations"]
    assert proof["signal"] == "INFORMATION_BUDGET_EXCEEDED"


def test_max_taint_level_breach(gate):
    proof = _usage(gate, _budget(gate, max_taint_level=0), {"f": "x"},
                   taint={"f": ["CUSTOMER_SENSITIVE"]})
    assert "MAX_TAINT_LEVEL" in proof["budget_violations"]
    assert proof["highest_output_taint"] >= 2


def test_max_edges_breach(gate):
    proof = _usage(gate, _budget(gate, max_read_to_output_edges=0),
                   {"f": "x"}, edges=["e0"])
    assert "MAX_EDGES" in proof["budget_violations"]


def test_max_repeated_query_breach(gate):
    proof = _usage(gate, _budget(gate), {"f": "x"}, repeated=6)
    assert "MAX_REPEATED_QUERY" in proof["budget_violations"]
    assert proof["repeated_query_count"] == 6


def test_buckets_are_coarse_low_resolution(gate):
    # Even with a large output the exposed metrics stay coarse bucket indices.
    big = {f"f{i}": i for i in range(20)}
    proof = _usage(gate, _budget(gate), big, repeated=50)
    assert 0 <= proof["output_entropy_bucket"] <= 4
    assert 0 <= proof["correlation_risk_bucket"] <= 3
    # No high-resolution timing / exact-entropy metric is exported.
    assert all("nanos" not in k2 and "exact" not in k2 for k2 in proof)


def test_usage_proof_hash_deterministic_and_self_excluding(gate):
    b = _budget(gate)
    a1 = _usage(gate, b, {"case_id": "C-1"}, edges=["e0"])
    a2 = _usage(gate, b, {"case_id": "C-1"}, edges=["e0"])
    assert a1["information_usage_proof_hash"] == \
        a2["information_usage_proof_hash"]
    recomputed = rt._core_hash(a1, "information_usage_proof_hash")
    assert recomputed == a1["information_usage_proof_hash"]


def test_information_usage_and_budget_endpoints(gate):
    rid, _ = gate.prepared_runtime()
    up = gate.rt(rid, path="/information-usage-proof")
    bp = gate.rt(rid, path="/information-budget")
    assert up.status_code == 200 and bp.status_code == 200
    assert up.json()["information_usage_proof"]["proof_status"] == \
        "INFORMATION_BUDGET_MATCHED"
    assert bp.json()["information_budget_envelope"]["budget_status"] == \
        "BUDGET_DEFINED"

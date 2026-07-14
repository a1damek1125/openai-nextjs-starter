"""TOOL-B6 v5 exfiltration-defense: information budget envelope + usage status.

The information-budget envelope declares coarse max_* limits (an upper bound on
information the safe output may carry). It is explicitly NOT approval to export
data. Breaching the budget dominates with INFORMATION_BUDGET_EXCEEDED. The
endpoint clamps supplied policy stricter-only.
"""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k

_MAX_FIELDS = ("max_output_fields", "max_sensitive_field_count",
               "max_taint_level_allowed", "max_read_to_output_edges",
               "max_repeated_query_count", "max_correlation_risk_bucket",
               "max_output_entropy_bucket")


def test_budget_envelope_has_all_max_fields(gate):
    env = rt.build_information_budget(tenant_id=gate.tid,
                                      runtime_request_id="rt1", policy=None)
    for f in _MAX_FIELDS:
        assert f in env, f"information budget required field {f}"
    assert env["budget_status"] == "BUDGET_DEFINED"
    assert env["information_budget_envelope_hash"]


def test_budget_envelope_note_is_not_export_approval(gate):
    env = rt.build_information_budget(tenant_id=gate.tid,
                                      runtime_request_id="rt1", policy=None)
    assert "not approval to export data" in env["note"], \
        "information budget is NOT export approval"


def test_clean_usage_matches_budget(gate):
    o = k.clean_outcome(gate)
    assert o["information_usage_proof"]["proof_status"] == \
        "INFORMATION_BUDGET_MATCHED"


def test_zero_output_field_budget_dominates(gate):
    b5, b5r, snap = k.setup(gate)
    o = k.prepare(gate, b5, b5r, snap, policy={"max_output_fields": 0})
    assert o["information_usage_proof"]["proof_status"] == \
        "INFORMATION_BUDGET_EXCEEDED", "information budget breach blocks"
    assert o["dominant_signal"] == "INFORMATION_BUDGET_EXCEEDED"
    assert o["runtime_status"] not in rt.POSITIVE_STATUSES


def test_stricter_taint_and_edge_budget_breaches(gate):
    # A stricter budget flags sensitive / taint dimensions directly.
    budget = rt.build_information_budget(
        tenant_id=gate.tid, runtime_request_id="rt1",
        policy={"max_taint_level": 0, "max_read_to_output_edges": 0})
    usage = rt.build_information_usage(
        tenant_id=gate.tid, runtime_request_id="rt1", budget=budget,
        safe_output={"f": "x"},
        provenance_map={"taint_join_results": {"f": ["INTERNAL"]},
                        "source_read_entry_ids": ["e0"]},
        read_set=[{"field_path": "f"}], repeated_query_count=0)
    assert usage["proof_status"] == "INFORMATION_BUDGET_EXCEEDED"
    assert "MAX_TAINT_LEVEL" in usage["budget_violations"]
    assert "MAX_EDGES" in usage["budget_violations"]


def test_endpoint_clamps_policy_stricter_only(gate):
    # Supplying a huge max_output_fields is clamped down to the default (8).
    rid, _ = gate.prepared_runtime(policy={"max_output_fields": 100000})
    resp = gate.rt(rid, path="/information-budget")
    assert resp.status_code == 200
    env = resp.json()["information_budget_envelope"]
    assert env["max_output_fields"] == rt.DEFAULT_POLICY["max_output_fields"]
    assert env["max_output_fields"] == 8


def test_budget_envelope_hash_deterministic(gate):
    a = rt.build_information_budget(tenant_id=gate.tid,
                                    runtime_request_id="rt1", policy=None)
    b = rt.build_information_budget(tenant_id=gate.tid,
                                    runtime_request_id="rt1", policy=None)
    assert a["information_budget_envelope_hash"] == \
        b["information_budget_envelope_hash"]
    recomputed = rt._core_hash(a, "information_budget_envelope_hash")
    assert recomputed == a["information_budget_envelope_hash"]


def test_usage_proof_hash_deterministic(gate):
    o = k.clean_outcome(gate)
    proof = o["information_usage_proof"]
    recomputed = rt._core_hash(proof, "information_usage_proof_hash")
    assert recomputed == proof["information_usage_proof_hash"]

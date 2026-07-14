"""TOOL-B6: query plan normal form. Unknown source blocks, forbidden projection
blocks, forbidden-class source flagged, plan hash participates in the decision."""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def _adapter(sources=("case_id", "status"), projection=("case_id", "status")):
    return rt.build_adapter_descriptor(
        adapter_id="adp", adapter_kind="field_projection",
        allowed_sources=list(sources), allowed_projection=list(projection))


def test_clean_plan_normalized(gate):
    _, _, snap = k.setup(gate)
    plan = rt.build_query_plan_normal_form(
        tenant_id=gate.tid, runtime_request_id="r", adapter=_adapter(),
        snapshot=snap, requested_sources=["case_id", "status"],
        requested_projection=["case_id", "status"])
    assert plan["query_plan_status"] == "PLAN_NORMALIZED"
    assert plan["signal"] is None
    assert plan["query_plan_hash"]
    norm = plan["normalized_query_plan"]
    assert norm["sources"] == ["case_id", "status"]
    assert norm["projection"] == ["case_id", "status"]
    assert norm["adapter_kind"] == "field_projection"


def test_query_plan_normal_form_required_fields(gate):
    """'query plan normal form required' -- the plan is a mandatory pre-exec
    artifact carrying a normalized plan + hash."""
    _, _, snap = k.setup(gate)
    plan = rt.build_query_plan_normal_form(
        tenant_id=gate.tid, runtime_request_id="r", adapter=_adapter(),
        snapshot=snap, requested_sources=["case_id", "status"],
        requested_projection=["case_id", "status"])
    for key in ("normalized_query_plan", "query_plan_hash",
                "query_plan_normal_form_hash", "query_plan_status"):
        assert key in plan, "query plan normal form required: " + key


def test_unknown_source_blocks(gate):
    """'unknown source blocks': a requested source not in the snapshot ->
    SEMANTIC_READ_DENIED."""
    _, _, snap = k.setup(gate)
    plan = rt.build_query_plan_normal_form(
        tenant_id=gate.tid, runtime_request_id="r", adapter=_adapter(),
        snapshot=snap, requested_sources=["case_id", "not_a_field"],
        requested_projection=["case_id", "status"])
    assert plan["query_plan_status"] == "PLAN_REJECTED"
    assert plan["signal"] == "SEMANTIC_READ_DENIED"
    assert "not_a_field" in plan["unknown_sources"]


def test_forbidden_projection_blocks(gate):
    """'forbidden projection blocks': a projection field outside the adapter's
    allowed_projection -> RUNTIME_PATH_POLICY_REJECTED."""
    _, _, snap = k.setup(gate)
    plan = rt.build_query_plan_normal_form(
        tenant_id=gate.tid, runtime_request_id="r", adapter=_adapter(),
        snapshot=snap, requested_sources=["case_id"],
        requested_projection=["not_allowed"])
    assert plan["query_plan_status"] == "PLAN_REJECTED"
    assert plan["signal"] == "RUNTIME_PATH_POLICY_REJECTED"
    assert "not_allowed" in plan["forbidden_projection_fields"]


def test_forbidden_class_source_flagged(gate):
    """A forbidden-class source (ssn/CUSTOMER_SENSITIVE) in the plan surfaces in
    forbidden_sources."""
    _, _, snap = k.setup(gate)
    adapter = _adapter(sources=("case_id", "status", "ssn"),
                       projection=("case_id", "status", "ssn"))
    plan = rt.build_query_plan_normal_form(
        tenant_id=gate.tid, runtime_request_id="r", adapter=adapter,
        snapshot=snap, requested_sources=["case_id", "ssn"],
        requested_projection=["case_id", "ssn"])
    assert plan["forbidden_sources"], "forbidden-class source must be flagged"
    assert "ssn" in plan["forbidden_sources"]


def test_prepare_forbidden_projection_rejected(gate):
    b5, b5r, snap = k.setup(gate)
    o = k.prepare(gate, b5, b5r, snap, requested_projection=["zzz"])
    assert o["runtime_status"] == "RUNTIME_BLOCKED"
    assert o["dominant_signal"] == "RUNTIME_PATH_POLICY_REJECTED"


def test_prepare_unknown_source_denied(gate):
    b5, b5r, snap = k.setup(gate)
    o = k.prepare(gate, b5, b5r, snap, requested_sources=["nonexistent"])
    assert o["runtime_status"] == "RUNTIME_BLOCKED"
    assert o["dominant_signal"] == "SEMANTIC_READ_DENIED"


def test_plan_hash_participates_and_deterministic(gate):
    """Changing the plan changes the runtime_decision_hash; identical inputs are
    deterministic (both directions)."""
    b5, b5r, snap = k.setup(gate)
    a = k.prepare(gate, b5, b5r, snap)
    a2 = k.prepare(gate, b5, b5r, snap)
    # Deterministic: identical plan -> identical hashes.
    assert a["query_plan_normal_form"]["query_plan_hash"] == \
        a2["query_plan_normal_form"]["query_plan_hash"]
    assert a["runtime_decision_hash"] == a2["runtime_decision_hash"]
    # Different (still clean) plan -> different plan hash AND decision hash.
    b = k.prepare(gate, b5, b5r, snap, requested_sources=["case_id"],
                  requested_projection=["case_id"])
    assert b["runtime_status"] == "RUNTIME_READ_ONLY_COMPLETED"
    assert a["query_plan_normal_form"]["query_plan_hash"] != \
        b["query_plan_normal_form"]["query_plan_hash"]
    assert a["runtime_decision_hash"] != b["runtime_decision_hash"]

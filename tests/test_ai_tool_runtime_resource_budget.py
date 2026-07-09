"""TOOL-B6 read-path runtime: runtime resource usage is bounded and recorded.

The resource budget envelope caps operations/reads/output size; usage is
proven within budget on the clean path and fails closed when a budget is
exceeded.
"""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def test_resource_budget_envelope(gate):
    rb = rt.build_resource_budget(tenant_id=gate.tid, runtime_request_id="r",
                                  policy=None)
    assert rb["op_budget"] == rt.DEFAULT_POLICY["resource_op_budget"]
    assert rb["read_budget"] == rt.DEFAULT_POLICY["resource_read_budget"]
    assert rb["output_size_budget"] == \
        rt.DEFAULT_POLICY["resource_output_size_budget"]


def test_resource_usage_within_budget(gate):
    o = k.clean_outcome(gate)
    ru = o["runtime_resource_usage_proof"]
    assert ru["usage_status"] == "RESOURCE_WITHIN_BUDGET"
    assert ru["budget_violations"] == []
    # runtime resource usage is bounded and recorded.
    assert ru["operation_count"] >= 0 and ru["read_count"] >= 0
    assert ru["output_size"] >= 0


def test_read_budget_exceeded_blocks(gate):
    b5, b5r, snap = k.setup(gate)
    o = k.prepare(gate, b5, b5r, snap, policy={"resource_read_budget": 0})
    assert o["runtime_status"] == "RUNTIME_BLOCKED"
    assert o["dominant_signal"] == "RESOURCE_BUDGET_EXCEEDED"
    assert "READ_BUDGET" in o["runtime_resource_usage_proof"][
        "budget_violations"]


def test_output_size_budget_exceeded_blocks(gate):
    b5, b5r, snap = k.setup(gate)
    o = k.prepare(gate, b5, b5r, snap,
                  policy={"resource_output_size_budget": 0})
    assert o["runtime_status"] == "RUNTIME_BLOCKED"
    assert o["dominant_signal"] == "RESOURCE_BUDGET_EXCEEDED"
    assert "OUTPUT_SIZE_BUDGET" in o["runtime_resource_usage_proof"][
        "budget_violations"]


def test_usage_is_recorded(gate):
    o = k.clean_outcome(gate)
    ru = o["runtime_resource_usage_proof"]
    # Usage is bound to its budget envelope by hash.
    rb = o["runtime_resource_budget_envelope"]
    assert ru["resource_budget_hash"] == rb[
        "runtime_resource_budget_envelope_hash"]


def test_resource_hashes_deterministic_and_self_excluding(gate):
    rb1 = rt.build_resource_budget(tenant_id=gate.tid, runtime_request_id="r",
                                   policy=None)
    rb2 = rt.build_resource_budget(tenant_id=gate.tid, runtime_request_id="r",
                                   policy=None)
    assert rb1["runtime_resource_budget_envelope_hash"] == \
        rb2["runtime_resource_budget_envelope_hash"]
    assert rt._core_hash(rb1, "runtime_resource_budget_envelope_hash") == \
        rb1["runtime_resource_budget_envelope_hash"]
    ru = rt.build_resource_usage(
        tenant_id=gate.tid, runtime_request_id="r", budget=rb1,
        operations=[{"op": "x"}], read_set=[{"field_path": "a"}],
        safe_output={"a": 1})
    assert rt._core_hash(ru, "runtime_resource_usage_proof_hash") == \
        ru["runtime_resource_usage_proof_hash"]


def test_resource_endpoints(gate):
    rid, _ = gate.prepared_runtime()
    rb = gate.rt(rid, path="/resource-budget")
    assert rb.status_code == 200
    assert "runtime_resource_budget_envelope" in rb.json()
    ru = gate.rt(rid, path="/resource-usage-proof")
    assert ru.status_code == 200
    assert ru.json()["runtime_resource_usage_proof"]["usage_status"] == \
        "RESOURCE_WITHIN_BUDGET"

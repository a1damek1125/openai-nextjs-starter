"""TOOL-B6: semantic read firewall (class/scope enforcement over reads)."""
from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


def _firewall(snap, allowed_sources, requested_sources):
    adapter = rt.build_adapter_descriptor(
        adapter_id="adp", adapter_kind="field_projection",
        allowed_sources=list(allowed_sources),
        allowed_projection=list(allowed_sources))
    qp = rt.build_query_plan_normal_form(
        tenant_id="t", runtime_request_id="r", adapter=adapter, snapshot=snap,
        requested_sources=list(requested_sources),
        requested_projection=list(allowed_sources))
    return rt.build_semantic_read_firewall(
        tenant_id="t", runtime_request_id="r", snapshot=snap, adapter=adapter,
        query_plan=qp)


def test_firewall_allows_public_sources(gate):
    _, _, snap = k.setup(gate)
    fw = _firewall(snap, ["case_id", "status"], ["case_id", "status"])
    assert fw["read_status"] == "SEMANTIC_READ_ALLOWED"
    assert fw["signal"] is None
    assert fw["firewall_findings"] == []


def test_firewall_blocks_forbidden_class_source(gate):
    _, _, snap = k.setup(gate)
    fw = _firewall(snap, ["case_id", "ssn"], ["case_id", "ssn"])
    assert fw["read_status"] == "SEMANTIC_READ_BLOCKED"
    assert fw["signal"] == "SEMANTIC_READ_DENIED"
    assert any(f.startswith("TAINT:ssn") for f in fw["firewall_findings"])


def test_firewall_scope_finding_for_source_outside_allowlist(gate):
    _, _, snap = k.setup(gate)
    # 'status' requested but adapter only allows 'case_id'.
    fw = _firewall(snap, ["case_id"], ["case_id", "status"])
    assert fw["read_status"] == "SEMANTIC_READ_BLOCKED"
    assert fw["signal"] == "SEMANTIC_READ_DENIED"
    assert any(f.startswith("SCOPE:status") for f in fw["firewall_findings"])


def test_firewall_hash_deterministic_and_self_excluding(gate):
    _, _, snap = k.setup(gate)
    f1 = _firewall(snap, ["case_id", "status"], ["case_id", "status"])
    f2 = _firewall(snap, ["case_id", "status"], ["case_id", "status"])
    assert f1["semantic_read_firewall_hash"] == \
        f2["semantic_read_firewall_hash"]
    assert f1["semantic_read_firewall_hash"] == rt._core_hash(
        f1, "semantic_read_firewall_hash")


def test_clean_outcome_firewall_allowed(gate):
    o = k.clean_outcome(gate)
    assert o["semantic_read_firewall"]["read_status"] == \
        "SEMANTIC_READ_ALLOWED"


def test_prepare_ssn_read_blocked(gate):
    b5, b5r, snap = k.setup(gate)
    o = k.prepare(gate, b5, b5r, snap,
                  allowed_sources=["case_id", "ssn"],
                  requested_sources=["case_id", "ssn"],
                  allowed_projection=["case_id"],
                  requested_projection=["case_id"])
    assert o["runtime_status"] == "RUNTIME_BLOCKED"
    assert o["dominant_signal"] == "SEMANTIC_READ_DENIED"


def test_prepare_ssn_value_not_in_safe_output(gate):
    b5, b5r, snap = k.setup(gate)
    o = k.prepare(gate, b5, b5r, snap,
                  allowed_sources=["case_id", "ssn"],
                  requested_sources=["case_id", "ssn"],
                  allowed_projection=["case_id"],
                  requested_projection=["case_id"])
    ssn_value = k.clean_fields()["ssn"]["value"]
    assert o["safe_output"] == {}
    assert ssn_value not in repr(o["safe_output"])


def test_prepare_clean_read_only_completed(gate):
    b5, b5r, snap = k.setup(gate)
    o = k.prepare(gate, b5, b5r, snap)
    assert o["runtime_status"] == "RUNTIME_READ_ONLY_COMPLETED"
    assert o["semantic_read_firewall"]["signal"] is None

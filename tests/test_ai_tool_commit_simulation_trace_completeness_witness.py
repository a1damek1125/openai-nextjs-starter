"""TOOL-B8 v5: Trace-completeness witness — every required trace family must be
observed; any missing family (critical or not) fails the witness and blocks."""
from finalis.ai_employee.tool_commit_simulation import (
    _core_hash, REQUIRED_TRACE_FAMILIES, CRITICAL_TRACE_FAMILIES)
from tests import _b8_kernel as k


def test_witness_exists(gate):
    w = k.clean_outcome(gate)["trace_completeness_witness"]
    assert w["trace_completeness_witness_id"].startswith("tcw-")
    assert w["signal"] is None


def test_clean_witness_complete(gate):
    w = k.clean_outcome(gate)["trace_completeness_witness"]
    assert w["witness_status"] == "COMPLETE"
    assert w["missing_trace_families"] == []
    assert w["critical_missing_trace_families"] == []
    assert w["required_trace_families"] == list(REQUIRED_TRACE_FAMILIES)
    assert w["observed_trace_hashes"]


def test_clean_outcome_accepted(gate):
    o = k.clean_outcome(gate)
    assert o["commit_simulation_status"] == "B8_V5_ACCEPTED"


def test_missing_critical_family_blocks(gate):
    observed = [f for f in REQUIRED_TRACE_FAMILIES if f != "NO_COMMIT_THEOREM"]
    o = k.clean_outcome(gate, observed_trace_families=observed)
    w = o["trace_completeness_witness"]
    assert w["witness_status"] == "INCOMPLETE"
    assert "NO_COMMIT_THEOREM" in w["missing_trace_families"]
    assert w["critical_missing_trace_families"]
    assert o["dominant_signal"] == "TRACE_COMPLETENESS_WITNESS_FAILED"
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_missing_noncritical_family_still_blocks(gate):
    # APPROVAL is required but NOT in CRITICAL_TRACE_FAMILIES; missing at all
    # still fails the witness.
    assert "APPROVAL" not in CRITICAL_TRACE_FAMILIES
    observed = [f for f in REQUIRED_TRACE_FAMILIES if f != "APPROVAL"]
    o = k.clean_outcome(gate, observed_trace_families=observed)
    w = o["trace_completeness_witness"]
    assert w["missing_trace_families"] == ["APPROVAL"]
    assert w["critical_missing_trace_families"] == []
    assert "TRACE_COMPLETENESS_WITNESS_FAILED" in o["all_signals"]
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_remove_audit_trace_malicious_blocks(gate):
    # "remove audit trace" — drop the non-execution audit family.
    observed = [f for f in REQUIRED_TRACE_FAMILIES if f != "NON_EXECUTION"]
    o = k.clean_outcome(gate, observed_trace_families=observed)
    assert "NON_EXECUTION" in o["trace_completeness_witness"][
        "missing_trace_families"]
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_all_critical_families_are_required(gate):
    assert CRITICAL_TRACE_FAMILIES <= set(REQUIRED_TRACE_FAMILIES)


def test_witness_hash_recomputes(gate):
    w = k.clean_outcome(gate)["trace_completeness_witness"]
    assert _core_hash(w, "trace_completeness_witness_hash", "signal") == \
        w["trace_completeness_witness_hash"]


def test_missing_trace_changes_witness_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["trace_completeness_witness"][
        "trace_completeness_witness_hash"]
    observed = [f for f in REQUIRED_TRACE_FAMILIES if f != "NO_COMMIT_THEOREM"]
    broken = k.prepare(gate, b7, observed_trace_families=observed)[
        "trace_completeness_witness"]["trace_completeness_witness_hash"]
    assert clean != broken


def test_missing_trace_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    observed = [f for f in REQUIRED_TRACE_FAMILIES if f != "NO_COMMIT_THEOREM"]
    broken = k.prepare(gate, b7, observed_trace_families=observed)[
        "commit_simulation_decision_hash"]
    assert clean != broken


def test_witness_endpoint_returns_witness(gate):
    sid, _ = gate.prepared_commit_simulation()
    w = gate.cs(sid, "/trace-completeness-witness").json()[
        "trace_completeness_witness"]
    assert w["witness_status"] == "COMPLETE"
    assert w["missing_trace_families"] == []

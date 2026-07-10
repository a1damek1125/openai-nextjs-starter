"""TOOL-B8 v4: trace coverage — all required trace families must be observed;
critical gaps hard-block, non-critical gaps request review."""
from finalis.ai_employee.tool_commit_simulation import (
    _core_hash, REQUIRED_TRACE_FAMILIES,
)
from tests import _b8_kernel as k


def test_clean_coverage_covered(gate):
    tc = k.clean_outcome(gate)["trace_coverage"]
    assert tc["coverage_status"] == "COVERED"
    assert tc["missing_families"] == []
    assert tc["required_families"] == list(REQUIRED_TRACE_FAMILIES)
    assert tc["signal"] is None


def test_critical_family_gap_insufficient(gate):
    # drop a CRITICAL family (NO_COMMIT_THEOREM). The trace-completeness witness
    # ALSO fires and DOMINATES the coverage-insufficient signal.
    observed = [f for f in REQUIRED_TRACE_FAMILIES if f != "NO_COMMIT_THEOREM"]
    o = k.clean_outcome(gate, observed_trace_families=observed)
    assert o["trace_coverage"]["coverage_status"] == "CRITICAL_GAP"
    assert "TRACE_COVERAGE_INSUFFICIENT" in o["all_signals"]
    assert o["dominant_signal"] == "TRACE_COMPLETENESS_WITNESS_FAILED"
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_critical_missing_recorded(gate):
    observed = [f for f in REQUIRED_TRACE_FAMILIES if f != "NO_COMMIT_THEOREM"]
    tc = k.clean_outcome(gate, observed_trace_families=observed)[
        "trace_coverage"]
    assert "NO_COMMIT_THEOREM" in tc["missing_families"]
    assert "NO_COMMIT_THEOREM" in tc["critical_missing_families"]


def test_noncritical_family_gap_partial(gate):
    # drop a NON-critical family (APPROVAL) -> PARTIAL coverage + review signal.
    observed = [f for f in REQUIRED_TRACE_FAMILIES if f != "APPROVAL"]
    o = k.clean_outcome(gate, observed_trace_families=observed)
    tc = o["trace_coverage"]
    assert tc["coverage_status"] == "PARTIAL"
    assert tc["critical_missing_families"] == []
    assert "TRACE_COVERAGE_REVIEW" in o["all_signals"]


def test_gap_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    observed = [f for f in REQUIRED_TRACE_FAMILIES if f != "APPROVAL"]
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    gap = k.prepare(gate, b7, observed_trace_families=observed)[
        "commit_simulation_decision_hash"]
    assert clean != gap


def test_coverage_hash_recomputes(gate):
    tc = k.clean_outcome(gate)["trace_coverage"]
    assert _core_hash(tc, "trace_coverage_hash", "signal") == \
        tc["trace_coverage_hash"]


# --- API layer -------------------------------------------------------------
def test_api_coverage_endpoint_covered(gate):
    sid, _ = gate.prepared_commit_simulation()
    tc = gate.cs(sid, "/trace-coverage").json()["trace_coverage"]
    assert tc["coverage_status"] == "COVERED"
    assert tc["missing_families"] == []
    assert tc["required_families"] == list(REQUIRED_TRACE_FAMILIES)


def test_api_coverage_hash_recomputes(gate):
    sid, _ = gate.prepared_commit_simulation()
    tc = gate.cs(sid, "/trace-coverage").json()["trace_coverage"]
    assert _core_hash(tc, "trace_coverage_hash", "signal") == \
        tc["trace_coverage_hash"]

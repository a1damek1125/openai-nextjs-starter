"""SP0005 scenarios, incidents, near-miss, reassessment, debt, envelopes. Covers
AC-0005-148..216."""
from __future__ import annotations

from tools.safety.scenarios import validate_scenario, pairwise, coverage_report
from tools.safety.incidents import validate_incidents, near_miss_findings
from tools.safety.reassessment import (triggers_for, impact_cone,
                                       incremental_equals_full)
from tools.safety.debt import assurance_debt, gate_findings, drift_snapshot
from tools.safety.envelope import safety_case_envelope, safety_decision_envelope
from tools.safety.model import (INVALID_SAFETY_SCHEMA, NEAR_MISS_REVIEW_REQUIRED,
                                INCIDENT_EVIDENCE_INCOMPLETE)


def _k(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


# ---- scenario compiler (AC-0005-148..158) ----------------------------------
def test_scenario_requires_verification_predicate():
    assert INVALID_SAFETY_SCHEMA in _k(validate_scenario(
        {"scenario_id": "S", "initial_state": {},
         "expected_safety_property": "x"}))  # no predicate


def test_scenario_predicate_must_be_observable():
    assert any("not observable" in f.message for f in validate_scenario(
        {"scenario_id": "S", "initial_state": {}, "expected_safety_property": "x",
         "verification_predicate": "p", "verification_oracle": "AGENT_SELF_REPORT"}))


def test_scenario_no_external_effect():
    assert any("external effect" in f.message for f in validate_scenario(
        {"scenario_id": "S", "initial_state": {}, "expected_safety_property": "x",
         "verification_predicate": "p", "effect_mode": "REAL"}))


def test_pairwise_bounded_not_cartesian():
    dims = {"a": [1, 2, 3], "b": ["x", "y", "z"], "c": [True, False]}
    cases = pairwise(dims)
    # full cartesian would be 18; pairwise must be far fewer
    assert 0 < len(cases) < 18


def test_coverage_report_multidimensional():
    r = coverage_report([{"hazard_refs": ["H1"], "channel": "email"}])
    assert "hazard_refs_covered" in r and "scenario_count" in r


# ---- incidents + near-miss (AC-0005-162..166) ------------------------------
def test_incident_severity_separate_from_legal():
    assert INCIDENT_EVIDENCE_INCOMPLETE in _k(validate_incidents(
        {"incidents": [{"incident_id": "I", "status": "CLOSED"}]}))  # missing both


def test_incident_cannot_mutate_policy():
    assert validate_incidents({"incidents": [
        {"incident_id": "I", "status": "CLOSED", "internal_severity": "LOW",
         "legal_reportability_status": "NO", "direct_policy_mutation": True}]})


def test_near_miss_is_evidence_requires_review():
    assert NEAR_MISS_REVIEW_REQUIRED in _k(near_miss_findings(
        {"near_misses": [{"near_miss_id": "N", "status": "DETECTED"}]}))


def test_near_miss_cannot_mutate_policy():
    assert near_miss_findings({"near_misses": [
        {"near_miss_id": "N", "reviewed": True, "direct_policy_mutation": True}]})


# ---- reassessment + impact cone (AC-0005-171..187) -------------------------
def test_reassessment_triggers():
    assert triggers_for({"changes": ["NEW_MODEL", "NEW_JURISDICTION", "BOGUS"]}) == \
        ["NEW_JURISDICTION", "NEW_MODEL"]


def test_impact_cone_maps_affected():
    prog = {"constraints": [{"constraint_id": "C", "hazard_refs": ["H"]}],
            "controls": [{"control_id": "K", "hazard_refs": ["H"]}],
            "claims": [{"claim_id": "CL", "hazard_refs": ["H"]}]}
    cone = impact_cone(prog, {"change_id": "X", "hazard_refs": ["H"],
                              "changes": ["NEW_MODEL"]})
    assert "K" in cone["affected_controls"] and "CL" in cone["affected_claims"]


def test_incremental_equals_full():
    prog = {"controls": [{"control_id": "K", "hazard_refs": ["H"]}]}
    assert incremental_equals_full(prog, {"hazard_refs": ["H"]})


# ---- assurance debt + gate (AC-0005-188..191) ------------------------------
def test_p0_open_fails_gate():
    rep = {"counts": {"P0": 1, "P1": 0}, "findings": []}
    debt = assurance_debt(rep, {})
    assert debt["safety_gate"] == "FAIL" and gate_findings(rep)


def test_no_p0_passes_gate():
    rep = {"counts": {"P0": 0, "P1": 0}, "findings": []}
    assert assurance_debt(rep, {})["safety_gate"] == "PASS"


def test_drift_advisory():
    d = drift_snapshot({"hazards": []}, {"counts": {"P0": 0, "P1": 0}})
    assert d["classification"] == "ADVISORY_NOT_A_GATE"


# ---- proof envelopes (AC-0005-208..216) ------------------------------------
def test_safety_case_envelope_deterministic_and_evidence():
    case = {"case_id": "SC", "claims": [{"claim_id": "C"}], "hazards": []}
    e1, e2 = safety_case_envelope(case), safety_case_envelope(case)
    assert e1["envelope_hash"] == e2["envelope_hash"]
    assert e1["classification"] == "EVIDENCE_NOT_AUTHORITY"


def test_envelope_changes_on_hazard_and_evidence_change():
    case = {"case_id": "SC", "hazards": [{"hazard_id": "H"}], "evidence": []}
    h0 = safety_case_envelope(case)["envelope_hash"]
    assert safety_case_envelope(dict(case, hazards=[{"hazard_id": "H2"}]))[
        "envelope_hash"] != h0
    assert safety_case_envelope(dict(case, evidence=[{"evidence_id": "E"}]))[
        "envelope_hash"] != h0


def test_envelope_changes_on_defeater_and_regulatory_change():
    case = {"case_id": "SC", "defeaters": [], "regulatory_context": []}
    h0 = safety_case_envelope(case)["envelope_hash"]
    assert safety_case_envelope(dict(case, defeaters=[{"defeater_id": "D"}]))[
        "envelope_hash"] != h0
    assert safety_case_envelope(dict(case, regulatory_context=[{"source_id": "S"}]))[
        "envelope_hash"] != h0


def test_decision_envelope_evidence_not_authority():
    d = safety_decision_envelope({"decision": "ALLOW", "reason_codes": ["x"]})
    assert d["classification"] == "EVIDENCE_NOT_AUTHORITY"
    assert safety_decision_envelope({"decision": "ALLOW"})["envelope_hash"] != \
        d["envelope_hash"]

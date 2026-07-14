"""SP0005 hazards/losses/threats/UCA/constraints/barriers. Covers AC-0005-009
..019, 072..084."""
from __future__ import annotations

from tools.safety.losses import validate_losses
from tools.safety.hazards import validate_hazards, traceability
from tools.safety.threats import validate_threats
from tools.safety.uca import validate_ucas, categories_covered
from tools.safety.constraints import validate_constraints
from tools.safety.barriers import (validate_controls, classify_independence,
                                   independence_findings, effective_controls_for,
                                   minimal_cut_sets, shared_failure_domains)
from tools.safety.model import (UNCONTROLLED_CRITICAL_HAZARD, ASSURANCE_COVERAGE_GAP,
                                CONTROL_INDEPENDENCE_NOT_ESTABLISHED,
                                INVALID_SAFETY_SCHEMA, UCA_CATEGORIES)


def _k(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


# ---- losses / hazards / threats / distinctness (AC-0005-009..013) ----------
def test_loss_taxonomy_valid():
    assert not validate_losses({"losses": [
        {"loss_id": "L", "category": "PRIVACY"}]})


def test_bad_loss_category_flagged():
    assert INVALID_SAFETY_SCHEMA in _k(validate_losses({"losses": [
        {"loss_id": "L", "category": "BOGUS"}]}))


def test_threat_taxonomy_distinct_from_hazard():
    assert not validate_threats({"threats": [
        {"threat_id": "T", "external_taxonomy": "OWASP_ASI_2026"}], "hazards": []})


# ---- UCA — 4 STPA categories (AC-0005-013/014) -----------------------------
def test_all_four_uca_categories_supported():
    reg = {"hazards": [{"hazard_id": "H"}], "unsafe_control_actions": [
        {"uca_id": f"U{i}", "control_action": "act", "category": c,
         "hazard_refs": ["H"]} for i, c in enumerate(sorted(UCA_CATEGORIES))]}
    assert not validate_ucas(reg)
    assert categories_covered(reg, "act") == UCA_CATEGORIES


# ---- traceability closure (AC-0005-016..019) -------------------------------
def test_uncontrolled_critical_hazard_fails():
    prog = {"hazards": [{"hazard_id": "H", "criticality": "CRITICAL",
                         "status": "ACTIVE", "loss_refs": ["L"]}],
            "losses": [{"loss_id": "L", "category": "PRIVACY"}],
            "constraints": [{"constraint_id": "C", "hazard_refs": ["H"]}],
            "controls": [], "claims": []}
    assert UNCONTROLLED_CRITICAL_HAZARD in _k(traceability(prog))


def test_hard_block_satisfies_control_requirement():
    prog = {"hazards": [{"hazard_id": "H", "criticality": "CRITICAL",
                         "status": "ACTIVE", "loss_refs": ["L"], "hard_block": True}],
            "losses": [{"loss_id": "L", "category": "LEGAL"}],
            "constraints": [{"constraint_id": "C", "hazard_refs": ["H"]}],
            "controls": [], "claims": []}
    assert UNCONTROLLED_CRITICAL_HAZARD not in _k(traceability(prog))


def test_missing_loss_or_constraint_is_gap():
    prog = {"hazards": [{"hazard_id": "H", "criticality": "HIGH",
                         "status": "ACTIVE", "loss_refs": []}],
            "losses": [], "constraints": [],
            "controls": [{"control_id": "K", "hazard_refs": ["H"]}], "claims": []}
    assert ASSURANCE_COVERAGE_GAP in _k(traceability(prog))


# ---- control barrier graph + independence (AC-0005-072..084) ---------------
def test_control_types_validated():
    reg = {"hazards": [{"hazard_id": "H"}], "controls": [
        {"control_id": "K", "control_type": "PREVENTIVE", "status": "EVIDENCED",
         "hazard_refs": ["H"]}]}
    assert not validate_controls(reg)


def test_declared_only_control_is_not_effective():
    reg = {"controls": [{"control_id": "K", "control_type": "PREVENTIVE",
                         "status": "DECLARED", "hazard_refs": ["H"]}]}
    assert effective_controls_for(reg, "H") == []


def test_shared_model_not_independent():
    a = {"control_id": "A", "failure_domains": {"model": "gpt", "code_path": "x"}}
    b = {"control_id": "B", "failure_domains": {"model": "gpt", "code_path": "y"}}
    assert shared_failure_domains(a, b) == ["model"]
    assert classify_independence(a, b)["classification"] == \
        "INDEPENDENCE_NOT_ESTABLISHED"


def test_unknown_independence_not_treated_as_independent():
    a = {"control_id": "A", "failure_domains": {"code_path": "x"}}  # rest UNKNOWN
    b = {"control_id": "B", "failure_domains": {"code_path": "y"}}
    assert classify_independence(a, b)["classification"] == "UNKNOWN"


def test_established_independence_when_fully_declared_none():
    from tools.safety.model import SHARED_FAILURE_DOMAINS
    a = {"control_id": "A", "failure_domains":
         {k: ("NONE" if k != "code_path" else "x") for k in SHARED_FAILURE_DOMAINS}}
    b = {"control_id": "B", "failure_domains":
         {k: ("NONE" if k != "code_path" else "y") for k in SHARED_FAILURE_DOMAINS}}
    assert classify_independence(a, b)["classification"] == \
        "INDEPENDENCE_ESTABLISHED"


def test_independence_claim_flagged_when_shared():
    reg = {"controls": [
        {"control_id": "A", "failure_domains": {"provider": "p"}},
        {"control_id": "B", "failure_domains": {"provider": "p"}}],
        "independence_claims": [{"control_a": "A", "control_b": "B"}]}
    assert CONTROL_INDEPENDENCE_NOT_ESTABLISHED in _k(independence_findings(reg))


def test_minimal_cut_set_reports_paths():
    reg = {"controls": [
        {"control_id": "A", "status": "EVIDENCED", "hazard_refs": ["H"],
         "barrier_path": "p1"},
        {"control_id": "B", "status": "EVIDENCED", "hazard_refs": ["H"],
         "barrier_path": "p2"}]}
    r = minimal_cut_sets(reg, "H")
    assert r["min_cut_size"] == 2 and r["independent_paths"] == 2

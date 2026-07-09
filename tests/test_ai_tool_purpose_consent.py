"""TOOL-B1 — purpose & consent contract governance tests.

Covers tr.build_purpose_contract and tr.build_consent_contract plus the
endpoint surfacing of a forbidden-purpose conflict. Tests assert ACTUAL
kernel behavior; no product files are modified.
"""
import pytest

from finalis.ai_employee import tool_registry as tr
from tests.conftest import OWNER, MANAGER, VIEWER


# --- purpose contract ------------------------------------------------------
def test_purpose_contract_always_injects_global_forbidden():
    pc = tr.build_purpose_contract(allowed_purposes=["CASE_TRIAGE"])
    # Every global forbidden purpose is present regardless of declaration.
    assert tr.FORBIDDEN_PURPOSES <= set(pc["forbidden_purposes"])
    assert set(pc["allowed_purposes"]) == {"CASE_TRIAGE"}
    assert pc["has_forbidden_purpose"] is False
    assert pc["purpose_conflict"] == []


def test_purpose_contract_cannot_opt_out_of_global_forbidden():
    # Declaring an empty forbidden set still yields the global forbidden set;
    # a descriptor can never remove a globally-forbidden purpose.
    pc = tr.build_purpose_contract(allowed_purposes=["RESEARCH"],
                                   forbidden_purposes=[])
    assert tr.FORBIDDEN_PURPOSES <= set(pc["forbidden_purposes"])


def test_purpose_conflict_detected_for_marketing():
    pc = tr.build_purpose_contract(allowed_purposes=["MARKETING", "CASE_TRIAGE"])
    assert pc["purpose_conflict"] == ["MARKETING"]
    assert pc["has_forbidden_purpose"] is True


def test_purpose_conflict_reports_all_overlaps_sorted():
    pc = tr.build_purpose_contract(
        allowed_purposes=["DATA_EXPORT", "COLLECTIONS", "CASE_TRIAGE"])
    assert pc["purpose_conflict"] == ["COLLECTIONS", "DATA_EXPORT"]
    assert pc["has_forbidden_purpose"] is True


def test_purpose_contract_benign_has_no_conflict():
    pc = tr.build_purpose_contract(
        allowed_purposes=["CASE_TRIAGE", "SUMMARIZATION", "DRAFTING"])
    assert pc["has_forbidden_purpose"] is False
    assert pc["purpose_conflict"] == []


def test_purpose_contract_deterministic_hash():
    a = tr.build_purpose_contract(allowed_purposes=["CASE_TRIAGE"],
                                  declared_intent="triage")
    b = tr.build_purpose_contract(allowed_purposes=["CASE_TRIAGE"],
                                  declared_intent="triage")
    assert a["purpose_contract_hash"] == b["purpose_contract_hash"]
    # A different declared intent changes the hash.
    c = tr.build_purpose_contract(allowed_purposes=["CASE_TRIAGE"],
                                  declared_intent="other")
    assert c["purpose_contract_hash"] != a["purpose_contract_hash"]


# --- consent contract ------------------------------------------------------
@pytest.mark.parametrize("req", sorted(tr.CONSENT_REQUIREMENTS))
def test_consent_can_never_be_overridden(req):
    cc = tr.build_consent_contract(consent_requirement=req, non_overridable=False)
    assert cc["consent_can_be_overridden"] is False


def test_explicit_non_overridable_forces_non_overridable():
    cc = tr.build_consent_contract(
        consent_requirement="EXPLICIT_NON_OVERRIDABLE", non_overridable=False)
    assert cc["non_overridable"] is True
    assert cc["consent_can_be_overridden"] is False


def test_prohibited_forces_non_overridable():
    cc = tr.build_consent_contract(consent_requirement="PROHIBITED",
                                   non_overridable=False)
    assert cc["non_overridable"] is True


def test_declared_non_overridable_is_preserved_when_true():
    # A descriptor may raise the bar even for an otherwise-overridable level.
    cc = tr.build_consent_contract(consent_requirement="EXPLICIT_REQUIRED",
                                   non_overridable=True)
    assert cc["non_overridable"] is True


def test_unknown_consent_requirement_raises():
    with pytest.raises(ValueError):
        tr.build_consent_contract(consent_requirement="MAYBE",
                                  non_overridable=False)


def test_consent_contract_deterministic_hash():
    a = tr.build_consent_contract(consent_requirement="EXPLICIT_REQUIRED",
                                  non_overridable=True, lawful_basis="contract")
    b = tr.build_consent_contract(consent_requirement="EXPLICIT_REQUIRED",
                                  non_overridable=True, lawful_basis="contract")
    assert a["consent_contract_hash"] == b["consent_contract_hash"]


# --- endpoint: forbidden purpose surfaces + fails invariant ----------------
def test_endpoint_forbidden_purpose_surfaces_and_fails_invariant(gate):
    r = gate.register_tool(allowed_purposes=["MARKETING"])
    assert r.status_code == 200
    tool_id = r.json()["tool_id"]
    pol = gate.tool(tool_id, "/policy", actor=OWNER).json()
    # The purpose conflict fails the no_purpose_conflict security invariant.
    assert "no_purpose_conflict" in pol["invariant_matrix"]["failed_invariants"]
    assert pol["invariant_matrix"]["all_pass"] is False
    # The global forbidden purposes are surfaced on the policy capsule.
    assert tr.FORBIDDEN_PURPOSES <= set(
        pol["policy_capsule"]["forbidden_purposes"])
    # A conflicting-purpose tool is not admissible.
    assert pol["policy_capsule"]["admissible"] is False

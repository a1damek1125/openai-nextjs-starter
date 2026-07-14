"""SP0005 regulatory temporal truth + applicability + use cases. Covers
AC-0005-098..124."""
from __future__ import annotations

from tools.safety.regulatory import (validate_sources, check_binding_claims,
                                     applicability, applicability_findings,
                                     is_binding)
from tools.safety.usecases import validate_usecases
from tools.safety.model import (SOURCE_STATUS, DRAFT_SOURCE_USED_AS_BINDING,
                                POLITICAL_AGREEMENT_USED_AS_ENACTED_LAW,
                                LEGAL_TIMELINE_STATE_AMBIGUOUS,
                                LEGAL_APPLICABILITY_UNCERTAIN, INVALID_SAFETY_SCHEMA)


def _k(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


# ---- source taxonomy (AC-0005-098..108) ------------------------------------
def test_all_source_statuses_representable():
    for st in ("BINDING_LAW", "ADOPTED_NOT_YET_APPLICABLE", "FORMAL_PROPOSAL",
               "POLITICAL_AGREEMENT_NOT_YET_ENACTED", "FINAL_OFFICIAL_GUIDANCE",
               "DRAFT_OFFICIAL_GUIDANCE", "OFFICIAL_CONSULTATION",
               "INTERNATIONAL_STANDARD", "RESEARCH", "VENDOR_GUIDANCE"):
        assert st in SOURCE_STATUS


def test_source_missing_url_flagged():
    assert INVALID_SAFETY_SCHEMA in _k(validate_sources({"sources": [
        {"source_id": "S", "source_status": "BINDING_LAW"}]}))


# ---- draft/political ≠ law (AC-0005-109..111, INV-0005-18/19/20) -----------
def test_draft_used_as_binding_fails():
    reg = {"sources": [{"source_id": "S", "source_status": "DRAFT_OFFICIAL_GUIDANCE",
                        "used_as": "BINDING", "official_url": "u"}]}
    assert DRAFT_SOURCE_USED_AS_BINDING in _k(check_binding_claims(reg))


def test_political_agreement_used_as_law_fails():
    reg = {"sources": [{"source_id": "S",
                        "source_status": "POLITICAL_AGREEMENT_NOT_YET_ENACTED",
                        "used_as": "BINDING", "official_url": "u"}]}
    assert POLITICAL_AGREEMENT_USED_AS_ENACTED_LAW in _k(check_binding_claims(reg))


def test_proposed_date_as_applicable_flagged():
    reg = {"sources": [{"source_id": "S", "source_status": "FORMAL_PROPOSAL",
                        "applicable_date_source": "proposal_date",
                        "official_url": "u"}]}
    assert LEGAL_TIMELINE_STATE_AMBIGUOUS in _k(check_binding_claims(reg))


def test_binding_law_is_binding_but_adopted_is_not():
    assert is_binding({"source_status": "BINDING_LAW"})
    assert not is_binding({"source_status": "ADOPTED_NOT_YET_APPLICABLE"})


# ---- applicability (AC-0005-120/121) ---------------------------------------
def test_adopted_not_yet_applicable():
    assert applicability({"source_status": "ADOPTED_NOT_YET_APPLICABLE"}, {}) == \
        "NOT_YET_APPLICABLE"


def test_ambiguous_returns_qualified_review():
    assert applicability({"source_status": "BINDING_LAW"},
                         {"ambiguous": True}) == "UNCERTAIN_REQUIRES_QUALIFIED_REVIEW"


def test_non_binding_returns_qualified_review():
    assert applicability({"source_status": "DRAFT_OFFICIAL_GUIDANCE"}, {}) == \
        "UNCERTAIN_REQUIRES_QUALIFIED_REVIEW"


def test_high_impact_uncertain_flagged():
    reg = {"sources": [{"source_id": "S", "source_status": "DRAFT_OFFICIAL_GUIDANCE",
                        "high_impact": True, "official_url": "u"}]}
    assert LEGAL_APPLICABILITY_UNCERTAIN in _k(applicability_findings(reg, {}))


# ---- use cases (AC-0005-122/123) -------------------------------------------
def test_internal_class_cannot_auto_create_legal():
    reg = {"use_cases": [{"use_case_id": "U",
                          "finalis_impact_class": "FINALIS_IMPACT_5",
                          "capability": "rank", "purpose": "p",
                          "affected_subject": "candidate",
                          "legal_classification": "HIGH_RISK",
                          "legal_classification_source": "AUTO_FROM_IMPACT"}]}
    assert INVALID_SAFETY_SCHEMA in _k(validate_usecases(reg))


def test_use_case_needs_capability_purpose_subject():
    reg = {"use_cases": [{"use_case_id": "U",
                          "finalis_impact_class": "FINALIS_IMPACT_2"}]}
    assert INVALID_SAFETY_SCHEMA in _k(validate_usecases(reg))


def test_valid_use_case():
    reg = {"use_cases": [{"use_case_id": "U",
                          "finalis_impact_class": "FINALIS_IMPACT_1",
                          "capability": "schedule", "purpose": "book",
                          "affected_subject": "candidate",
                          "legal_classification_source": "QUALIFIED_REVIEW_REQUIRED"}]}
    assert not validate_usecases(reg)

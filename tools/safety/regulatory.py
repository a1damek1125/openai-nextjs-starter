"""Regulatory Source Registry + Temporal Truth + Applicability (SP0005 §10.7,
D-0005-46..50, §2.4, INV-0005-17/18/19/20).

A regulatory matter has MANY dates (proposal / political_agreement / adoption /
publication / entry_into_force / general_application / special_application /
consultation_close / transition_deadline) — never one `effective_date`
(D-0005-46). Legal state (source_status) and timeline state are SEPARATE
(D-0005-47). A draft is not binding law (INV-0005-18); a political agreement is
not enacted law (INV-0005-19); a proposed date is not an applicable date
(INV-0005-20). Applicability is evaluated separately, and where ambiguous returns
UNCERTAIN_REQUIRES_QUALIFIED_REVIEW — SP0005 is not a legal oracle (D-0005-50).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, SOURCE_STATUS, NON_BINDING_STATUS,
                    REG_DATE_TYPES, APPLICABLE_DATE_TYPES, APPLICABILITY,
                    INVALID_SAFETY_SCHEMA, SOURCE_STATUS_UNKNOWN,
                    LEGAL_TIMELINE_STATE_AMBIGUOUS, DRAFT_SOURCE_USED_AS_BINDING,
                    POLITICAL_AGREEMENT_USED_AS_ENACTED_LAW,
                    LEGAL_APPLICABILITY_UNCERTAIN)


def source_index(reg: dict) -> dict[str, dict]:
    return {s["source_id"]: s for s in reg.get("sources", [])}


def validate_sources(reg: dict) -> list[Finding]:
    out: list[Finding] = []
    seen: set[str] = set()
    for s in reg.get("sources", []):
        sid = s.get("source_id")
        if sid in seen:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, sid,
                               "duplicate source_id", {}))
        seen.add(sid)
        if s.get("source_status") not in SOURCE_STATUS:
            out.append(Finding(SOURCE_STATUS_UNKNOWN, P1, sid or "-",
                               f"invalid/unknown source_status "
                               f"{s.get('source_status')!r}", {}))
        # legal review status must be explicit and separate from source status
        if not s.get("official_url"):
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, sid or "-",
                               "regulatory source missing official_url "
                               "(AC-0005-238)", {}))
    return out


def is_binding(source: dict) -> bool:
    """Only BINDING_LAW is treated as binding; ADOPTED_NOT_YET_APPLICABLE is law
    but not yet applicable (still not binding *now*)."""
    return source.get("source_status") == "BINDING_LAW"


def check_binding_claims(reg: dict) -> list[Finding]:
    """A source USED as binding (used_as='BINDING') that is actually draft /
    proposal / political-agreement is a hard error (INV-0005-18/19)."""
    out: list[Finding] = []
    for s in reg.get("sources", []):
        sid = s.get("source_id", "-")
        # normalize casing/whitespace so 'binding'/'Binding'/'BINDING ' cannot
        # evade the gate (SWARM-N E3; INV-0005-18/19)
        used = str(s.get("used_as", "")).strip().upper()
        status = s.get("source_status")
        if used == "BINDING" and status in NON_BINDING_STATUS:
            if status == "POLITICAL_AGREEMENT_NOT_YET_ENACTED":
                out.append(Finding(POLITICAL_AGREEMENT_USED_AS_ENACTED_LAW, P0,
                                   sid, "a political agreement is used as enacted "
                                   "law (INV-0005-19)", {}))
            elif status in ("DRAFT_OFFICIAL_GUIDANCE", "OFFICIAL_CONSULTATION",
                            "FORMAL_PROPOSAL"):
                out.append(Finding(DRAFT_SOURCE_USED_AS_BINDING, P0, sid,
                                   f"a {status} source is used as binding law "
                                   "(INV-0005-18)", {}))
            else:
                out.append(Finding(DRAFT_SOURCE_USED_AS_BINDING, P0, sid,
                                   f"a non-binding ({status}) source is used as "
                                   "binding", {}))
        # an 'applicable' date must be drawn from a real applicability date; any
        # pre-enactment date (proposal / political-agreement / consultation /
        # publication) as the applicable date is ambiguous (SWARM-N E5;
        # INV-0005-20)
        ads = s.get("applicable_date_source")
        if ads is not None and ads not in APPLICABLE_DATE_TYPES:
            out.append(Finding(LEGAL_TIMELINE_STATE_AMBIGUOUS, P1, sid,
                               f"applicable date derived from a non-applicability "
                               f"date ({ads}) (INV-0005-20)", {}))
    return out


def applicability(source: dict, situation: dict) -> str:
    """Evaluate applicability separately from source status (D-0005-49). Returns a
    value in APPLICABILITY. Ambiguity => UNCERTAIN_REQUIRES_QUALIFIED_REVIEW."""
    # not-yet-applicable if adopted but its application date is in the future
    if source.get("source_status") == "ADOPTED_NOT_YET_APPLICABLE":
        return "NOT_YET_APPLICABLE"
    if source.get("source_status") in NON_BINDING_STATUS:
        return "UNCERTAIN_REQUIRES_QUALIFIED_REVIEW"
    juris = source.get("jurisdiction")
    if juris and situation.get("jurisdiction") and juris != situation["jurisdiction"]:
        return "DOES_NOT_APPLY"
    if situation.get("ambiguous"):
        return "UNCERTAIN_REQUIRES_QUALIFIED_REVIEW"
    if source.get("source_status") == "BINDING_LAW":
        return "APPLIES" if not situation.get("possibly") else "POSSIBLY_APPLIES"
    return "UNCERTAIN_REQUIRES_QUALIFIED_REVIEW"


def applicability_findings(reg: dict, situation: dict) -> list[Finding]:
    out: list[Finding] = []
    for s in reg.get("sources", []):
        if applicability(s, situation) == "UNCERTAIN_REQUIRES_QUALIFIED_REVIEW" \
                and s.get("high_impact"):
            out.append(Finding(LEGAL_APPLICABILITY_UNCERTAIN, P1,
                               s.get("source_id", "-"),
                               "high-impact source applicability is uncertain — "
                               "requires qualified review (D-0005-50)", {}))
    return out

"""Evidence requirement profiles for critical decisions.

Which decision needs which admissible evidence — the contract Quote
Builder, Payment, Fulfillment, Complaint and Warranty will call later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from .models import ADMISSIBLE_STATES, EvidenceObject


@dataclass
class EvidenceRequirementProfile:
    decision_type: str
    required_types: list[list[str]]     # each inner list = alternatives
    min_trust: float = 0.60
    human_verification_required: bool = False
    min_distinct_objects: int = 1
    max_age_days: Optional[int] = None
    compliance_review_required: bool = False
    human_verified_fallback: bool = False   # human proof can replace file


REQUIREMENT_PROFILES: dict[str, EvidenceRequirementProfile] = {
    "QUOTE_DRAFT": EvidenceRequirementProfile(
        "QUOTE_DRAFT", required_types=[], min_trust=0.0,
        min_distinct_objects=0),
    "QUOTE_SEND": EvidenceRequirementProfile(
        "QUOTE_SEND", required_types=[["scope_evidence",
                                       "installation_photo"]],
        min_trust=0.5),
    "QUOTE_ACCEPT": EvidenceRequirementProfile(
        "QUOTE_ACCEPT", required_types=[["acceptance_evidence"]],
        min_trust=0.6),
    "PAYMENT_MARK_PAID": EvidenceRequirementProfile(
        "PAYMENT_MARK_PAID", required_types=[["payment_proof"]],
        min_trust=0.7, human_verified_fallback=True),
    "FULFILLMENT_COMPLETED": EvidenceRequirementProfile(
        "FULFILLMENT_COMPLETED",
        required_types=[["fulfillment_photo", "completion_protocol",
                         "technician_note"]],
        min_trust=0.6, max_age_days=30),
    "WON_COMPLETED": EvidenceRequirementProfile(
        "WON_COMPLETED",
        required_types=[["payment_proof"],
                        ["fulfillment_photo", "completion_protocol",
                         "technician_note"]],
        min_trust=0.7, min_distinct_objects=2),
    "COMPLAINT_RESOLVED": EvidenceRequirementProfile(
        "COMPLAINT_RESOLVED",
        required_types=[["resolution_note", "client_confirmation"]],
        min_trust=0.6, human_verification_required=True),
    "WARRANTY_DECISION": EvidenceRequirementProfile(
        "WARRANTY_DECISION",
        required_types=[["warranty_document"], ["defect_evidence"]],
        min_trust=0.7, compliance_review_required=True),
    "CHANGE_ORDER_APPROVAL": EvidenceRequirementProfile(
        "CHANGE_ORDER_APPROVAL",
        required_types=[["accepted_quote_reference"],
                        ["scope_delta_evidence"]],
        min_trust=0.6),
}


@dataclass
class RequirementCheck:
    ok: bool
    missing: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def check_requirements(decision_type: str,
                       evidence: list[EvidenceObject], *,
                       trust_by_id: Optional[dict[str, float]] = None,
                       human_verified: bool = False,
                       now: Optional[datetime] = None) -> RequirementCheck:
    profile = REQUIREMENT_PROFILES.get(decision_type)
    if profile is None:
        return RequirementCheck(False,
                                reasons=[f"unknown decision "
                                         f"{decision_type} — deny by "
                                         "default"])
    now = now or datetime.utcnow()
    trust_by_id = trust_by_id or {}
    # Only admissible + trusted + fresh evidence counts.
    usable = []
    for ev in evidence:
        if ev.state not in ADMISSIBLE_STATES:
            continue
        if trust_by_id.get(ev.id, 1.0) < profile.min_trust:
            continue
        if profile.max_age_days is not None and \
                now - ev.created_at > timedelta(days=profile.max_age_days):
            continue
        usable.append(ev)
    missing, reasons = [], []
    for alternatives in profile.required_types:
        if not any(ev.evidence_type in alternatives for ev in usable):
            if profile.human_verified_fallback and human_verified:
                reasons.append(
                    f"{'/'.join(alternatives)}: satisfied by explicit "
                    "human verification instead of a file")
                continue
            missing.append(" or ".join(alternatives))
    if profile.human_verification_required and not human_verified:
        reasons.append("human verification required for this decision")
    if profile.compliance_review_required:
        reasons.append("compliance review required for this decision")
    if len(usable) < profile.min_distinct_objects \
            and not (profile.human_verified_fallback and human_verified):
        reasons.append(f"needs {profile.min_distinct_objects} distinct "
                       f"admissible evidence objects, has {len(usable)}")
    ok = not missing and not any(
        r.startswith(("human verification required",
                      "needs ")) for r in reasons)
    return RequirementCheck(ok, missing, reasons)

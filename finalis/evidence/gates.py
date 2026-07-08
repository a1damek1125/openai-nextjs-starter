"""EvidenceAdmissibilityGate + AIFileAccessGate.

Hard blockers always win. A perfect trust score cannot admit malware;
a perfect risk score cannot cross a tenant boundary; and no document
content is ever treated as an instruction.
"""
from __future__ import annotations

from typing import Optional

from .models import (ADMISSIBLE_STATES, AIFileAccessDecision,
                     EvidenceAdmissibilityDecision, EvidenceObject)
from .scores import EvidenceThresholds

ADMISSIBILITY_DECISIONS = {"ADMISSIBLE", "ADMISSIBLE_WITH_LIMITS",
                           "HUMAN_REVIEW_REQUIRED", "REJECTED",
                           "QUARANTINE_REQUIRED",
                           "COMPLIANCE_REVIEW_REQUIRED",
                           "DENIED_BY_HARD_BLOCKER"}


def admissibility_gate(ev: EvidenceObject, *, tenant_id: str,
                       case_id: Optional[str] = None,
                       file_risk: float = 0.0, trust: float = 1.0,
                       actor_has_permission: bool = True,
                       actor_has_sensitive_clearance: bool = False,
                       thresholds: Optional[EvidenceThresholds] = None
                       ) -> EvidenceAdmissibilityDecision:
    t = thresholds or EvidenceThresholds()
    hard: list[str] = []
    if ev.tenant_id != tenant_id:
        hard.append("tenant mismatch")
    if case_id is not None and ev.case_id != case_id:
        hard.append("case mismatch")
    if ev.integrity is None:
        hard.append("missing integrity record")
    elif not ev.integrity.valid:
        hard.append("checksum mismatch — integrity failed")
    if ev.state == "MALWARE_SUSPECTED":
        hard.append("malware suspected")
    if ev.state == "SCAN_FAILED":
        hard.append("required scan failed")
    if ev.state == "REJECTED":
        hard.append("evidence was rejected")
    if ev.state in ("UPLOADED", "QUARANTINED", "SCAN_PENDING"):
        hard.append("evidence is still quarantined/unscanned")
    if ev.state == "INTEGRITY_FAILED":
        hard.append("integrity failure blocks all usage")
    if ev.state == "DELETED_SOFT":
        hard.append("evidence was deleted")
    if not actor_has_permission:
        hard.append("actor lacks required permission")
    if ev.sensitivity in ("sensitive", "legal") \
            and not actor_has_sensitive_clearance and not ev.human_verified:
        hard.append("sensitive evidence without clearance")
    if hard:
        # Quarantine gets its own actionable verdict; everything else is
        # a plain hard denial.
        if "evidence is still quarantined/unscanned" in hard \
                and len(hard) == 1:
            return EvidenceAdmissibilityDecision(
                "QUARANTINE_REQUIRED", hard, hard)
        return EvidenceAdmissibilityDecision(
            "DENIED_BY_HARD_BLOCKER", hard, hard)

    if ev.sensitivity == "legal":
        return EvidenceAdmissibilityDecision(
            "COMPLIANCE_REVIEW_REQUIRED",
            ["legal-sensitivity evidence needs compliance review"])
    if file_risk > t.max_auto_file_risk or ev.state == "NEEDS_HUMAN_REVIEW":
        return EvidenceAdmissibilityDecision(
            "HUMAN_REVIEW_REQUIRED",
            [f"file risk {file_risk:.2f} above auto threshold"
             if file_risk > t.max_auto_file_risk
             else "flagged for human review"])
    if trust < t.min_decision_trust:
        return EvidenceAdmissibilityDecision(
            "HUMAN_REVIEW_REQUIRED",
            [f"trust {trust:.2f} below decision minimum"])
    if trust < t.limits_band_trust or ev.meta.active_content \
            or ev.state == "ADMISSIBLE_WITH_LIMITS":
        return EvidenceAdmissibilityDecision(
            "ADMISSIBLE_WITH_LIMITS",
            ["usable with limits (moderate trust or active content)"])
    return EvidenceAdmissibilityDecision("ADMISSIBLE", ["all checks passed"])


AI_ACCESS_DECISIONS = {"ALLOW_METADATA_ONLY", "ALLOW_SAFE_DERIVATIVE",
                       "ALLOW_REDACTED_DERIVATIVE",
                       "REQUIRE_HUMAN_APPROVAL", "DENY"}

_AI_DENY_STATES = {"UPLOADED", "QUARANTINED", "SCAN_PENDING", "SCAN_FAILED",
                   "MALWARE_SUSPECTED", "PARSER_FAILED", "REJECTED",
                   "INTEGRITY_FAILED", "DELETED_SOFT"}


def ai_file_access_gate(ev: EvidenceObject, *, tenant_id: str,
                        purpose: str = "fact_extraction",
                        task_scoped_authorization: bool = False,
                        requested_raw: bool = False,
                        thresholds: Optional[EvidenceThresholds] = None
                        ) -> AIFileAccessDecision:
    """Documents provide facts, never commands — and AI never reads what
    the fabric has not cleared."""
    t = thresholds or EvidenceThresholds()
    if ev.tenant_id != tenant_id:
        return AIFileAccessDecision("DENY", ["tenant mismatch"])
    if ev.state in _AI_DENY_STATES:
        return AIFileAccessDecision(
            "DENY", [f"evidence state {ev.state} is not AI-readable"])
    if ev.integrity is None or not ev.integrity.valid:
        return AIFileAccessDecision("DENY", ["integrity not proven"])
    if requested_raw:
        if ev.injection_risk > t.max_injection_for_raw_ai:
            return AIFileAccessDecision(
                "ALLOW_SAFE_DERIVATIVE",
                ["raw content refused: injection-style instructions "
                 "detected — safe derivative only (facts, not commands)"])
        if ev.source.kind != "staff":
            return AIFileAccessDecision(
                "ALLOW_SAFE_DERIVATIVE",
                ["external content: AI reads the safe derivative, "
                 "never the raw file"])
    if ev.sensitivity in ("sensitive", "legal"):
        if not task_scoped_authorization:
            return AIFileAccessDecision(
                "REQUIRE_HUMAN_APPROVAL",
                ["sensitive evidence needs task-scoped authorization"])
        return AIFileAccessDecision(
            "ALLOW_REDACTED_DERIVATIVE",
            ["sensitive: redacted derivative only"])
    if any(d.kind in ("safe_text", "thumbnail") for d in ev.derivatives):
        return AIFileAccessDecision(
            "ALLOW_SAFE_DERIVATIVE", ["safe derivative available"])
    return AIFileAccessDecision(
        "ALLOW_METADATA_ONLY",
        ["no safe derivative yet — metadata only"])

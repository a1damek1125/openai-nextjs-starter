"""Safety Evidence Registry + Applicability + Freshness (SP0005 §10.9, D-0005-42/
43, INV-0005-16).

Evidence records the CONTEXT in which it is valid: code version, policy version,
model/provider version, semantic epoch, contract version, environment, oracle
version. A material change to any of these yields EVIDENCE_REVIEW_REQUIRED /
EVIDENCE_STALE — stale critical evidence cannot silently support current assurance
(D-0005-43, INV-0005-16, AC-0005-097).
"""
from __future__ import annotations

from .model import (Finding, P1, EVIDENCE_STATUS, INVALID_SAFETY_SCHEMA)

APPLICABILITY_KEYS = ("code_version", "policy_version", "semantic_epoch",
                      "provider_version", "environment", "oracle_version")


def validate_evidence(reg: dict) -> list[Finding]:
    out: list[Finding] = []
    seen: set[str] = set()
    for e in reg.get("evidence", []):
        eid = e.get("evidence_id")
        if eid in seen:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, eid,
                               "duplicate evidence_id", {}))
        seen.add(eid)
        st = e.get("status", "CURRENT")
        if st not in EVIDENCE_STATUS:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, eid or "-",
                               f"invalid evidence status {st!r}", {}))
    return out


def applicable(evidence: dict, current: dict) -> bool:
    """Evidence applies only if every declared applicability key still matches the
    current context. A declared key that changed => not applicable."""
    for k in APPLICABILITY_KEYS:
        want = evidence.get(k)
        if want is not None and current.get(k) is not None and want != current[k]:
            return False
    return True


def freshness(evidence: dict, current: dict) -> str:
    """CURRENT if still applicable; else EVIDENCE_STALE (a material input changed).
    Deterministic — takes the current context, not the clock."""
    if evidence.get("status") in ("EVIDENCE_STALE", "SUPERSEDED"):
        return evidence["status"]
    return "CURRENT" if applicable(evidence, current) else "EVIDENCE_STALE"

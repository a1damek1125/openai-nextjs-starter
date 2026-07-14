"""Incident + Near-Miss Registry (SP0005 D-0005-70/71/72, §10, INV-0005-24/25).

A NEAR MISS (hazardous condition occurred but loss prevented) is safety evidence
even without a realized loss (INV-0005-24). Neither a near miss nor an incident can
DIRECTLY mutate production policy (INV-0005-25): the flow is analysis → control-gap
candidate → test → governed change (D-0005-71). Internal severity is separate from
legal reportability (D-0005-72, AC-0005-166).
"""
from __future__ import annotations

from .model import (Finding, P1, INCIDENT_STATES, INVALID_SAFETY_SCHEMA,
                    INCIDENT_EVIDENCE_INCOMPLETE, NEAR_MISS_REVIEW_REQUIRED)


def validate_incidents(reg: dict) -> list[Finding]:
    out: list[Finding] = []
    for i in reg.get("incidents", []):
        iid = i.get("incident_id", "-")
        if i.get("status") not in INCIDENT_STATES:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, iid,
                               f"invalid incident status {i.get('status')!r}", {}))
        # internal severity and legal reportability must be separate fields
        if "internal_severity" not in i or "legal_reportability_status" not in i:
            out.append(Finding(INCIDENT_EVIDENCE_INCOMPLETE, P1, iid,
                               "incident must record internal_severity AND "
                               "legal_reportability_status separately "
                               "(AC-0005-166)", {}))
        # an incident may not directly mutate policy
        if i.get("direct_policy_mutation"):
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, iid,
                               "incident cannot directly self-modify production "
                               "policy (INV-0005-25)", {}))
    return out


def near_miss_findings(reg: dict) -> list[Finding]:
    """An unreviewed near miss surfaces a review requirement (safety evidence)."""
    out: list[Finding] = []
    for n in reg.get("near_misses", []):
        nid = n.get("near_miss_id", "-")
        if n.get("direct_policy_mutation"):
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, nid,
                               "near miss cannot directly mutate production policy "
                               "(INV-0005-25, D-0005-71)", {}))
        if n.get("status", "DETECTED") == "DETECTED" and not n.get("reviewed"):
            out.append(Finding(NEAR_MISS_REVIEW_REQUIRED, P1, nid,
                               "near miss is safety evidence and requires review "
                               "(INV-0005-24)", {}))
    return out

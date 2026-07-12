"""Assurance Case Model + Coverage Closure + Defeater Propagation (SP0005
D-0005-40..45, §11.9/§11.10, INV-0005-15/16).

A critical claim requires claim + argument + evidence + context + assumption +
defeater + residual uncertainty (D-0005-40). A claim cannot be SUPPORTED_CURRENT
while a blocking defeater is open (D-0005-45, INV-0005-15) or while its critical
evidence is stale (INV-0005-16). Defeaters propagate: a challenged claim forces
REASSESSMENT_REQUIRED on dependents (D-0005-45, §11.10).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, CLAIM_STATES, EVIDENCE_STATUS,
                    CRITICAL_DEFEATER_OPEN, ASSURANCE_EVIDENCE_STALE,
                    INVALID_SAFETY_SCHEMA)


def claim_index(reg: dict) -> dict[str, dict]:
    return {c["claim_id"]: c for c in reg.get("claims", [])}


def validate_claims(reg: dict) -> list[Finding]:
    out: list[Finding] = []
    seen: set[str] = set()
    for c in reg.get("claims", []):
        cid = c.get("claim_id")
        if cid in seen:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, cid,
                               "duplicate claim_id", {}))
        seen.add(cid)
        if c.get("status") not in CLAIM_STATES:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, cid or "-",
                               f"invalid claim status {c.get('status')!r}", {}))
    return out


def open_defeaters(reg: dict) -> list[Finding]:
    """A claim asserting SUPPORTED_CURRENT while a blocking (critical, open)
    defeater targets it is a hard failure (INV-0005-15)."""
    out: list[Finding] = []
    defeaters = {d["defeater_id"]: d for d in reg.get("defeaters", [])}
    for c in reg.get("claims", []):
        if c.get("status") != "SUPPORTED_CURRENT":
            continue
        for did in c.get("defeater_refs", []):
            d = defeaters.get(did)
            if d and d.get("severity") == "CRITICAL" and \
                    d.get("status", "OPEN") == "OPEN":
                out.append(Finding(CRITICAL_DEFEATER_OPEN, P0, c["claim_id"],
                                   f"claim SUPPORTED_CURRENT but critical defeater "
                                   f"{did} is OPEN (INV-0005-15)", {}))
    return out


def stale_critical_evidence(reg: dict) -> list[Finding]:
    """A SUPPORTED_CURRENT critical claim resting on STALE evidence is a hard
    failure (INV-0005-16)."""
    out: list[Finding] = []
    ev = {e["evidence_id"]: e for e in reg.get("evidence", [])}
    for c in reg.get("claims", []):
        if c.get("status") != "SUPPORTED_CURRENT" or not c.get("critical"):
            continue
        for eid in c.get("evidence_refs", []):
            e = ev.get(eid)
            if e and e.get("status") in ("EVIDENCE_STALE", "SUPERSEDED"):
                out.append(Finding(ASSURANCE_EVIDENCE_STALE, P1, c["claim_id"],
                                   f"critical claim rests on stale evidence {eid} "
                                   "(INV-0005-16)", {}))
    return out


def propagate_defeater(reg: dict, defeater_id: str) -> dict:
    """A critical open defeater challenges its target claims and marks dependents
    REASSESSMENT_REQUIRED (§11.10)."""
    challenged, reassess = [], []
    for c in reg.get("claims", []):
        if defeater_id in c.get("defeater_refs", []):
            challenged.append(c["claim_id"])
    challenged_set = set(challenged)
    for c in reg.get("claims", []):
        if c["claim_id"] in challenged_set:
            continue
        if challenged_set & set(c.get("depends_on", [])):
            reassess.append(c["claim_id"])
    return {"defeater": defeater_id, "challenged": sorted(challenged),
            "reassessment_required": sorted(reassess)}

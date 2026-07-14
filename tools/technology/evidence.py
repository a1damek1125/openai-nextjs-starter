"""Evidence Registry + freshness engine (SP0004 §10.3/§13.5, D-0004-56).

Every technology claim cites an evidence record with source URL, source type,
retrieval date, technology version and applicability. Freshness is
technology-relative: fast-moving technologies get shorter horizons (D-0004-56).
Vendor documentation is authoritative for its own interface/version, NOT for
comparative superiority (§17.2) — the source_type carries that distinction.
"""
from __future__ import annotations

from .model import (Finding, P1, P2, EVIDENCE_STATES, EVIDENCE_TYPES,
                    INVALID_TDR, INSUFFICIENT_EVIDENCE)

# freshness horizon (days) by volatility class — explicit, not universal
HORIZON_DAYS = {"VERY_HIGH": 90, "HIGH": 180, "MEDIUM": 365, "LOW": 730,
                "FOUNDATIONAL": 1095}


def validate_evidence(reg: dict) -> list[Finding]:
    out: list[Finding] = []
    seen: set[str] = set()
    for e in reg.get("evidence", []):
        eid = e.get("evidence_id", "-")
        if eid in seen:
            out.append(Finding(INVALID_TDR, P1, eid, "duplicate evidence_id", {}))
        seen.add(eid)
        if not e.get("source_url"):
            out.append(Finding(INSUFFICIENT_EVIDENCE, P1, eid,
                               "evidence missing source_url (AC-0004-159)", {}))
        if e.get("source_type") not in EVIDENCE_TYPES:
            out.append(Finding(INVALID_TDR, P1, eid,
                               f"invalid source_type {e.get('source_type')!r}",
                               {}))
        if not e.get("retrieved_at"):
            out.append(Finding(INVALID_TDR, P1, eid,
                               "evidence missing retrieved_at (AC-0004-024)", {}))
        fs = e.get("freshness_status")
        if fs is not None and fs not in EVIDENCE_STATES:
            out.append(Finding(INVALID_TDR, P1, eid,
                               f"invalid freshness_status {fs!r}", {}))
    return out


def freshness_status(evidence: dict, *, today: str,
                     volatility: str = "MEDIUM") -> str:
    """Compare retrieved_at + horizon to `today` (ISO date strings). Determinism:
    `today` is passed in, never read from the clock."""
    retrieved = evidence.get("retrieved_at")
    if not retrieved:
        return "STALE"
    horizon = HORIZON_DAYS.get(volatility, 365)
    # ISO date arithmetic without importing datetime-at-runtime randomness:
    from datetime import date
    try:
        r = date.fromisoformat(str(retrieved)[:10])
        t = date.fromisoformat(str(today)[:10])
    except ValueError:
        return "STALE"
    age = (t - r).days
    if age <= horizon:
        return "CURRENT"
    if age <= horizon * 2:
        return "REVIEW_DUE"
    return "STALE"


def stale_evidence(reg: dict, *, today: str,
                   volatility_by_id: dict | None = None) -> list[Finding]:
    volatility_by_id = volatility_by_id or {}
    out: list[Finding] = []
    for e in reg.get("evidence", []):
        eid = e.get("evidence_id", "-")
        vol = volatility_by_id.get(eid, "MEDIUM")
        st = freshness_status(e, today=today, volatility=vol)
        if st == "STALE":
            out.append(Finding(INSUFFICIENT_EVIDENCE, P2, eid,
                               "evidence is stale (advisory review)", {}))
    return out

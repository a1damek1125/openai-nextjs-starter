"""Advisory agent-readiness diagnostics (SP0008 §readiness, D-0008-38/39).

Answers one question per surface: "does the inventory know ENOUGH about this
surface for an autonomous agent to act on it safely?" — and it is purely
DIAGNOSTIC. A READY verdict grants NO authority (INV-0008-39): authority lives in
the product's own gates (RBAC, approval, authority boundary). Readiness is
fail-closed: any hard blocker (unknown tenant scope, unknown authority, unknown
external effect, unknown idempotency, unknown approval requirement, or a witness
with UNKNOWN_OUTCOME) makes the surface NOT_READY. Absence of a blocker is
"no known blocker", never a positive grant.
"""
from __future__ import annotations

from typing import Iterable

from .model import Finding, P2, AGENT_READINESS_BLOCKED

HARD_BLOCKERS = (
    "unknown_tenant_scope",
    "unknown_authority",
    "unknown_external_effect",
    "unknown_idempotency",
    "unknown_approval_requirement",
    "unknown_outcome_witness",
)


def assess_surface(surface, *, crit_vec: dict, reach: dict,
                   consumer: dict, witnesses: list) -> dict:
    """Compute the readiness diagnostic for one surface. Fail-closed."""
    blockers = []
    # tenant / authority — from the criticality vector's UNKNOWN hard flags
    if crit_vec.get("tenant") == "UNKNOWN":
        blockers.append("unknown_tenant_scope")
    if crit_vec.get("authority") == "UNKNOWN":
        blockers.append("unknown_authority")
    # external effect — from reachability exactness
    if reach.get("exactness") == "UNKNOWN":
        blockers.append("unknown_external_effect")
    # idempotency — not derivable statically for write routes => unknown
    if surface.surface_kind == "HTTP_ROUTE":
        blockers.append("unknown_idempotency")
        blockers.append("unknown_approval_requirement")
    # witness outcome
    if any(w.get("outcome") == "UNKNOWN_OUTCOME" for w in witnesses):
        blockers.append("unknown_outcome_witness")

    blockers = sorted(set(b for b in blockers if b in HARD_BLOCKERS))
    return {
        "surface_id": surface.surface_id,
        "verdict": "NOT_READY" if blockers else "NO_KNOWN_BLOCKER",
        "hard_blockers": blockers,
        "grants_authority": False,   # never
        "note": "diagnostic only; grants no authority (INV-0008-39)",
    }


def readiness_findings(assessment: dict) -> list[Finding]:
    out: list[Finding] = []
    if assessment["verdict"] == "NOT_READY":
        out.append(Finding(
            AGENT_READINESS_BLOCKED, P2, assessment["surface_id"],
            f"surface is NOT_READY for autonomous action: "
            f"{assessment['hard_blockers']} (advisory; grants no authority)",
            {"hard_blockers": assessment["hard_blockers"]}))
    return out


def readiness_summary(assessments: Iterable[dict]) -> dict:
    assessments = list(assessments)
    ready = [a for a in assessments if a["verdict"] == "NO_KNOWN_BLOCKER"]
    return {
        "total": len(assessments),
        "no_known_blocker": len(ready),
        "not_ready": len(assessments) - len(ready),
        "grants_authority": False,
    }

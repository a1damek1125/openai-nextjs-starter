"""Continuous requalification (SP0011 §2.1.R, §11.27, D-0011-025/026/100..111,
AC-0011-281..292, 300).

A score may fall; a qualification may expire; a configuration change may
invalidate part or all of the score. This module registers drift detectors
(input / outcome / calibration / judge / provider / harness / policy / tool /
memory / scenario-saturation), computes the requalification IMPACT CONE for a
material change (which credits become STALE), and validates that incremental
recomputation equals full recomputation on fixtures (D-0011-102). Historical
scores remain immutable (D-0011-104); new scorecards supersede, never overwrite.
Continuous evaluation NEVER auto-promotes production (D-0011-109).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P1

DRIFT_KINDS = ("input", "outcome", "calibration", "judge", "provider", "harness",
               "policy", "tool", "memory", "scenario_saturation")

# which credit domains a change to a configuration field invalidates (impact cone)
_CHANGE_IMPACT = {
    "model_identity": ["D1", "D2", "D8"], "harness_identity": ["D2", "D4", "D9"],
    "prompt_epoch": ["D1", "D5"], "policy_epoch": ["D3", "D6"],
    "tool_versions": ["D4"], "provider_adapters": ["D4"],
    "memory_snapshot": ["D5"], "languages": ["D6"],
}


def drift_registry() -> dict:
    return {k: {"kind": k, "detector": f"detect_{k}_drift",
                "triggers_requalification": True} for k in DRIFT_KINDS}


def impact_cone(changed_fields: list, claims: dict) -> dict:
    """Given a set of changed material fields, the affected domains and the
    credits that become STALE."""
    domains = set()
    for f in changed_fields:
        domains.update(_CHANGE_IMPACT.get(f, []))
    stale = sorted(cid for cid, c in claims.items()
                   if c["domain_id"] in domains)
    return {"changed_fields": sorted(changed_fields),
            "affected_domains": sorted(domains),
            "stale_credits": stale, "stale_count": len(stale)}


def incremental_equals_full(incremental_score: int, full_score: int) -> dict:
    """The incremental recomputation must equal the full-recompute reference
    oracle on fixtures (D-0011-102)."""
    return {"incremental": incremental_score, "full": full_score,
            "equal": incremental_score == full_score}


def evidence_expiration(credits: list, now: str) -> dict:
    """Credits with valid_until <= now are expired and award zero."""
    expired = sorted(c["claim_id"] for c in credits
                     if c.get("valid_until") is not None
                     and str(c["valid_until"]) <= str(now))
    return {"expired_credits": expired, "expired_count": len(expired)}


def drift_findings(*, incremental_check: dict = None,
                   requalification_required: list = None) -> list[Finding]:
    out: list[Finding] = []
    if incremental_check and not incremental_check["equal"]:
        out.append(Finding("EVALUATION_GENOME_MISMATCH", P1, "requalification",
                           "incremental recomputation != full recompute "
                           "(D-0011-102)", incremental_check))
    for cid in (requalification_required or []):
        out.append(Finding("REQUALIFICATION_REQUIRED", P1, cid,
                           "material change invalidated this credit; "
                           "requalification required", {}))
    return out


def drift_root(registry: dict, cone: dict) -> str:
    return hash_obj({"kinds": sorted(registry), "cone": cone["affected_domains"]})

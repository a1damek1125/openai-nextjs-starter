"""Compatibility Vector, Algebra and Directional Consumer-Specific Claims
(SP0007 §10.4/10.5, §12, D-0007-01/02/05/07/14).

Compatibility is DIRECTIONAL, CONSUMER-SPECIFIC, MULTIDIMENSIONAL, VERSION-BOUND
and EVIDENCE-BOUND. A bare `compatible = true` is constitutionally invalid. The
hard gate is the AND over all hard dimensions; a hard failure can never be
averaged away (INV-0007-07); UNKNOWN is never COMPATIBLE (INV-0007-08);
compatibility is never assumed transitive (D-0007-14, §12.10).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, COMPAT_DIMENSIONS, HARD_DIMENSIONS,
                    COMPAT_STATES, DIRECTIONS, CONSUMER_INCOMPATIBLE,
                    COMPATIBILITY_EVIDENCE_STALE, TRANSITIVITY_ASSUMED,
                    INVALID_COMPAT_SCHEMA)
from .canon import core_hash, environment_hash


def new_vector() -> dict:
    """All dimensions start UNKNOWN — never COMPATIBLE by default."""
    return {d: "UNKNOWN" for d in COMPAT_DIMENSIONS}


def validate_vector(vec: dict) -> list[Finding]:
    out: list[Finding] = []
    for d in COMPAT_DIMENSIONS:
        v = (vec or {}).get(d, "UNKNOWN")
        if v not in COMPAT_STATES:
            out.append(Finding(INVALID_COMPAT_SCHEMA, P1, d,
                               f"unknown compatibility state {v!r}", {}))
    for d in vec or {}:
        if d not in COMPAT_DIMENSIONS:
            out.append(Finding(INVALID_COMPAT_SCHEMA, P1, d,
                               f"unrecognized compatibility dimension {d!r}", {}))
    return out


def hard_gate(vec: dict) -> str:
    """AND over hard dimensions (§12.5). Fail-closed: INCOMPATIBLE dominates;
    UNKNOWN / REVIEW_REQUIRED on a hard dimension keeps the gate from passing —
    it can NEVER reach COMPATIBLE via averaging (INV-0007-07/08)."""
    vec = vec or {}
    states = [vec.get(d, "UNKNOWN") for d in COMPAT_DIMENSIONS
              if d in HARD_DIMENSIONS]
    # require POSITIVE proof: the gate passes only when every hard dimension is
    # explicitly COMPATIBLE. INCOMPATIBLE dominates; UNKNOWN blocks; anything
    # else on a hard dim (REVIEW_REQUIRED, NOT_APPLICABLE, or an unrecognized
    # state) needs justification and can NEVER silently pass (SWARM-M E1;
    # INV-0007-07/08).
    if any(s == "INCOMPATIBLE" for s in states):
        return "INCOMPATIBLE"
    if any(s == "UNKNOWN" for s in states):
        return "UNKNOWN"
    if all(s == "COMPATIBLE" for s in states):
        return "COMPATIBLE"
    return "REVIEW_REQUIRED"


def overall(vec: dict) -> str:
    """Whole-vector verdict: the hard gate, degraded by any soft INCOMPATIBLE
    dimension. Never better than the hard gate."""
    hg = hard_gate(vec)
    if hg != "COMPATIBLE":
        return hg
    soft = [(vec or {}).get(d, "UNKNOWN") for d in COMPAT_DIMENSIONS
            if d not in HARD_DIMENSIONS]
    if any(s == "INCOMPATIBLE" for s in soft):
        return "INCOMPATIBLE"
    if any(s in ("UNKNOWN", "REVIEW_REQUIRED") for s in soft):
        return "PARTIALLY_VERIFIED"
    return "COMPATIBLE"


# --- directional consumer-specific claims (D-0007-01/05/07) ------------------
CLAIM_REQUIRED = ("claim_id", "contract_id", "producer_version", "consumer_id",
                  "consumer_version", "direction", "scenario_scope",
                  "evidence_refs", "validator_version", "tested_at")


def build_claim(**kw) -> dict:
    """Build a claim binding producer/consumer/direction/scope/evidence/
    validator/date/environment (D-0007-01/07)."""
    claim = dict(kw)
    claim.setdefault("compatibility_vector", new_vector())
    claim["hard_gate_result"] = hard_gate(claim["compatibility_vector"])
    claim["environment_hash"] = environment_hash(claim.pop("environment", None))
    claim.setdefault("expires_at", None)
    claim["status"] = _claim_status(claim)
    claim["claim_hash"] = core_hash(
        {k: claim.get(k) for k in CLAIM_REQUIRED + ("compatibility_vector",
                                                    "environment_hash")})
    return claim


def _claim_status(claim: dict) -> str:
    verdict = overall(claim.get("compatibility_vector") or {})
    return {"COMPATIBLE": "VERIFIED", "INCOMPATIBLE": "INCOMPATIBLE",
            "PARTIALLY_VERIFIED": "PARTIALLY_VERIFIED"}.get(verdict, "PROPOSED")


def validate_claim(claim: dict) -> list[Finding]:
    """A claim without direction/consumer/scope/evidence/date/validator is
    invalid — `compatible = true` alone is unconstitutional (D-0007-01)."""
    out: list[Finding] = []
    cid = claim.get("claim_id", "-")
    for f in CLAIM_REQUIRED:
        v = claim.get(f)
        if v in (None, "", []):
            out.append(Finding(INVALID_COMPAT_SCHEMA, P1, cid,
                               f"compatibility claim missing {f} "
                               "(D-0007-01)", {}))
    if claim.get("direction") not in DIRECTIONS:
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, cid,
                           f"unknown direction {claim.get('direction')!r}", {}))
    out.extend(validate_vector(claim.get("compatibility_vector") or {}))
    # a VERIFIED status must be justified by the vector (no self-asserted pass)
    if claim.get("status") == "VERIFIED" \
            and overall(claim.get("compatibility_vector") or {}) != "COMPATIBLE":
        out.append(Finding(CONSUMER_INCOMPATIBLE, P0, cid,
                           "claim asserts VERIFIED but its vector does not "
                           "prove COMPATIBLE (INV-0007-08)", {}))
    return out


def freshness(claim: dict, *, current_env: dict | None = None,
              producer_version: str | None = None,
              consumer_version: str | None = None,
              validator_version: str | None = None) -> str:
    """A claim is STALE when any bound identity materially changed (D-0007-07/64)
    — stale evidence cannot prove current compatibility (INV-0007-45)."""
    if producer_version and claim.get("producer_version") != producer_version:
        return "STALE"
    if consumer_version and claim.get("consumer_version") != consumer_version:
        return "STALE"
    if validator_version and claim.get("validator_version") != validator_version:
        return "STALE"
    if current_env is not None and \
            claim.get("environment_hash") != environment_hash(current_env):
        return "STALE"
    return "CURRENT"


def staleness_findings(claim: dict, **kw) -> list[Finding]:
    if freshness(claim, **kw) == "STALE":
        return [Finding(COMPATIBILITY_EVIDENCE_STALE, P1,
                        claim.get("claim_id", "-"),
                        "compatibility evidence is stale — bound identity "
                        "changed (D-0007-64, INV-0007-45)", {})]
    return []


def transitive_inference_findings(claims: list[dict],
                                  inferred: dict) -> list[Finding]:
    """Compat(v1,v2) AND Compat(v2,v3) never imply Compat(v1,v3) without direct
    evidence (D-0007-14, §12.10). An inferred claim whose evidence_refs point
    only at other claims (no direct fixtures) is rejected."""
    ev = inferred.get("evidence_refs") or []
    claim_ids = {c.get("claim_id") for c in claims}
    if ev and all(e in claim_ids for e in ev):
        return [Finding(TRANSITIVITY_ASSUMED, P0,
                        inferred.get("claim_id", "-"),
                        "compatibility inferred transitively from other claims "
                        "without direct evidence (D-0007-14)", {})]
    return []

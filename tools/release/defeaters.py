"""Release defeaters and requalification (SP0009 FUNCTION R, §10.16, §11.22,
§12.14, D-0009-63, AC-0009-231..234).

Qualification is NOT permanent: it holds only while its evidence and
assumptions remain valid. A defeater — new vulnerability, revoked trust root,
stale attestation, discovered incompatibility, provider drift, hidden test
failure, invalid VEX, false SBOM completeness, broken rollback, new safety
hazard — invalidates a specific claim; when validated and blocking it moves a
QUALIFIED candidate to SUSPENDED_BY_DEFEATER and then REQUALIFICATION_REQUIRED.
The prior qualified state remains fully visible history (nothing is rewritten).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, DEFEATER_STATES

DEFEATER_TYPES = (
    "NEW_VULNERABILITY", "TRUST_ROOT_REVOKED", "STALE_ATTESTATION",
    "NEW_INCOMPATIBILITY", "PROVIDER_DRIFT", "HIDDEN_TEST_FAILURE",
    "INVALID_VEX", "FALSE_SBOM_COMPLETENESS", "BROKEN_ROLLBACK",
    "NEW_SAFETY_HAZARD",
)


def defeater(*, candidate_genome: str, defeater_type: str,
             claim_invalidated: str, evidence_refs: list,
             severity: str = "BLOCKING") -> dict:
    if defeater_type not in DEFEATER_TYPES:
        raise ValueError(f"unknown defeater type {defeater_type!r}")
    d = {"candidate_genome": candidate_genome,
         "defeater_type": defeater_type,
         "claim_invalidated": claim_invalidated,
         "evidence_refs": list(evidence_refs),
         "severity": severity,
         "status": "OPEN"}
    d["defeater_id"] = "DF-" + hash_obj(d)[:20]
    return d


def validate_defeater(d: dict) -> dict:
    """A defeater with evidence becomes VALIDATED; a blocking validated
    defeater becomes BLOCKING. Evidence-free defeaters stay OPEN (a rumor is
    not a defeater), they never block by themselves."""
    after = dict(d)
    if d.get("evidence_refs"):
        after["status"] = "BLOCKING" if d.get("severity") == "BLOCKING" \
            else "VALIDATED"
    assert after["status"] in DEFEATER_STATES
    return after


def apply_to_candidate(candidate: dict, defeaters: list) -> tuple:
    """Apply validated blocking defeaters: QUALIFIED (or later) candidates are
    SUSPENDED_BY_DEFEATER; history preserves the prior qualified state
    (AC-0009-234). Returns (candidate_after, findings)."""
    blocking = [d for d in defeaters
                if d.get("status") == "BLOCKING"
                and d.get("candidate_genome") ==
                candidate.get("candidate_genome")]
    findings: list[Finding] = []
    if not blocking:
        return candidate, findings
    after = dict(candidate)
    prior = candidate.get("status")
    if prior in ("QUALIFIED", "ARTIFACT_CLOSURE_SEALED",
                 "READY_FOR_LATER_PROMOTION"):
        after["status"] = "SUSPENDED_BY_DEFEATER"
        after["history"] = list(candidate.get("history") or []) + [
            {"event": "RELEASE_DEFEATER_OPENED",
             "prior_status": prior,
             "defeaters": [d["defeater_id"] for d in blocking]}]
    for d in blocking:
        findings.append(Finding(
            "DEFEATER_BLOCKING", P0, d["defeater_id"],
            f"validated blocking defeater ({d['defeater_type']}) invalidates "
            f"claim {d['claim_invalidated']!r}: qualification suspended "
            "(D-0009-63)", {"prior_status": prior}))
    return after, findings


def require_requalification(candidate: dict) -> dict:
    """SUSPENDED_BY_DEFEATER -> REQUALIFICATION_REQUIRED (§13.1)."""
    if candidate.get("status") != "SUSPENDED_BY_DEFEATER":
        raise ValueError("only a suspended candidate can require "
                         "requalification")
    after = dict(candidate)
    after["status"] = "REQUALIFICATION_REQUIRED"
    after["history"] = list(candidate.get("history") or []) + [
        {"event": "RELEASE_REQUALIFICATION_REQUIRED"}]
    return after


def historical_qualified_visible(candidate: dict) -> bool:
    """The prior QUALIFIED state must remain visible in history after
    suspension (AC-0009-234)."""
    return any(h.get("prior_status") in ("QUALIFIED",
                                         "ARTIFACT_CLOSURE_SEALED",
                                         "READY_FOR_LATER_PROMOTION")
               for h in candidate.get("history") or []
               if h.get("event") == "RELEASE_DEFEATER_OPENED")

"""Progressive delivery contracts with anytime-valid evidence (SP0009 FUNCTION
M/N, §10.15, §11.21, §12.13, D-0009-52..57, AC-0009-217..223).

SP0009 DEFINES delivery contracts; it never executes one (no live rollout,
AC-0009-223). A contract binds the exact artifact digest and configuration hash
(artifact identity vs routing identity stay separate, D-0009-52), explicit
cohorts, metrics, PREDECLARED sequential rules (no threshold may change after
observing data, D-0009-53), a sample-ratio-mismatch policy that blocks ordinary
interpretation (D-0009-56), an interference policy (D-0009-57), and hard-abort
rules that trigger IMMEDIATELY on tenant/authority/safety/proof events without
waiting for statistics (D-0009-55).

The anytime-valid engine is a deterministic e-process for a Bernoulli null: a
nonnegative supermartingale E_t with E_0 = 1; the sequential rule rejects when
E_t >= 1/alpha, valid under optional stopping (§12.13). CANARY PASSED AT ONE
CHECKPOINT != ANYTIME-VALID EVIDENCE.
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, P1

STAGES = ("SHADOW", "INTERNAL", "LIMITED_CANARY", "EXPANDED_CANARY",
          "DECLARED_SCOPE")
HARD_ABORT_EVENTS = ("TENANT_VIOLATION", "AUTHORITY_VIOLATION",
                     "SAFETY_VIOLATION", "PROOF_INTEGRITY_VIOLATION")


def contract(*, candidate_genome: str, artifact_digest: str,
             configuration_hash: str, stages: list, cohorts: list,
             metrics: list, hard_abort_rules: list, sequential_policy: dict,
             sample_ratio_policy: dict, interference_policy: dict,
             rollback_ref: str, owner: str) -> dict:
    c = {
        "candidate_genome": candidate_genome,
        "artifact_digest": artifact_digest,
        "configuration_hash": configuration_hash,
        "stages": list(stages),
        "cohorts": list(cohorts),
        "metrics": list(metrics),
        "hard_abort_rules": list(hard_abort_rules),
        "sequential_policy": dict(sequential_policy),
        "sample_ratio_policy": dict(sample_ratio_policy),
        "interference_policy": dict(interference_policy),
        "rollback_ref": rollback_ref,
        "owner": owner,
        "status": "DRAFT",
        "executes_rollout": False,       # SP0009 never rolls out
    }
    c["progressive_contract_id"] = "PD-" + hash_obj(c)[:20]
    return c


def validate_contract(c: dict) -> list[Finding]:
    out: list[Finding] = []
    subject = str(c.get("progressive_contract_id") or "-")
    if not c.get("artifact_digest"):
        out.append(Finding("PROGRESSIVE_ABORT_REQUIRED", P1, subject,
                           "contract lacks exact artifact digest", {}))
    for s in c.get("stages") or []:
        if s not in STAGES:
            out.append(Finding("PROGRESSIVE_ABORT_REQUIRED", P1, subject,
                               f"unknown stage {s!r}", {}))
    for cohort in c.get("cohorts") or []:
        if not cohort.get("cohort_id"):
            out.append(Finding(
                "PROGRESSIVE_ABORT_REQUIRED", P1, subject,
                "cohort without explicit identity (AC-0009-218)", {}))
    sp = c.get("sequential_policy") or {}
    # the sequential rule must be PREDECLARED: alpha + rule type fixed up front
    if not sp.get("predeclared") is True or "alpha" not in sp:
        out.append(Finding(
            "SEQUENTIAL_POLICY_NOT_PREDECLARED", P0, subject,
            "sequential policy is not predeclared with a fixed alpha: "
            "thresholds may never be chosen after observing data "
            "(D-0009-53)", {"sequential_policy": sp}))
    if not c.get("hard_abort_rules"):
        out.append(Finding("PROGRESSIVE_ABORT_REQUIRED", P1, subject,
                           "no hard abort rules declared", {}))
    if c.get("executes_rollout") is not False:
        out.append(Finding(
            "PROGRESSIVE_ABORT_REQUIRED", P0, subject,
            "SP0009 contracts must not execute a rollout (AC-0009-223)", {}))
    return out


# --- anytime-valid e-process (§11.21, §12.13) -----------------------------------------
def eprocess_step(e_t: float, outcome: int, *, p0: float, p1: float) -> float:
    """One likelihood-ratio update of the e-process for a Bernoulli stream:
    E_{t+1} = E_t * [p1/p0]^x * [(1-p1)/(1-p0)]^(1-x). Under the null (rate
    p0) this is a nonnegative supermartingale with E_0=1, so
    P(exists t: E_t >= 1/alpha) <= alpha — valid under optional stopping."""
    if outcome not in (0, 1):
        raise ValueError("outcome must be 0 or 1")
    if not (0 < p0 < 1 and 0 < p1 < 1):
        raise ValueError("p0,p1 must be in (0,1)")
    ratio = (p1 / p0) if outcome == 1 else ((1 - p1) / (1 - p0))
    return e_t * ratio


def sequential_verdict(outcomes: list, *, policy: dict) -> dict:
    """Run the predeclared e-process over an outcome stream (1 = bad event).
    Rejects (abort) when E_t crosses 1/alpha. The policy is fixed BEFORE data:
    this function refuses to run an undeclared policy."""
    if policy.get("predeclared") is not True:
        raise ValueError("sequential policy must be predeclared (D-0009-53)")
    alpha = float(policy["alpha"])
    p0, p1 = float(policy["p0"]), float(policy["p1"])
    e_t = 1.0
    crossed_at = None
    trajectory = []
    for i, x in enumerate(outcomes):
        e_t = eprocess_step(e_t, x, p0=p0, p1=p1)
        trajectory.append(round(e_t, 6))
        if e_t >= 1.0 / alpha and crossed_at is None:
            crossed_at = i + 1
    return {"e_final": round(e_t, 6), "threshold": round(1.0 / alpha, 6),
            "crossed_at": crossed_at,
            "verdict": "ABORT" if crossed_at is not None else "CONTINUE",
            "trajectory": trajectory,
            "anytime_valid": True}


def hard_abort(events: list) -> dict:
    """Hard safety events abort IMMEDIATELY, independent of statistics
    (D-0009-55, AC-0009-222)."""
    hits = [e for e in events if e in HARD_ABORT_EVENTS]
    return {"abort": bool(hits), "immediate": True, "events": sorted(hits),
            "note": "hard abort does not wait for statistical accumulation"}


# --- sample-ratio mismatch (D-0009-56) -------------------------------------------------
def sample_ratio_check(*, expected_ratio: float, treatment_n: int,
                       control_n: int, tolerance: float = 0.05) -> dict:
    """A cheap deterministic SRM check: |observed - expected| ratio deviation
    beyond tolerance blocks ordinary interpretation. (A z-test refinement can
    replace this; the CONTRACT is that mismatch blocks, D-0009-56.)"""
    total = treatment_n + control_n
    if total == 0:
        return {"srm": True, "reason": "no samples", "blocks": True}
    observed = treatment_n / total
    deviation = abs(observed - expected_ratio)
    srm = deviation > tolerance
    return {"expected": expected_ratio, "observed": round(observed, 6),
            "deviation": round(deviation, 6), "tolerance": tolerance,
            "srm": srm, "blocks": srm}


def srm_findings(check: dict, subject: str) -> list[Finding]:
    out: list[Finding] = []
    if check.get("blocks"):
        out.append(Finding(
            "CANARY_SAMPLE_RATIO_MISMATCH", P0, subject,
            "sample-ratio mismatch: cohort allocation deviates from the "
            "predeclared ratio; ordinary comparison is invalidated "
            "(D-0009-56)", check))
    return out


def interference_findings(*, shared_state_domains: list,
                          subject: str) -> list[Finding]:
    """Cross-cohort shared state blocks naive causal inference (D-0009-57)."""
    out: list[Finding] = []
    if shared_state_domains:
        out.append(Finding(
            "CANARY_INTERFERENCE_DETECTED", P1, subject,
            f"treatment and control share state domains "
            f"{sorted(shared_state_domains)}: interference blocks naive "
            "causal comparison (D-0009-57)",
            {"domains": sorted(shared_state_domains)}))
    return out

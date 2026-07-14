"""Score computation, Qualification Envelope and maturity classification (SP0011
§2.2, §2.4, §11.25, §12.1, D-0011-021..024, AC-0011-045, 055..058).

Score = Σ 5·q_i over the 200 claims, 0 ≤ Score ≤ 1000, where q_i = 1 only when
the claim's credit certificate is AWARDED by the independent kernel AND the hard
gates pass (§12.2/12.3). The score is NOT a probability. The official score always
carries maturity, hard-gate state, the Qualification Envelope (a vector, never a
hidden weighted average), and an expiration. A placeholder 1000 is impossible:
the score is computed from awarded certificates only.
"""
from __future__ import annotations

from .canon import hash_obj
from .model import (Finding, P0, MAX_CREDITS, CREDIT_PER_CLAIM, MATURITY_NAMES)


def compute_score(*, claims: dict, awards: dict, hard_gate_result: dict,
                  configuration_id: str, program_seal: str, evaluation_seal,
                  sealed_at: str, valid_until, envelope_ref: str,
                  achieved_maturity: str, open_blockers: list,
                  open_production_gaps: list) -> dict:
    """awards: claim_id -> {awarded: bool, credits: int}. If the hard gates fail,
    the OFFICIAL score is blocked (non-compensatory): domain scores are still
    reported but total_credits carries the block."""
    domain_scores = {}
    total = 0
    for cid, claim in sorted(claims.items()):
        aw = awards.get(cid, {"awarded": False, "credits": 0})
        credits = CREDIT_PER_CLAIM if aw.get("awarded") else 0
        total += credits
        d = claim["domain_id"]
        domain_scores.setdefault(d, {"credits": 0, "max": 0,
                                     "qualified_claims": 0})
        domain_scores[d]["credits"] += credits
        domain_scores[d]["max"] += CREDIT_PER_CLAIM
        if aw.get("awarded"):
            domain_scores[d]["qualified_claims"] += 1
    gate_ok = hard_gate_result["overall_pass"]
    scorecard = {
        "scorecard_id": "SCORECARD-" + configuration_id,
        "configuration_id": configuration_id,
        "program_seal": program_seal,
        "evaluation_seal": evaluation_seal,
        "domain_scores": domain_scores,
        "total_credits": total if gate_ok else 0,
        "diagnostic_total_credits": total,     # pre-gate diagnostic value
        "maximum_credits": MAX_CREDITS,
        "maturity": achieved_maturity,
        "maturity_name": MATURITY_NAMES.get(achieved_maturity, achieved_maturity),
        "hard_gate_state": hard_gate_result["overall"],
        "official_score_blocked_by_gate": not gate_ok,
        "qualification_envelope_ref": envelope_ref,
        "open_blockers": sorted(open_blockers),
        "open_production_gaps": sorted(open_production_gaps),
        "valid_from": sealed_at, "valid_until": valid_until,
    }
    scorecard["scorecard_hash"] = hash_obj(
        {k: scorecard[k] for k in scorecard if k != "scorecard_hash"})
    return scorecard


def build_envelope(*, configuration_id: str, scorecard_id: str,
                   achieved_maturity: str, hard_gate_state: str,
                   nominal_bounds: dict, worst_stratum_bounds: dict,
                   robust_mixture_bounds: dict, tail_risk: dict,
                   rare_failure_bounds: dict, contamination_state: str,
                   judge_reliability_state: str, evidence_robustness: dict,
                   validity_scope: dict, valid_until, open_gaps: list) -> dict:
    """The Qualification Envelope is a VECTOR (D-0011-023) — never collapsed into
    one hidden weighted average."""
    env = {
        "envelope_id": "ENV-" + configuration_id,
        "configuration_id": configuration_id, "scorecard_id": scorecard_id,
        "maturity": achieved_maturity, "hard_gate_state": hard_gate_state,
        "nominal_bounds": nominal_bounds,
        "worst_stratum_bounds": worst_stratum_bounds,
        "robust_mixture_bounds": robust_mixture_bounds,
        "tail_risk": tail_risk, "rare_failure_bounds": rare_failure_bounds,
        "contamination_state": contamination_state,
        "judge_reliability_state": judge_reliability_state,
        "evidence_robustness": evidence_robustness,
        "validity_scope": validity_scope, "valid_until": valid_until,
        "open_gaps": sorted(open_gaps),
    }
    env["envelope_hash"] = hash_obj(
        {k: env[k] for k in env if k != "envelope_hash"})
    return env


def verify_score_arithmetic(scorecard: dict, awards: dict) -> list[Finding]:
    """Independent re-addition (score arithmetic checker): the diagnostic total
    must equal Σ awarded·5, must not exceed 1000, and the official total must be
    zero when the hard gate blocks (D-0011-022, AC-0011-045)."""
    out: list[Finding] = []
    recomputed = sum(CREDIT_PER_CLAIM for a in awards.values()
                     if a.get("awarded"))
    if scorecard["diagnostic_total_credits"] != recomputed:
        out.append(Finding("SCORE_ARITHMETIC_INVALID", P0, "scorecard",
                           "diagnostic credit sum does not match awards", {}))
    if scorecard["diagnostic_total_credits"] > MAX_CREDITS:
        out.append(Finding("SCORE_ARITHMETIC_INVALID", P0, "scorecard",
                           "score exceeds 1000", {}))
    if scorecard["official_score_blocked_by_gate"] and \
            scorecard["total_credits"] != 0:
        out.append(Finding("SCORE_ARITHMETIC_INVALID", P0, "scorecard",
                           "hard gate blocks but official score is non-zero", {}))
    # score must carry maturity, hard-gate state, envelope, expiration
    for req in ("maturity", "hard_gate_state", "qualification_envelope_ref"):
        if not scorecard.get(req):
            out.append(Finding("SCORECARD_INVALID", P0, "scorecard",
                               f"score missing required field {req}", {}))
    return out


def maturity_classification(claims: dict, awards: dict) -> str:
    """The scorecard's maturity is the MINIMUM achieved maturity across AWARDED
    claims — an awarded set is only as mature as its weakest evidence. With no
    awarded claim, the system is DEFINITION_ONLY (M0). Repository-evidenced awards
    give M1. Field/production maturity is never claimed without such evidence."""
    achieved = [claims[cid]["achieved_maturity"] for cid, a in awards.items()
                if a.get("awarded") and cid in claims]
    if not achieved:
        return "M0"
    rank = {"M0": 0, "M1": 1, "M2": 2, "M3": 3, "M4": 4, "M5": 5}
    return min(achieved, key=lambda m: rank.get(m, 0))

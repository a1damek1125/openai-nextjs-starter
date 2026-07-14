"""Sensitivity, scenario & minimax-regret analysis (SP0004 D-0004-09/10/11,
§11.4/§11.5, AC-0004-032/033/034/035).

Sensitivity analysis perturbs weights/assumptions within declared plausible ranges
and classifies a weighted decision ROBUST / SENSITIVE / UNSTABLE. Minimax regret
is computed ONLY where utility definitions are meaningful and the scenario set is
explicit; otherwise REGRET_ANALYSIS_NOT_CALIBRATED — no fabricated numbers.
"""
from __future__ import annotations

import itertools

from .model import Finding, P2, DECISION_SENSITIVE, REGRET_NOT_CALIBRATED
from .pareto import normalized_utility


def _winner(candidates, criteria, weights):
    best, best_u = None, float("-inf")
    for c in candidates:
        u = normalized_utility(c, criteria, weights)["utility"]
        if u > best_u:
            best_u, best = u, c.get("candidate_id")
    return best


def sensitivity(decision: dict, *, perturbation: float = 0.2,
                steps: int = 2) -> dict:
    """Vary each criterion weight by +/- perturbation and see if the winner
    changes. ROBUST = winner never changes; SENSITIVE = changes under some
    plausible perturbation; UNSTABLE = changes under most."""
    criteria = decision.get("criteria", [])
    cands = decision.get("candidates", [])
    base_weights = {cr["key"]: cr.get("weight", 0.0) for cr in criteria}
    if not criteria or len(cands) < 2:
        return {"classification": "NOT_APPLICABLE", "base_winner": None,
                "flips": 0, "trials": 0}
    base_winner = _winner(cands, criteria, base_weights)
    deltas = [1 - perturbation, 1 + perturbation]
    keys = [cr["key"] for cr in criteria]
    flips, trials = 0, 0
    for combo in itertools.product(deltas, repeat=len(keys)):
        w = {k: base_weights[k] * m for k, m in zip(keys, combo)}
        trials += 1
        if _winner(cands, criteria, w) != base_winner:
            flips += 1
    ratio = flips / trials if trials else 0.0
    cls = "ROBUST" if flips == 0 else ("UNSTABLE" if ratio > 0.5 else "SENSITIVE")
    return {"classification": cls, "base_winner": base_winner,
            "flips": flips, "trials": trials, "flip_ratio": round(ratio, 4)}


def sensitivity_findings(decision: dict) -> list[Finding]:
    r = sensitivity(decision)
    if r["classification"] in ("SENSITIVE", "UNSTABLE"):
        return [Finding(DECISION_SENSITIVE, P2, decision.get("decision_id", "-"),
                        f"weighted decision is {r['classification']} "
                        f"(flip ratio {r.get('flip_ratio')})", r)]
    return []


def minimax_regret(decision: dict) -> dict:
    """R(c,s)=U*(s)-U(c,s); MR(c)=max_s R(c,s). Calibrated only when scenarios
    carry per-candidate utility. Else REGRET_ANALYSIS_NOT_CALIBRATED."""
    scenarios = decision.get("scenarios", [])
    cands = [c.get("candidate_id") for c in decision.get("candidates", [])]
    # scenario must provide a utility per candidate to be calibrated
    calibrated = scenarios and all(
        isinstance(s.get("candidate_utility"), dict)
        and all(cid in s["candidate_utility"] for cid in cands)
        for s in scenarios)
    if not calibrated:
        return {"status": REGRET_NOT_CALIBRATED,
                "message": "scenario set lacks explicit per-candidate utilities"}
    regret = {cid: 0.0 for cid in cands}
    for s in scenarios:
        u = s["candidate_utility"]
        best = max(u.values())
        for cid in cands:
            regret[cid] = max(regret[cid], best - u[cid])
    minimax = min(regret, key=lambda c: regret[c])
    return {"status": "CALIBRATED", "max_regret": {k: round(v, 6)
            for k, v in regret.items()},
            "minimax_regret_choice": minimax}

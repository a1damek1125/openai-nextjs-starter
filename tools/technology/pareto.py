"""Pareto Frontier + weighted-utility normalization (SP0004 D-0004-07/08,
§11.3/§11.4, AC-0004-029/030/031).

Pareto analysis precedes arbitrary weighted scoring: identify DOMINATED vs
NON_DOMINATED candidates before aggregating criteria, so obvious domination is
never hidden behind weights. Weighted utility, where used, requires explicit
per-criterion direction + normalization + weight — no unexplained "94.3/100".
"""
from __future__ import annotations

from .model import Finding, P2, CANDIDATE_DOMINATED


def _better(a_val, b_val, direction: str) -> int:
    """1 if a is better than b, -1 if worse, 0 if equal (by criterion direction).
    'MAX' = higher is better, 'MIN' = lower is better."""
    if a_val == b_val:
        return 0
    if direction == "MIN":
        return 1 if a_val < b_val else -1
    return 1 if a_val > b_val else -1


def dominates(a: dict, b: dict, criteria: list[dict]) -> bool:
    """a dominates b iff a is no worse on every criterion and strictly better on
    at least one (§11.3)."""
    strictly_better = False
    for cr in criteria:
        key, direction = cr["key"], cr.get("direction", "MAX")
        av, bv = a.get("scores", {}).get(key), b.get("scores", {}).get(key)
        if av is None or bv is None:
            return False   # cannot claim domination with missing data
        cmp = _better(av, bv, direction)
        if cmp < 0:
            return False
        if cmp > 0:
            strictly_better = True
    return strictly_better


def pareto_frontier(candidates: list[dict], criteria: list[dict]) -> dict:
    """Return non-dominated set + dominated set (with dominator)."""
    non_dominated, dominated = [], []
    for c in candidates:
        cid = c.get("candidate_id")
        dominator = None
        for other in candidates:
            if other is c:
                continue
            if dominates(other, c, criteria):
                dominator = other.get("candidate_id")
                break
        if dominator:
            dominated.append({"candidate_id": cid, "dominated_by": dominator})
        else:
            non_dominated.append(cid)
    return {"non_dominated": sorted(non_dominated),
            "dominated": sorted(dominated, key=lambda d: d["candidate_id"])}


def dominated_findings(decision: dict) -> list[Finding]:
    """Advisory: flag a selected candidate that is Pareto-dominated."""
    out: list[Finding] = []
    criteria = decision.get("criteria", [])
    cands = decision.get("candidates", [])
    if not criteria or not cands:
        return out
    pf = pareto_frontier(cands, criteria)
    sel = decision.get("selected_candidate")
    for d in pf["dominated"]:
        if d["candidate_id"] == sel:
            out.append(Finding(CANDIDATE_DOMINATED, P2,
                               decision.get("decision_id", "-"),
                               f"selected candidate {sel!r} is Pareto-dominated "
                               f"by {d['dominated_by']!r}", d))
    return out


def normalized_utility(candidate: dict, criteria: list[dict],
                       weights: dict) -> dict:
    """U(c) = sum w_i * n_i(c) with explicit min-max normalization per criterion.
    Requires every criterion to declare direction; returns the breakdown so the
    number is never unexplained (D-0004-08)."""
    total = 0.0
    breakdown = {}
    for cr in criteria:
        key = cr["key"]
        direction = cr.get("direction", "MAX")
        lo = cr.get("min")
        hi = cr.get("max")
        w = weights.get(key, cr.get("weight", 0.0))
        v = candidate.get("scores", {}).get(key)
        if v is None or lo is None or hi is None or hi == lo:
            n = 0.0
        else:
            n = (v - lo) / (hi - lo)
            if direction == "MIN":
                n = 1.0 - n
        contrib = round(w * n, 6)
        breakdown[key] = {"raw": v, "normalized": round(n, 6), "weight": w,
                          "contribution": contrib}
        total += contrib
    return {"utility": round(total, 6), "breakdown": breakdown}

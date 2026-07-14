"""Distributionally robust qualification (SP0011 §2.1.J, §11.15/11.16, §12.7/12.8/
12.9, D-0011-062..066, AC-0011-141..160).

Nominal reliability != robust reliability (D-0011-064). Average success must not
hide a weak critical stratum (D-0011-063). This module computes the worst-stratum
lower bound (§12.7), the robust lower bound over a declared plausible deployment-
mixture set (§12.8), tail risk via CVaR (§12.9, NOT a probability), and the zero-
observed-failure upper bound (rare failures). All bounds are separate; nominal and
robust results are never merged.
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0
from .statistics import clopper_pearson_lower, zero_failure_upper_bound


def worst_stratum(stratum_stats: dict, thresholds: dict, alpha: float = 0.05):
    """stratum_stats: stratum -> (successes, n). Returns per-stratum lower bounds
    and the worst (minimum). Qualification requires min >= threshold (§12.7)."""
    bounds = {s: clopper_pearson_lower(k, n, alpha)
              for s, (k, n) in sorted(stratum_stats.items())}
    worst = min(bounds.values()) if bounds else 0.0
    worst_stratum_id = min(bounds, key=bounds.get) if bounds else None
    passed = all(bounds[s] >= thresholds.get(s, 0.0) for s in bounds)
    return {"stratum_lower_bounds": bounds, "worst_stratum": worst_stratum_id,
            "worst_lower_bound": worst, "thresholds": thresholds,
            "passes": passed}


def robust_mixture_lower_bound(stratum_lower_bounds: dict,
                               mixtures: list) -> dict:
    """R_robust = min over declared mixtures of Σ w_s · LowerBound(p_s) (§12.8).
    The plausible mixture set must be explicitly declared."""
    if not mixtures:
        return {"robust_lower_bound": None, "note": "no declared mixture set"}
    vals = []
    for w in mixtures:
        vals.append(sum(w.get(s, 0.0) * lb
                        for s, lb in stratum_lower_bounds.items()))
    return {"robust_lower_bound": min(vals) if vals else None,
            "mixture_count": len(mixtures), "worst_mixture_value": min(vals)}


def cvar(losses: list, beta: float = 0.95) -> dict:
    """CVaR_beta via the Rockafellar-Uryasev minimization over a grid of eta.
    CVaR is a loss, NOT a probability (D-0011-066)."""
    if not losses:
        return {"cvar": None, "beta": beta}
    xs = sorted(losses)
    best = None
    for eta in xs:
        val = eta + (1 / (1 - beta)) * (
            sum(max(0.0, x - eta) for x in xs) / len(xs))
        best = val if best is None else min(best, val)
    return {"cvar": best, "beta": beta, "is_probability": False,
            "loss_definition": "1 - outcome_success"}


def robust_qualification(*, stratum_stats: dict, thresholds: dict,
                         mixtures: list, losses: list,
                         zero_failure_n: int | None = None) -> dict:
    ws = worst_stratum(stratum_stats, thresholds)
    rm = robust_mixture_lower_bound(ws["stratum_lower_bounds"], mixtures)
    tr = cvar(losses)
    rare = (zero_failure_upper_bound(zero_failure_n)
            if zero_failure_n is not None else None)
    result = {"worst_stratum": ws, "robust_mixture": rm, "tail_risk": tr,
              "rare_failure": rare,
              "nominal_and_robust_separate": True}
    result["robust_root"] = hash_obj({"ws": ws["worst_lower_bound"],
                                      "rm": rm.get("robust_lower_bound"),
                                      "cvar": tr.get("cvar")})
    return result


def robust_findings(result: dict, *, observed_catastrophic: bool = False,
                    hidden_weak_stratum: bool = False) -> list[Finding]:
    out: list[Finding] = []
    if observed_catastrophic:
        out.append(Finding("OBSERVED_CATASTROPHIC_FAILURE", P0, "tail",
                           "observed catastrophic failure blocks regardless of "
                           "the average (D-0011-059)", {}))
    if hidden_weak_stratum:
        out.append(Finding("HIDDEN_WEAK_STRATUM", P0, "stratum",
                           "a weak critical stratum was hidden by pooled average "
                           "(D-0011-063)", {}))
    return out

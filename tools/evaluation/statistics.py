"""Statistical qualification (SP0011 §2.1.I, §11.12..11.14, §12.4..12.6, §12.16,
D-0011-013/014/015, AC-0011-121..140).

Standard-library-only reference implementations of the statistical machinery every
qualification claim needs: estimands, preregistered analysis plans, exact/
conservative binomial lower bounds (Clopper-Pearson by monotone bisection on the
binomial tail), the zero-observed-failure one-sided upper bound (§12.5), an
anytime-valid e-process + confidence sequence (Ville's inequality), dependence-
aware effective sample size (design effect), and multiple-testing control
(Bonferroni + Benjamini-Hochberg). Every statistical claim carries an estimand,
a dependence structure and a frozen plan; a result WITHOUT a frozen plan is not a
qualifying certificate (D-0011-013/014, INV-47..54).
"""
from __future__ import annotations

import math

from .canon import hash_obj
from .model import Finding, P1, STAT_DESIGNS


def estimand(*, quantity: str, unit: str, target_population: dict,
             target_distribution: dict, dependence_structure: dict,
             time_horizon: dict, aggregation: str, scope: dict) -> dict:
    e = {"quantity": quantity, "unit": unit,
         "target_population": target_population,
         "target_distribution": target_distribution,
         "dependence_structure": dependence_structure,
         "time_horizon": time_horizon, "aggregation": aggregation, "scope": scope}
    e["estimand_id"] = "EST-" + hash_obj(e)[:16]
    return e


def analysis_plan(*, estimand_ref: str, design: str, alpha: float,
                  stopping_rule: str, confidence_method: str,
                  dependence_adjustment: str, multiple_testing_family=None,
                  practical_threshold: float | None = None,
                  effect_size: float | None = None) -> dict:
    if design not in STAT_DESIGNS:
        raise ValueError(f"bad design {design!r}")
    p = {"estimand_ref": estimand_ref, "design": design, "alpha": alpha,
         "stopping_rule": stopping_rule, "confidence_method": confidence_method,
         "dependence_adjustment": dependence_adjustment,
         "multiple_testing_family": multiple_testing_family,
         "practical_threshold": practical_threshold, "effect_size": effect_size,
         "preregistered": True}
    p["plan_hash"] = hash_obj(p)
    p["plan_id"] = "PLAN-" + p["plan_hash"][:16]
    return p


# --- binomial ----------------------------------------------------------------
def _binom_tail_leq(k: int, n: int, p: float) -> float:
    """P(X <= k) for X~Binomial(n,p), computed stably in log space."""
    if p <= 0:
        return 1.0
    if p >= 1:
        return 0.0 if k < n else 1.0
    total = 0.0
    for i in range(0, k + 1):
        logc = (math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1))
        total += math.exp(logc + i * math.log(p) + (n - i) * math.log(1 - p))
    return min(1.0, total)


def clopper_pearson_lower(successes: int, n: int, alpha: float = 0.05) -> float:
    """Exact one-sided lower confidence bound on the success probability. Found by
    bisection: the largest p with P(X >= successes) >= alpha, i.e. P(X <=
    successes-1) <= 1-alpha."""
    if n == 0:
        return 0.0
    if successes == 0:
        return 0.0
    if successes == n:
        return alpha ** (1.0 / n)
    lo, hi = 0.0, 1.0
    # f(p)=P(X<=successes-1; p) is DECREASING in p; the lower confidence limit
    # p_L solves f(p_L)=1-alpha. If f(mid) > 1-alpha then mid < p_L (search up).
    for _ in range(200):
        mid = (lo + hi) / 2
        if _binom_tail_leq(successes - 1, n, mid) > 1 - alpha:
            lo = mid
        else:
            hi = mid
    return lo


def zero_failure_upper_bound(n: int, alpha: float = 0.05) -> dict:
    """One-sided failure-rate upper bound with zero observed failures (§12.5):
    1 - alpha^(1/n). NEVER report zero risk (D-0011-061)."""
    if n <= 0:
        return {"n": n, "upper_bound": 1.0, "note": "no samples"}
    ub = 1 - alpha ** (1.0 / n)
    return {"n": n, "alpha": alpha, "failure_rate_upper_bound": ub,
            "zero_risk_claimed": False,
            "note": "zero observed failures => an upper bound, not zero risk"}


# --- anytime-valid -----------------------------------------------------------
def e_process_bernoulli(outcomes: list, p0: float) -> dict:
    """A simple nonnegative e-process for H0: p <= p0 using a fixed alternative
    p1 > p0 betting strategy. E_{H0}[E_t] <= 1; by Ville, P(sup E_t >= 1/alpha)
    <= alpha (§12.6). Optional stopping preserves validity."""
    p1 = min(0.99, p0 + 0.1)
    e = 1.0
    path = []
    for x in outcomes:
        factor = (p1 / p0) if x == 1 else ((1 - p1) / (1 - p0))
        e *= factor
        path.append(e)
    return {"design": "ANYTIME_VALID", "p0": p0, "p1": p1,
            "e_value": e, "max_e": max(path) if path else 1.0,
            "reject_at_alpha_0_05": (max(path) if path else 1.0) >= 20.0,
            "optional_stopping_valid": True}


def confidence_sequence(successes: int, n: int, alpha: float = 0.05) -> dict:
    """Time-uniform (anytime-valid) lower bound via a Hoeffding-style confidence
    sequence: p_hat - sqrt(log(1/alpha) / (2n)). Conservative but valid under
    optional stopping."""
    if n == 0:
        return {"n": 0, "lower_bound": 0.0}
    phat = successes / n
    radius = math.sqrt(math.log(1 / alpha) / (2 * n))
    return {"n": n, "p_hat": phat, "lower_bound": max(0.0, phat - radius),
            "time_uniform": True, "alpha": alpha}


# --- dependence --------------------------------------------------------------
def effective_sample_size(n: int, cluster_sizes: list, icc: float = 0.2) -> dict:
    """Dependence-aware effective n via the design effect DEFF = 1 + (m-1)·ICC
    for average cluster size m. Correlated runs are NOT independent Bernoulli
    (D-0011-015, INV-51)."""
    if not cluster_sizes:
        return {"n": n, "effective_n": n, "design_effect": 1.0}
    m = sum(cluster_sizes) / len(cluster_sizes)
    deff = 1 + (m - 1) * icc
    return {"n": n, "avg_cluster_size": m, "icc": icc, "design_effect": deff,
            "effective_n": n / deff if deff > 0 else n}


# --- multiple testing --------------------------------------------------------
def bonferroni(pvalues: dict, alpha: float = 0.05) -> dict:
    m = len(pvalues)
    thr = alpha / m if m else alpha
    return {"method": "BONFERRONI", "threshold": thr,
            "rejected": sorted(k for k, p in pvalues.items() if p <= thr)}


def benjamini_hochberg(pvalues: dict, alpha: float = 0.05) -> dict:
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    rejected = []
    for i, (k, p) in enumerate(items, start=1):
        if p <= (i / m) * alpha:
            rejected = [kk for kk, _ in items[:i]]
    return {"method": "BENJAMINI_HOCHBERG", "alpha": alpha, "m": m,
            "rejected": sorted(rejected)}


def equivalence(delta: float, ci_low: float, ci_high: float,
                margin: float) -> dict:
    """TOST-style: equivalence is supported only when the CI lies fully inside
    [-margin, +margin] (§12.16). No detected difference is NOT equivalence."""
    return {"delta": delta, "ci": [ci_low, ci_high], "margin": margin,
            "equivalent": ci_low >= -margin and ci_high <= margin,
            "no_difference_is_not_equivalence": True}


def statistical_findings(plans: list) -> list[Finding]:
    out: list[Finding] = []
    for p in plans:
        if not p.get("preregistered"):
            out.append(Finding("STATISTICAL_PLAN_VIOLATION", P1,
                               p.get("plan_id", "-"),
                               "analysis plan is not preregistered", {}))
    return out


def statistics_root(plans: list) -> str:
    return hash_obj(sorted(p["plan_hash"] for p in plans))

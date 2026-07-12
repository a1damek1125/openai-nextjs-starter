"""Long-horizon competing-risk reliability (SP0011 §2.1.K, §11.17/11.18, §12.10/
12.11, D-0011-067..072, AC-0011-161..180).

Reliability depends on task duration (D-0011-067); there is no single universal
horizon (D-0011-068). This module fits a logistic horizon curve P(success | log
duration), reports p50/p80 task horizons with an interpolation/extrapolation
label, and runs a competing-risk analysis (cause-specific hazards + cumulative
incidence, §12.11) over distinct failure causes. Recovery success does not erase
an initial failure (D-0011-070); PARTIAL and UNKNOWN remain distinct from SUCCESS.
"""
from __future__ import annotations

import math

from .canon import hash_obj
from .model import Finding, P1


def horizon_curve(observations: list) -> dict:
    """observations: list of (duration_seconds, success∈{0,1}). Fit a 2-parameter
    logistic P(success)=sigmoid(a + b·log(duration)) by deterministic gradient
    descent, then solve for the p50/p80 horizons."""
    pts = [(math.log(max(1.0, d)), y) for d, y in observations]
    a, b = 0.0, 0.0
    lr = 0.1
    for _ in range(500):
        ga = gb = 0.0
        for x, y in pts:
            p = 1 / (1 + math.exp(-(a + b * x)))
            ga += (p - y)
            gb += (p - y) * x
        a -= lr * ga / max(1, len(pts))
        b -= lr * gb / max(1, len(pts))
    def horizon(r):
        # solve sigmoid(a+b·x)=r  => x = (logit(r)-a)/b
        if abs(b) < 1e-9:
            return None
        x = (math.log(r / (1 - r)) - a) / b
        return math.exp(x)
    durations = [d for d, _ in observations]
    lo, hi = (min(durations), max(durations)) if durations else (0, 0)
    def label(h):
        if h is None:
            return "UNDEFINED"
        return "INTERPOLATION" if lo <= h <= hi else "EXTRAPOLATION"
    h50, h80 = horizon(0.5), horizon(0.8)
    return {"coefficients": {"a": a, "b": b},
            "p50_horizon_seconds": h50, "p50_region": label(h50),
            "p80_horizon_seconds": h80, "p80_region": label(h80),
            "observed_range": [lo, hi], "n": len(observations)}


def competing_risks(events: list, horizon: float) -> dict:
    """events: list of (time, cause) where cause in {..., 'success'}. Cause-
    specific hazard ~ count/exposure; cumulative incidence F_k(t) approximated by
    the fraction of the population reaching cause k by the horizon (§12.11)."""
    n = len(events)
    if n == 0:
        return {"cause_specific_hazards": {}, "cumulative_incidence": {}, "n": 0}
    causes = {}
    for t, c in events:
        if t <= horizon:
            causes[c] = causes.get(c, 0) + 1
    incidence = {c: cnt / n for c, cnt in sorted(causes.items())}
    hazards = {c: cnt / max(1, n) for c, cnt in sorted(causes.items())}
    return {"cause_specific_hazards": hazards,
            "cumulative_incidence": incidence, "n": n, "horizon": horizon,
            "recovery_erases_failure": False}


def long_horizon_result(*, configuration_id: str, observations: list,
                        events: list, horizon: float) -> dict:
    hc = horizon_curve(observations)
    cr = competing_risks(events, horizon)
    r = {"configuration_id": configuration_id, "task_duration_unit": "SECONDS",
         "horizon_curve": hc, "competing_risks": cr}
    r["long_horizon_root"] = hash_obj({"h50": hc["p50_horizon_seconds"],
                                       "h80": hc["p80_horizon_seconds"],
                                       "ci": cr["cumulative_incidence"]})
    return r


def long_horizon_findings(result: dict) -> list[Finding]:
    out: list[Finding] = []
    hc = result["horizon_curve"]
    for reg in ("p50_region", "p80_region"):
        if hc.get(reg) == "EXTRAPOLATION":
            out.append(Finding("LONG_HORIZON_EXTRAPOLATION_LIMIT", P1,
                               result["configuration_id"],
                               f"{reg} is an extrapolation beyond observed "
                               "durations: labeled, not qualified", {}))
    return out

"""Risk Vector + Non-Compensatory Control Floor + optional Expected-Loss/CVaR
(SP0006 §9 risk model, §11.7, §12.4/12.5/12.6, D-0006-27..31, INV-0006-20/21/22).

Risk is a VECTOR over eight ordinal dimensions (operational, financial, privacy,
security, legal, rights, reputation, irreversibility). The required control floor
is a NON-COMPENSATORY join: the maximum control class across all dimensions, so a
low dimension can never average away a critical one (D-0006-28). A hard-prohibited
dimension forces the top control class (CC5). UNKNOWN risk is NOT low: it maps to
CC3, never CC1 (INV-0006-22) — absence of evidence of risk is not evidence of
absence. Quantitative expected-loss / CVaR figures are ADVISORY only and are
computed ONLY when every scenario is calibrated (probabilities in [0,1] summing to
~1 and numeric losses); ordinal labels are never multiplied as if numeric
(D-0006-30). No scalar may ever override the hard control floor (§11.7, §12.4).

Governance tooling only; product runtime must never import it (INV-0006-46).
"""
from __future__ import annotations

from .model import (Finding, P2, RISK_DIMENSIONS, RISK_LEVELS, CONTROL_CLASSES,
                    QUANTITATIVE_RISK_NOT_CALIBRATED)

# Ordinal risk level -> required control class. UNKNOWN maps to CC3 (fail-closed),
# never CC1: unknown risk is NOT low risk (INV-0006-22).
RISK_TO_CC = {"NONE": "CC0", "LOW": "CC1", "MEDIUM": "CC2", "HIGH": "CC3",
              "CRITICAL": "CC4", "UNKNOWN": "CC3"}

# a dimension may be hard-prohibited, forcing the maximum control class
PROHIBITED = "PROHIBITED"

_CC_RANK = {c: i for i, c in enumerate(CONTROL_CLASSES)}
_RISK_RANK = {lvl: i for i, lvl in enumerate(RISK_LEVELS)}  # UNKNOWN ranks highest
_CALIBRATION_TOL = 1e-6


def _cc_for_level(level) -> str:
    """Control class for one risk level. An unrecognised / missing level is
    treated as UNKNOWN (CC3), never as low (INV-0006-22)."""
    if level == PROHIBITED:
        return "CC5"
    return RISK_TO_CC.get(str(level).upper() if level is not None else "UNKNOWN",
                          RISK_TO_CC["UNKNOWN"])


def control_floor(risk_vector: dict) -> str:
    """Non-compensatory JOIN over the eight risk dimensions: the MAX control
    class required by any single dimension (D-0006-28). A PROHIBITED dimension
    forces CC5. No dimension can average away another."""
    rv = risk_vector or {}
    best_rank = _CC_RANK["CC0"]
    for dim in RISK_DIMENSIONS:
        cc = _cc_for_level(rv.get(dim, "UNKNOWN"))
        if cc == "CC5":
            return "CC5"
        best_rank = max(best_rank, _CC_RANK[cc])
    return CONTROL_CLASSES[best_rank]


def risk_ge(a, b) -> bool:
    """Ordinal comparison a >= b over risk levels (UNKNOWN ranks at the top so it
    is never treated as lower than a known level)."""
    return _RISK_RANK.get(str(a).upper(), _RISK_RANK["UNKNOWN"]) \
        >= _RISK_RANK.get(str(b).upper(), _RISK_RANK["UNKNOWN"])


def monotonicity_holds(lo: dict, hi: dict) -> bool:
    """Monotonicity of the control floor (INV-0006-21): if ``hi`` dominates
    ``lo`` dimension-by-dimension then the control floor of ``hi`` is at least
    that of ``lo``. Returns True when the property holds (or when ``hi`` does not
    dominate ``lo``, in which case the property does not apply)."""
    lo, hi = lo or {}, hi or {}
    dominates = all(risk_ge(hi.get(d, "UNKNOWN"), lo.get(d, "UNKNOWN"))
                    for d in RISK_DIMENSIONS)
    if not dominates:
        return True
    return _CC_RANK[control_floor(hi)] >= _CC_RANK[control_floor(lo)]


def no_compensation(risk_vector: dict) -> bool:
    """True iff the control floor equals the maximum per-dimension control class
    — i.e. no low dimension has offset a higher one (D-0006-28). This holds by
    construction for :func:`control_floor`; the check guards against regressions."""
    rv = risk_vector or {}
    per_dim = [_cc_for_level(rv.get(d, "UNKNOWN")) for d in RISK_DIMENSIONS]
    if "CC5" in per_dim:
        return control_floor(rv) == "CC5"
    max_rank = max((_CC_RANK[c] for c in per_dim), default=_CC_RANK["CC0"])
    return _CC_RANK[control_floor(rv)] == max_rank


def _calibrated_scenarios(scenarios):
    """Return the list of scenarios if it is fully calibrated (each has a numeric
    probability in [0,1] and a numeric loss, probabilities summing to ~1), else
    None. Ordinal string losses are rejected (they must never be multiplied)."""
    if not scenarios:
        return None
    norm = []
    total_p = 0.0
    for s in scenarios:
        if not isinstance(s, dict):
            return None
        p, loss = s.get("probability"), s.get("loss")
        if isinstance(p, bool) or isinstance(loss, bool):
            return None
        if not isinstance(p, (int, float)) or not isinstance(loss, (int, float)):
            return None
        if p < 0 or p > 1:
            return None
        total_p += float(p)
        norm.append((float(p), float(loss)))
    if abs(total_p - 1.0) > _CALIBRATION_TOL:
        return None
    return norm


def expected_loss(scenarios: list[dict] | None) -> dict:
    """Advisory expected loss E[L] = sum(p_i * L_i), computed ONLY when every
    scenario is calibrated (D-0006-30). Returns
    ``{"status": "CALIBRATED", "value": ..., "advisory": True}`` or
    ``{"status": "NOT_CALIBRATED", "reason": ..., "calibrated": False}``.
    Ordinal labels are never multiplied as numbers."""
    cal = _calibrated_scenarios(scenarios)
    if cal is None:
        return {"status": "NOT_CALIBRATED", "calibrated": False,
                "reason": "scenarios lack calibrated numeric probability/loss "
                          "summing to 1 (D-0006-30)"}
    return {"status": "CALIBRATED", "calibrated": True, "advisory": True,
            "value": sum(p * loss for p, loss in cal)}


def cvar(scenarios: list[dict] | None, alpha: float) -> dict:
    """Advisory Conditional Value at Risk at confidence ``alpha`` (mean loss over
    the worst ``1 - alpha`` probability tail), computed ONLY when calibrated.
    Returns a CALIBRATED result or ``{"status": "NOT_CALIBRATED"}``."""
    cal = _calibrated_scenarios(scenarios)
    if cal is None:
        return {"status": "NOT_CALIBRATED", "calibrated": False,
                "reason": "scenarios not calibrated (D-0006-30)"}
    tail = 1.0 - float(alpha)
    if tail <= 0:
        # degenerate confidence -> worst-case single loss
        worst = max(loss for _p, loss in cal)
        return {"status": "CALIBRATED", "calibrated": True, "advisory": True,
                "alpha": alpha, "value": worst}
    acc = 0.0
    remaining = tail
    for loss, p in sorted(((l, p) for p, l in cal), reverse=True):
        w = p if p < remaining else remaining
        acc += w * loss
        remaining -= w
        if remaining <= 0:
            break
    return {"status": "CALIBRATED", "calibrated": True, "advisory": True,
            "alpha": alpha, "value": acc / tail}


def risk_findings(risk_vector: dict, *,
                  expected_loss_scenarios: list[dict] | None = None) \
        -> list[Finding]:
    """Findings for the risk model. When a quantitative model is requested
    (``expected_loss_scenarios`` provided) but the inputs are uncalibrated, emit
    QUANTITATIVE_RISK_NOT_CALIBRATED (P2, advisory). The hard control floor stands
    regardless: no scalar may override it (§11.7, §12.4)."""
    out: list[Finding] = []
    floor = control_floor(risk_vector)
    if expected_loss_scenarios is not None:
        el = expected_loss(expected_loss_scenarios)
        if el["status"] != "CALIBRATED":
            out.append(Finding(QUANTITATIVE_RISK_NOT_CALIBRATED, P2,
                               "risk_vector",
                               "quantitative expected-loss requested but inputs "
                               "are uncalibrated; falling back to the ordinal "
                               "control floor (INV-0006-20)",
                               {"control_floor": floor,
                                "reason": el.get("reason")}))
    return out

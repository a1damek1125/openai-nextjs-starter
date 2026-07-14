"""Dynamic Safety State Vector + Control-Class Lattice (SP0005 D-0005-18..24,
§11.6/§12, INV-0005-09/10).

The safety state is a VECTOR over ten distinct dimensions (never prematurely
scalarized, §12.1). Each dimension maps to a minimum required control class; the
overall class is the JOIN (max) — a NON-COMPENSATORY structure: a severe
dimension cannot be averaged away by a low one (D-0005-19, §12.2). Risk
monotonicity holds: worsening risk cannot lower the required class without
validated compensation (D-0005-20). UNKNOWN is NOT LOW (INV-0005-09). A hard
prohibition dominates all optimization (D-0005-22, INV-0005-10); expected loss is
advisory only (D-0005-23); tail-risk math runs only where calibrated (D-0005-24).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, STATE_DIMENSIONS, RISK_LEVELS,
                    CONTROL_CLASSES, PROHIBITED_ACTION, UNKNOWN_TREATED_AS_LOW,
                    TAIL_RISK_NOT_CALIBRATED, PROHIBITED_PRACTICE_CANDIDATE)

# per-dimension risk level -> minimum control class. UNKNOWN maps HIGH (never LOW,
# INV-0005-09): uncertainty about a potentially severe action raises controls.
_LEVEL_TO_CC = {"NONE": "CC0", "LOW": "CC1", "MEDIUM": "CC2", "HIGH": "CC3",
                "CRITICAL": "CC4", "UNKNOWN": "CC3"}
_CC_ORDER = {cc: i for i, cc in enumerate(CONTROL_CLASSES)}
_RISK_ORDER = {lvl: i for i, lvl in enumerate(
    ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"])}


def normalize_vector(vec: dict) -> dict:
    """Return the 10-dim state vector; missing dims are UNKNOWN (not LOW)."""
    return {d: vec.get(d, "UNKNOWN") for d in STATE_DIMENSIONS}


def g(level: str) -> str:
    """Per-dimension minimum control class g_i(x_i)."""
    return _LEVEL_TO_CC.get(level, "CC3")   # unrecognized -> treat as HIGH


def control_class(vec: dict) -> str:
    """ControlClass(x) = join_i g_i(x_i) = the maximum required class (non-
    compensatory, D-0005-19)."""
    v = normalize_vector(vec)
    best = "CC0"
    for d in STATE_DIMENSIONS:
        cc = g(v[d])
        if _CC_ORDER[cc] > _CC_ORDER[best]:
            best = cc
    return best


def risk_ge(y: dict, x: dict) -> bool:
    """y >=_risk x : y is no better than x on every dimension (UNKNOWN treated as
    HIGH for ordering)."""
    vy, vx = normalize_vector(y), normalize_vector(x)

    def lvl(v):
        return _RISK_ORDER.get(v, _RISK_ORDER["HIGH"])   # UNKNOWN ~ HIGH
    return all(lvl(vy[d]) >= lvl(vx[d]) for d in STATE_DIMENSIONS)


def monotonicity_holds(x: dict, y: dict) -> bool:
    """If y >=_risk x then ControlClass(y) >= ControlClass(x) (D-0005-20)."""
    if not risk_ge(y, x):
        return True   # precondition not met -> property vacuously holds
    return _CC_ORDER[control_class(y)] >= _CC_ORDER[control_class(x)]


def evaluate(action: dict, vec: dict, *, prohibited: bool = False,
             prohibited_practice: bool = False) -> tuple[str, list[Finding]]:
    """Return (decision_class, findings). Hard prohibition dominates: a prohibited
    action is DENY regardless of any score (INV-0005-10). UNKNOWN dims never lower
    the class."""
    out: list[Finding] = []
    if prohibited:
        out.append(Finding(PROHIBITED_ACTION, P0, action.get("action_type", "-"),
                           "action is hard-prohibited; optimization cannot allow "
                           "it (INV-0005-10)", {}))
        return "DENY", out
    if prohibited_practice:
        out.append(Finding(PROHIBITED_PRACTICE_CANDIDATE, P0,
                           action.get("action_type", "-"),
                           "action matches a prohibited-practice candidate — "
                           "requires qualified review before any authority", {}))
    v = normalize_vector(vec)
    # detect an UNKNOWN dimension that a caller tried to treat as LOW
    for d in STATE_DIMENSIONS:
        if vec.get(d) == "LOW" and vec.get(d + "_source") == "UNKNOWN_DEFAULT":
            out.append(Finding(UNKNOWN_TREATED_AS_LOW, P1, d,
                               f"dimension {d} defaulted UNKNOWN but recorded LOW",
                               {}))
    return control_class(v), out


def expected_loss(prob: float | None, severity: float | None) -> dict:
    """EL = P(L) x Severity — ADVISORY only (D-0005-23). Returns not-calibrated
    when inputs are absent."""
    if prob is None or severity is None:
        return {"status": "NOT_CALIBRATED", "advisory": True}
    return {"status": "CALIBRATED", "expected_loss": round(prob * severity, 6),
            "advisory": True}


def tail_risk(distribution: dict | None) -> dict:
    """CVaR-style tail risk only where a defensible distribution + units exist
    (D-0005-24). Else TAIL_RISK_NOT_CALIBRATED."""
    if not distribution or not distribution.get("units") \
            or not distribution.get("samples"):
        return {"status": "TAIL_RISK_NOT_CALIBRATED"}
    return {"status": "CALIBRATED", "note": "caller supplies calibrated model"}

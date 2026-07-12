"""Unsafe Control Action Registry (SP0005 §10, D-0005-06, STPA).

For every relevant control action, the four STPA UCA categories are analyzed:
NOT_PROVIDED_WHEN_REQUIRED, PROVIDED_WHEN_UNSAFE, WRONG_TIMING_OR_ORDER,
STOPPED_TOO_SOON_OR_APPLIED_TOO_LONG (AC-0005-014). Each UCA links to a hazard.
"""
from __future__ import annotations

from .model import Finding, P1, UCA_CATEGORIES, INVALID_SAFETY_SCHEMA


def validate_ucas(reg: dict) -> list[Finding]:
    out: list[Finding] = []
    hazards = {h["hazard_id"] for h in reg.get("hazards", [])}
    seen: set[str] = set()
    for u in reg.get("unsafe_control_actions", []):
        uid = u.get("uca_id")
        if uid in seen:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, uid,
                               "duplicate uca_id", {}))
        seen.add(uid)
        if u.get("category") not in UCA_CATEGORIES:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, uid or "-",
                               f"invalid UCA category {u.get('category')!r}", {}))
        for hz in u.get("hazard_refs", []):
            if hz not in hazards:
                out.append(Finding(INVALID_SAFETY_SCHEMA, P1, uid or "-",
                                   f"UCA references unknown hazard {hz!r}", {}))
    return out


def categories_covered(reg: dict, control_action: str) -> set[str]:
    """Which of the 4 UCA categories are analyzed for a given control action."""
    return {u["category"] for u in reg.get("unsafe_control_actions", [])
            if u.get("control_action") == control_action}

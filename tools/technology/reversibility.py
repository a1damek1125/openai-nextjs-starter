"""Reversibility, switching-cost vector & multi-dimensional lock-in exposure
(SP0004 D-0004-12/13/14, §10.2, INV-0004-10).

Reversibility class R0..R4 (config switch → semantic rewrite). Switching cost is a
VECTOR (adapter/data/state/revalidation/operations/training/downtime) — never
collapsed to a scalar unless normalization is explicit (D-0004-13). Lock-in
exposure keeps its ten dimensions separate (D-0004-14). An interface existing does
NOT prove replaceability (INV-0004-10) — that is measured in exit_readiness.py.
"""
from __future__ import annotations

from .model import (Finding, P1, REVERSIBILITY, SWITCHING_COST_DIMS,
                    LOCK_IN_DIMENSIONS, ONE_WAY_MIGRATION_RISK, INVALID_TDR)

REVERSIBILITY_MEANING = {
    "R0": "configuration switch",
    "R1": "adapter replacement",
    "R2": "data migration",
    "R3": "runtime-state migration",
    "R4": "semantic / architecture rewrite",
}


def validate_reversibility(decision: dict) -> list[Finding]:
    out: list[Finding] = []
    did = decision.get("decision_id", "-")
    rc = decision.get("reversibility_class")
    if rc is not None and rc not in REVERSIBILITY:
        out.append(Finding(INVALID_TDR, P1, did,
                           f"invalid reversibility_class {rc!r}", {}))
    # R3/R4 imply one-way migration risk that must be explicitly acknowledged
    if rc in ("R3", "R4") and not decision.get("one_way_migration_ack"):
        out.append(Finding(ONE_WAY_MIGRATION_RISK, P1, did,
                           f"reversibility {rc} ({REVERSIBILITY_MEANING.get(rc)}) "
                           "requires explicit one-way-migration acknowledgement "
                           "(D-0004-70)", {}))
    sc = decision.get("switching_cost", {})
    if sc and not isinstance(sc, dict):
        out.append(Finding(INVALID_TDR, P1, did,
                           "switching_cost must be a vector (dict)", {}))
    return out


def switching_cost_vector(decision: dict) -> dict:
    """Return the full switching-cost vector; missing dims are UNKNOWN, never 0."""
    sc = decision.get("switching_cost", {})
    return {d: sc.get(d, "UNKNOWN") for d in SWITCHING_COST_DIMS}


def lock_in_exposure(decision: dict) -> dict:
    """Return the ten lock-in dimensions kept separate; missing = UNKNOWN."""
    li = decision.get("lock_in_exposure", {})
    return {d: li.get(d, "UNKNOWN") for d in LOCK_IN_DIMENSIONS}


def max_lock_in(decision: dict) -> str:
    """Highest single lock-in level present (never an average — §12.6)."""
    order = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4,
             "UNKNOWN": -1}
    li = lock_in_exposure(decision)
    ranked = [(order.get(v, -1), d) for d, v in li.items()]
    ranked.sort(reverse=True)
    return li[ranked[0][1]] if ranked else "UNKNOWN"

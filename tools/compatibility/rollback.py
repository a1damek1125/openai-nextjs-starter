"""Last Safe Rollback Point + Rollback/Forward-Fix (SP0007 D-0007-37/51/52,
AC-0007-142/143/169/170).

An up migration never proves rollback (D-0007-37, INV-0007-31): a rollback
plan may only reference edges whose inverse transformer exists AND is
verified — anything else is ROLLBACK_NOT_AVAILABLE. Every plan carries a last
safe rollback point (D-0007-51); once execution passes it, rollback is
REJECTED (LAST_SAFE_ROLLBACK_POINT_REACHED, AC-0007-170) and the only way out
is forward: a forward-fix plan is required (D-0007-52). Rollback evidence
binds the inverse transformer hash and the round-trip result into a
reproducible proof envelope (AC-0007-196).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, ROLLBACK_NOT_AVAILABLE,
                    LAST_SAFE_ROLLBACK_POINT_REACHED, INVALID_COMPAT_SCHEMA)
from .canon import core_hash, transformer_hash


def _plan_edge_ids(plan: dict) -> list:
    if "edge_ids" in plan:
        return list(plan.get("edge_ids") or [])
    return [s.get("edge_id") for s in plan.get("steps", [])
            if isinstance(s, dict)]


def validate_rollback_plan(plan: dict, edges_by_id: dict) -> list[Finding]:
    """A rollback plan may ONLY reference edges with a real, VERIFIED inverse
    (D-0007-37, INV-0007-31). Missing edge, missing inverse_transformer_ref,
    or inverse_verified is not True => ROLLBACK_NOT_AVAILABLE (P0)."""
    out: list[Finding] = []
    pid = plan.get("plan_id", "-")
    edge_ids = _plan_edge_ids(plan)
    if not edge_ids:
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, pid,
                           "rollback plan references no migration edges", {}))
    for eid in edge_ids:
        edge = edges_by_id.get(eid)
        if edge is None:
            out.append(Finding(ROLLBACK_NOT_AVAILABLE, P0, str(eid),
                               f"rollback plan {pid!r} references unknown "
                               f"edge {eid!r} — no inverse can exist "
                               "(fail-closed)", {"plan_id": pid}))
            continue
        if not edge.get("inverse_transformer_ref"):
            out.append(Finding(ROLLBACK_NOT_AVAILABLE, P0, str(eid),
                               f"edge {eid!r} has no inverse_transformer_ref "
                               "— rollback is not available (D-0007-37)",
                               {"plan_id": pid}))
            continue
        if edge.get("inverse_verified") is not True:
            out.append(Finding(ROLLBACK_NOT_AVAILABLE, P0, str(eid),
                               f"edge {eid!r} inverse is not verified — an up "
                               "migration does not prove rollback "
                               "(INV-0007-31)", {"plan_id": pid}))
    return out


def _after_boundary(plan: dict, current_position: str) -> bool:
    """True iff current_position is strictly AFTER the last safe rollback
    point in plan['step_order']. Fail-closed: an undeclared boundary or an
    unknown position counts as after."""
    order = list(plan.get("step_order", []))
    boundary = plan.get("last_safe_rollback_point")
    if boundary not in order or current_position not in order:
        return True
    return order.index(current_position) > order.index(boundary)


def boundary_findings(plan: dict, *, current_position: str) -> list[Finding]:
    """Once execution passes the last safe rollback point, rollback is
    REJECTED: LAST_SAFE_ROLLBACK_POINT_REACHED (P0), rollback blocked
    (D-0007-51, AC-0007-170)."""
    if not _after_boundary(plan, current_position):
        return []
    pid = plan.get("plan_id", "-")
    return [Finding(LAST_SAFE_ROLLBACK_POINT_REACHED, P0, pid,
                    f"position {current_position!r} is past the last safe "
                    f"rollback point "
                    f"{plan.get('last_safe_rollback_point')!r} — rollback "
                    "blocked; forward fix is the only path (D-0007-51, "
                    "AC-0007-170)",
                    {"current_position": current_position,
                     "last_safe_rollback_point":
                         plan.get("last_safe_rollback_point"),
                     "rollback_blocked": True})]


def forward_fix_required(plan: dict, *, current_position: str) -> dict:
    """Past the boundary, the only exit is forward (D-0007-52). A required
    forward fix without a forward_fix_plan_ref carries a P1 finding."""
    if not _after_boundary(plan, current_position):
        return {"forward_fix_required": False,
                "forward_fix_plan_ref": plan.get("forward_fix_plan_ref"),
                "findings": []}
    findings: list[Finding] = []
    ref = plan.get("forward_fix_plan_ref")
    if not ref:
        findings.append(Finding(INVALID_COMPAT_SCHEMA, P1,
                                plan.get("plan_id", "-"),
                                "forward fix required past the last safe "
                                "rollback point but no forward_fix_plan_ref "
                                "is declared (D-0007-52)", {}))
    return {"forward_fix_required": True, "forward_fix_plan_ref": ref,
            "findings": findings}


def rollback_evidence(edge: dict, result: dict) -> dict:
    """Build the rollback proof-envelope fragment: edge identity, hash of the
    inverse transformer, and the round-trip verdict, sealed under a
    reproducible evidence hash (AC-0007-142/143, AC-0007-196)."""
    inverse = edge.get("inverse_transformer")
    if not isinstance(inverse, dict):
        inverse = {"transformer_id": edge.get("inverse_transformer_ref"),
                   "from_version": edge.get("to_version"),
                   "to_version": edge.get("from_version"),
                   "rules": edge.get("inverse_rules"),
                   "loss_vector": edge.get("inverse_loss_vector")}
    core = {"edge_id": edge.get("migration_edge_id"),
            "inverse_transformer_hash": transformer_hash(inverse),
            "round_trip_passed": bool(result.get("passed"))}
    return dict(core, evidence_hash=core_hash(core))

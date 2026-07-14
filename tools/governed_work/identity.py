"""Execution Identity Registry (SP0006 §10.3, D-0006-12). Every root agent,
subagent, verifier or deterministic executor has an explicit execution identity
bound to one work order, with a parent, delegation depth, role, lease set and
responsibility scope.
"""
from __future__ import annotations

from .model import Finding, P1, INVALID_WORK_SCHEMA

REQUIRED = ("execution_identity_id", "work_order_id", "role")


def validate_identity(idn: dict) -> list[Finding]:
    out: list[Finding] = []
    iid = idn.get("execution_identity_id", "-")
    for f in REQUIRED:
        if not idn.get(f):
            out.append(Finding(INVALID_WORK_SCHEMA, P1, iid,
                               f"execution identity missing {f}", {}))
    depth = idn.get("delegation_depth", 0)
    if not isinstance(depth, int) or depth < 0:
        out.append(Finding(INVALID_WORK_SCHEMA, P1, iid,
                           "delegation_depth must be a non-negative int", {}))
    # a non-root identity must reference a parent (INV-0006-14)
    if depth and not idn.get("parent_identity_id"):
        out.append(Finding(INVALID_WORK_SCHEMA, P1, iid,
                           "non-root identity has no parent", {}))
    return out


def validate_registry(idns: list[dict]) -> list[Finding]:
    out: list[Finding] = []
    seen: set[str] = set()
    by_id = {i.get("execution_identity_id"): i for i in idns}
    for idn in idns:
        out.extend(validate_identity(idn))
        iid = idn.get("execution_identity_id")
        if iid in seen:
            out.append(Finding(INVALID_WORK_SCHEMA, P1, iid,
                               "duplicate execution_identity_id", {}))
        seen.add(iid)
        # every active identity belongs to exactly one work order (INV-0006-14)
        pid = idn.get("parent_identity_id")
        if pid and pid in by_id and \
                by_id[pid].get("work_order_id") != idn.get("work_order_id"):
            out.append(Finding(INVALID_WORK_SCHEMA, P1, iid,
                               "identity work_order differs from parent's", {}))
    return out

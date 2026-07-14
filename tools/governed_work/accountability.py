"""Accountability Conservation + Responsibility Chain (SP0006 §9.13, D-0006-21/22,
INV-0006-13).

Delegation distributes WORK, not ACCOUNTABILITY (D-0006-21): the accountable
owner at the root equals the accountable owner at the terminal outcome unless an
explicit authorized reassignment exists. A subagent may be RESPONSIBLE for a
subtask while the accountable owner remains explicitly traceable (D-0006-22).
"""
from __future__ import annotations

from .model import Finding, P0, P1, ACCOUNTABILITY_CHAIN_BROKEN
from .canon import core_hash


def responsibility_chain(work_order: dict, edges: list[dict]) -> dict:
    """Build the responsibility chain: root owner + per-identity responsibility,
    with the single accountable owner carried through every edge."""
    owner = work_order.get("accountable_owner_id")
    links = []
    for e in edges:
        links.append({
            "parent_identity": e.get("parent_identity"),
            "child_identity": e.get("child_identity"),
            "subtask_scope": e.get("subtask_scope", {}),
            "responsible": e.get("child_identity"),
            "accountable_owner_id": e.get("accountable_owner_id") or owner,
        })
    return {"work_order_id": work_order.get("work_order_id"),
            "accountable_owner_id": owner,
            "links": links,
            "chain_hash": core_hash({"owner": owner,
                                     "links": [(l["parent_identity"],
                                                l["child_identity"],
                                                l["accountable_owner_id"])
                                               for l in links]})}


def conservation_findings(work_order: dict, edges: list[dict],
                          *, terminal_owner: str | None = None,
                          reassignments: list[dict] | None = None) -> list[Finding]:
    """Owner(root) == Owner(terminal) unless an explicit authorized reassignment
    exists (D-0006-21, §12.8). Every edge must carry the accountable owner."""
    out: list[Finding] = []
    root_owner = work_order.get("accountable_owner_id")
    wid = work_order.get("work_order_id", "-")
    authorized = {r.get("to_owner") for r in (reassignments or [])
                  if r.get("authorized")}
    # every delegation edge must keep an accountable owner traceable
    for e in edges:
        eo = e.get("accountable_owner_id") or root_owner
        if not eo:
            out.append(Finding(ACCOUNTABILITY_CHAIN_BROKEN, P0,
                               e.get("delegation_id", "-"),
                               "delegation edge has no accountable owner "
                               "(INV-0006-13)", {}))
        elif eo != root_owner and eo not in authorized:
            out.append(Finding(ACCOUNTABILITY_CHAIN_BROKEN, P0,
                               e.get("delegation_id", "-"),
                               f"accountable owner changed to {eo!r} without an "
                               "authorized reassignment (D-0006-21)", {}))
    # terminal owner must match root unless authorized reassignment
    if terminal_owner is not None and terminal_owner != root_owner \
            and terminal_owner not in authorized:
        out.append(Finding(ACCOUNTABILITY_CHAIN_BROKEN, P0, wid,
                           f"terminal accountable owner {terminal_owner!r} != "
                           f"root {root_owner!r} without authorized reassignment "
                           "(§12.8)", {}))
    return out


def validate_reassignment(reassignment: dict) -> list[Finding]:
    """An owner reassignment must be explicit and authorized (D-0006-22)."""
    out: list[Finding] = []
    rid = reassignment.get("reassignment_id", "-")
    if not reassignment.get("authorized"):
        out.append(Finding(ACCOUNTABILITY_CHAIN_BROKEN, P1, rid,
                           "owner reassignment is not explicitly authorized", {}))
    if not (reassignment.get("from_owner") and reassignment.get("to_owner")):
        out.append(Finding(ACCOUNTABILITY_CHAIN_BROKEN, P1, rid,
                           "reassignment missing from/to owner", {}))
    return out

"""Dependency Impact Cone + Rework Impact Cone (SP0003 §11.20/§11.21,
D-0003-22/23/32, INV-0003-07).

Dependency impact follows the hard precedence graph forward (what downstream work
is affected structurally). Rework impact follows the SEPARATE rework graph and
yields review/reverify/possible-rework signals — it never deletes completed work
(§11.21). The two cones are deliberately distinct (AC-0003-67).
"""
from __future__ import annotations

from .graphalgo import precedence_pairs, reachable_from
from .hypergraph import default_active
from .rework import rework_impact as _rework_reach


def dependency_impact_cone(program: dict, changed: set[str],
                           active=default_active) -> dict:
    """Impact(S) = S ∪ ReachableSuccessors(S) over the hard precedence graph."""
    pairs = precedence_pairs(program, active)
    succ = reachable_from(pairs, sorted(changed))
    cone = set(changed) | succ
    return {"changed": sorted(changed),
            "downstream": sorted(succ),
            "cone": sorted(cone),
            "cone_size": len(cone)}


def rework_impact_cone(program: dict, changed: set[str]) -> dict:
    """ReworkImpact(S) over the rework graph, classified by required action."""
    reach = _rework_reach(program, set(changed))
    # classify by the strongest rework edge type reaching each node
    action: dict[str, str] = {}
    order = {"MIGRATE_IF_CHANGED": 4, "REWORK_TRIGGER": 3, "MAY_INVALIDATE": 2,
             "REVERIFY_IF_CHANGED": 1, "RECALIBRATE_IF_CHANGED": 1}
    label = {4: "POSSIBLE_REWORK", 3: "POSSIBLE_REWORK", 2: "REVERIFY_REQUIRED",
             1: "REVIEW_REQUIRED"}
    # single-hop classification for the direct signal; reachable set is the cone
    for e in program.get("rework_edges", []):
        if e.get("from_node") in changed and e.get("to_node") in reach:
            r = order.get(e.get("rework_type"), 1)
            tgt = e["to_node"]
            if r > order.get(action.get(tgt, ""), 0):
                action[tgt] = e.get("rework_type")
    classified = {n: label[order.get(action.get(n, "REVERIFY_IF_CHANGED"), 1)]
                  for n in reach}
    return {"changed": sorted(changed), "rework_cone": sorted(reach),
            "classified": classified, "cone_size": len(reach)}

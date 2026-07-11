"""AND/OR hypergraph achievability, dominators and bounded min-cut (SP0003
§11.14/§11.15, D-0003-29/30/31).

Ordinary pairwise reachability treats a JOINT (ALL_OF) prerequisite as
OR-reachable and therefore UNDER-reports dominators and fragility. Resilience
analysis must respect the hypergraph AND/OR/threshold semantics: a node is
achievable only when its prerequisite EXPRESSION is satisfied by already-achievable
nodes. Dominators are then exact. Minimum cut over an AND/OR graph is NP-hard in
general, so we search cuts of BOUNDED size and report the bound honestly
(D-0003-30 — never overclaim exact hypergraph cut semantics).
"""
from __future__ import annotations

from itertools import combinations

from .hypergraph import incoming, edge_satisfied, default_active


def achievable(program: dict, *, blocked: set[str] | None = None,
               active=default_active) -> set[str]:
    """Forward AND/OR closure: a node is achievable iff it is not blocked and
    either has no incoming active edge (a source) or some incoming active edge is
    satisfied by the already-achievable set."""
    blocked = blocked or set()
    inc = incoming(program, active)
    ach: set[str] = set()
    nodes = [n["node_id"] for n in program.get("nodes", [])]
    changed = True
    while changed:
        changed = False
        for nid in nodes:
            if nid in ach or nid in blocked:
                continue
            edges = inc.get(nid, [])
            if not edges or any(edge_satisfied(e, ach) for e in edges):
                ach.add(nid)
                changed = True
    return ach


def is_achievable(program, target, *, blocked=None, active=default_active) -> bool:
    return target in achievable(program, blocked=blocked or set(), active=active)


def hyper_dominators(program: dict, target: str, active=default_active
                     ) -> list[str]:
    """Exact single-node dominators under AND/OR semantics: nodes whose blocking
    makes `target` unachievable."""
    if not is_achievable(program, target, active=active):
        return []
    doms: list[str] = []
    for n in sorted(x["node_id"] for x in program.get("nodes", [])):
        if n == target:
            continue
        if not is_achievable(program, target, blocked={n}, active=active):
            doms.append(n)
    return doms


def hyper_min_cut(program: dict, target: str, *, max_size: int = 3,
                  active=default_active) -> dict:
    """Bounded minimum blocker set: smallest set of nodes whose blocking renders
    `target` unachievable, searched up to `max_size`. Returns the size, an example
    cut, and whether the search was exhaustive at that bound."""
    if not is_achievable(program, target, active=active):
        return {"min_cut_size": 0, "example_cut": [], "bounded": False,
                "note": "target already unachievable"}
    candidates = sorted(n["node_id"] for n in program.get("nodes", [])
                        if n["node_id"] != target)
    for size in range(1, max_size + 1):
        for combo in combinations(candidates, size):
            if not is_achievable(program, target, blocked=set(combo),
                                 active=active):
                return {"min_cut_size": size, "example_cut": sorted(combo),
                        "bounded": True, "exhaustive_up_to": max_size,
                        "single_point_fragility": size == 1}
    return {"min_cut_size": f">{max_size}", "example_cut": [], "bounded": True,
            "exhaustive_up_to": max_size,
            "note": f"no cut of size <= {max_size} found"}

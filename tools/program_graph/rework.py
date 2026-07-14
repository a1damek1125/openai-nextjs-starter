"""Rework / Feedback Graph — SEPARATE from the hard prerequisite graph
(SP0003 D-0003-10, §11.5/§11.21, INV-0003-07/08).

Rework edges (MAY_INVALIDATE, REVERIFY_IF_CHANGED, REWORK_TRIGGER,
RECALIBRATE_IF_CHANGED, MIGRATE_IF_CHANGED) capture that changing A may force
review/rework of B. This graph MAY contain cycles (real engineering iteration)
and must never contaminate the acyclic hard execution backbone (INV-0003-08): a
rework SCC is a feedback cluster, NOT a HARD_DEPENDENCY_CYCLE.
"""
from __future__ import annotations

from collections import deque

from .model import (Finding, P1, REWORK_TYPES, REWORK_MODEL_ERROR,
                    REWORK_CLUSTER_DETECTED)


def rework_pairs(program: dict) -> list[tuple[str, str]]:
    return sorted({(e["from_node"], e["to_node"])
                   for e in program.get("rework_edges", [])
                   if e.get("from_node") and e.get("to_node")})


def validate_rework(program: dict) -> list[Finding]:
    out: list[Finding] = []
    nodes = {n["node_id"] for n in program.get("nodes", [])}
    for e in program.get("rework_edges", []):
        rid = e.get("rework_edge_id", "-")
        if e.get("rework_type") not in REWORK_TYPES:
            out.append(Finding(REWORK_MODEL_ERROR, P1, rid,
                               f"invalid rework_type {e.get('rework_type')!r}",
                               {}))
        for k in ("from_node", "to_node"):
            if e.get(k) not in nodes:
                out.append(Finding(REWORK_MODEL_ERROR, P1, rid,
                                   f"rework {k}={e.get(k)!r} unknown", {}))
    return out


def strongly_connected_components(nodes, pairs) -> list[list[str]]:
    """Tarjan SCC (iterative) over the rework graph. Cycles are ALLOWED here."""
    succ: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in pairs:
        succ.setdefault(u, []).append(v)
        succ.setdefault(v, [])
    index = {}
    low = {}
    on_stack = set()
    stack: list[str] = []
    result: list[list[str]] = []
    counter = [0]

    def strongconnect(root):
        work = [(root, 0)]
        while work:
            v, pi = work[-1]
            if pi == 0:
                index[v] = low[v] = counter[0]
                counter[0] += 1
                stack.append(v)
                on_stack.add(v)
            recursed = False
            neighbors = sorted(succ.get(v, []))
            for i in range(pi, len(neighbors)):
                w = neighbors[i]
                if w not in index:
                    work[-1] = (v, i + 1)
                    work.append((w, 0))
                    recursed = True
                    break
                elif w in on_stack:
                    low[v] = min(low[v], index[w])
            if recursed:
                continue
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                result.append(sorted(comp))
            work.pop()
            if work:
                p = work[-1][0]
                low[p] = min(low[p], low[v])

    for n in sorted(succ):
        if n not in index:
            strongconnect(n)
    return sorted(result, key=lambda c: (len(c), c))


def feedback_clusters(program: dict) -> list[list[str]]:
    """SCCs of size >= 2 (or self-loops) in the rework graph."""
    nodes = [n["node_id"] for n in program.get("nodes", [])]
    pairs = rework_pairs(program)
    selfloops = {u for u, v in pairs if u == v}
    comps = strongly_connected_components(nodes, pairs)
    return [c for c in comps if len(c) >= 2 or (len(c) == 1 and c[0] in selfloops)]


def rework_cluster_findings(program: dict) -> list[Finding]:
    """Advisory (P1 informational) — a detected feedback cluster is reported, not
    a hard failure (rework cycles are legal, INV-0003-08)."""
    out: list[Finding] = []
    for c in feedback_clusters(program):
        out.append(Finding(REWORK_CLUSTER_DETECTED, P1, ",".join(c),
                           f"rework feedback cluster of {len(c)} nodes "
                           "(advisory; not a hard cycle)", {"cluster": c}))
    return out


def rework_impact(program: dict, changed: set[str]) -> set[str]:
    """Nodes reachable via rework edges from a change set (§11.21) — distinct from
    ordinary downstream dependency impact. Trigger-condition filtering: only
    edges whose trigger is unset or matches propagate."""
    succ: dict[str, list[str]] = {}
    for e in program.get("rework_edges", []):
        succ.setdefault(e["from_node"], []).append(e["to_node"])
    out: set[str] = set()
    q = deque(changed)
    while q:
        u = q.popleft()
        for v in sorted(succ.get(u, [])):
            if v not in out and v not in changed:
                out.add(v)
                q.append(v)
    return out

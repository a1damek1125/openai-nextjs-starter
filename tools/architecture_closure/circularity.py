"""Unsupported circular-assurance detection (SP0010 FUNCTION H, §11.6, §12,
D-0010-07, AC-0010-058/059).

No constitution may launder its own assumptions: a critical claim that depends
only on an unsupported support cycle cannot close (INV-0010-13). Support
dependencies form a graph; its strongly-connected components are found by
Tarjan's algorithm. An SCC is ANCHORED only when at least one required support
chain enters it from an INDEPENDENTLY GROUNDED external source (an anchored
claim outside the SCC); otherwise it is UNSUPPORTED and blocks any critical
claim resting on it.
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, SCC_CLASSES


def _tarjan(nodes: list, edges: dict) -> list:
    """Return the list of SCCs (each a list of nodes). edges: node -> [deps]."""
    index = {}
    low = {}
    on_stack = {}
    stack = []
    counter = [0]
    sccs = []
    order = list(nodes)

    def strong(v, work):
        # iterative Tarjan to avoid recursion limits
        work.append((v, 0))
        while work:
            node, pi = work[-1]
            if pi == 0:
                index[node] = low[node] = counter[0]
                counter[0] += 1
                stack.append(node)
                on_stack[node] = True
            recursed = False
            deps = edges.get(node, [])
            for j in range(pi, len(deps)):
                w = deps[j]
                if w not in index:
                    work[-1] = (node, j + 1)
                    work.append((w, 0))
                    recursed = True
                    break
                elif on_stack.get(w):
                    low[node] = min(low[node], index[w])
            if recursed:
                continue
            if low[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    comp.append(w)
                    if w == node:
                        break
                sccs.append(sorted(comp))
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])

    for v in order:
        if v not in index:
            strong(v, [])
    return sccs


def analyze(support_edges: dict, anchored: set, nodes: set) -> dict:
    """support_edges: claim -> [claims it depends on for support].
    Classify each non-trivial SCC as ANCHORED / UNSUPPORTED (§11.6)."""
    sccs = _tarjan(sorted(nodes), support_edges)
    results = []
    for comp in sccs:
        comp_set = set(comp)
        is_cycle = len(comp) > 1 or any(
            n in support_edges.get(n, []) for n in comp)
        if not is_cycle:
            continue
        # anchored iff some member depends on an anchored claim OUTSIDE the SCC
        # (D-0010-07). An in-cycle member being itself "anchored" does NOT
        # anchor the cycle — the anchor must ENTER from outside, or the cycle
        # launders its own assumptions (red-team P1-4).
        entering_anchor = any(
            dep in anchored and dep not in comp_set
            for n in comp for dep in support_edges.get(n, []))
        cls = "ANCHORED" if entering_anchor else "UNSUPPORTED"
        results.append({
            "scc_id": "SCC-" + hash_obj(comp)[:16],
            "members": comp,
            "classification": cls,
        })
    return {"sccs": results,
            "unsupported": [s["scc_id"] for s in results
                            if s["classification"] == "UNSUPPORTED"]}


def circularity_findings(analysis: dict, critical: set,
                         support_edges: dict) -> list[Finding]:
    """A critical claim resting on an unsupported SCC blocks closure."""
    out: list[Finding] = []
    unsupported_members = set()
    for s in analysis["sccs"]:
        if s["classification"] == "UNSUPPORTED":
            unsupported_members |= set(s["members"])
            out.append(Finding(
                "UNSUPPORTED_CIRCULAR_ASSURANCE", P0, s["scc_id"],
                f"unsupported support cycle {s['members']}: a cycle needs an "
                "independently grounded external anchor (D-0010-07)",
                {"members": s["members"]}))
    return out


def circularity_root(analysis: dict) -> str:
    return hash_obj([s["scc_id"] + ":" + s["classification"]
                     for s in analysis["sccs"]])

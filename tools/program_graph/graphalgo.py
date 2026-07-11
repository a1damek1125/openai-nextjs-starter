"""Deterministic graph algorithms over a COMPILED scenario execution graph
(SP0003 §11.4/§11.14/§11.15, §23).

Everything here is mechanically decidable and must never be delegated to an LLM:
cycle detection (Kahn), topological order, reachability, transitive reduction,
exact dominators, and exact minimum vertex cut (vertex-split max-flow / min-cut).

A hyperedge is expanded to precedence PAIRS (tail -> head) purely for these
structural analyses; the pair expansion is NOT a claim that each pairwise edge is
independently sufficient (readiness semantics live in hypergraph.py).
"""
from __future__ import annotations

from collections import deque
from typing import Callable, Iterable

from .hypergraph import default_active

INF = float("inf")


def precedence_pairs(program: dict,
                     active: Callable[[dict], bool] = default_active
                     ) -> list[tuple[str, str]]:
    """Active tail->head precedence pairs (deduplicated, sorted)."""
    seen: set[tuple[str, str]] = set()
    for e in program.get("hyperedges", []):
        if not active(e):
            continue
        h = e["head_node"]
        for t in e.get("tail_nodes", []):
            seen.add((t, h))
    return sorted(seen)


def mandatory_precedence_pairs(program: dict,
                               active: Callable[[dict], bool] = default_active
                               ) -> list[tuple[str, str]]:
    """Active tail->head pairs from MANDATORY prerequisites only. A tail is
    mandatory iff its edge is ALL_OF (every tail required). ANY_OF / threshold
    tails are NOT individually mandatory (they are a choice), so they cannot form
    a hard-backbone cycle (red-team SWARM-L P2). Used for the acyclicity gate."""
    seen: set[tuple[str, str]] = set()
    for e in program.get("hyperedges", []):
        if not active(e) or e.get("logic", "ALL_OF") != "ALL_OF":
            continue
        h = e["head_node"]
        for t in e.get("tail_nodes", []):
            seen.add((t, h))
    return sorted(seen)


def node_ids(program: dict) -> list[str]:
    return sorted(n["node_id"] for n in program.get("nodes", []))


def adjacency(nodes: Iterable[str], pairs: Iterable[tuple[str, str]]):
    succ: dict[str, set[str]] = {n: set() for n in nodes}
    pred: dict[str, set[str]] = {n: set() for n in nodes}
    for u, v in pairs:
        succ.setdefault(u, set()).add(v)
        pred.setdefault(v, set()).add(u)
        succ.setdefault(v, set())
        pred.setdefault(u, set())
    return succ, pred


def detect_cycle(nodes, pairs) -> list[str]:
    """Return a sorted list of node_ids that remain in a cycle (empty if DAG),
    via Kahn's algorithm — O(V+E)."""
    nodes = list(nodes)
    succ, pred = adjacency(nodes, pairs)
    indeg = {n: len(pred[n]) for n in succ}
    q = deque(sorted(n for n in succ if indeg[n] == 0))
    removed = 0
    while q:
        u = q.popleft()
        removed += 1
        for v in sorted(succ[u]):
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    if removed == len(succ):
        return []
    return sorted(n for n in succ if indeg[n] > 0)


def topo_order(nodes, pairs) -> list[str] | None:
    """Deterministic topological order (lexicographic tie-break); None if cyclic."""
    nodes = list(nodes)
    succ, pred = adjacency(nodes, pairs)
    indeg = {n: len(pred[n]) for n in succ}
    q = deque(sorted(n for n in succ if indeg[n] == 0))
    order: list[str] = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in sorted(succ[u]):
            indeg[v] -= 1
            if indeg[v] == 0:
                # insert preserving lexicographic determinism
                q.append(v)
                q = deque(sorted(q))
    return order if len(order) == len(succ) else None


def reachable_from(pairs, sources: Iterable[str]) -> set[str]:
    """All nodes reachable FROM sources following edges forward (excludes the
    sources themselves unless reachable via a cycle)."""
    succ: dict[str, set[str]] = {}
    for u, v in pairs:
        succ.setdefault(u, set()).add(v)
    out: set[str] = set()
    q = deque(sources)
    while q:
        u = q.popleft()
        for v in sorted(succ.get(u, ())):
            if v not in out:
                out.add(v)
                q.append(v)
    return out


def reachable_to(pairs, targets: Iterable[str]) -> set[str]:
    """All ancestors that can reach any target following edges backward."""
    pred: dict[str, set[str]] = {}
    for u, v in pairs:
        pred.setdefault(v, set()).add(u)
    out: set[str] = set()
    q = deque(targets)
    while q:
        v = q.popleft()
        for u in sorted(pred.get(v, ())):
            if u not in out:
                out.add(u)
                q.append(u)
    return out


def transitive_reduction(nodes, pairs) -> list[tuple[str, str]]:
    """Keep edge (u,v) iff v is NOT reachable from u without that direct edge —
    i.e. the edge is not implied by a longer path (DAG only). Deterministic."""
    keep: list[tuple[str, str]] = []
    for u, v in sorted(set(pairs)):
        others = [(a, b) for a, b in pairs if not (a == u and b == v)]
        if v not in reachable_from(others, [u]):
            keep.append((u, v))
    return keep


def _reach_excluding(pairs, source, target, removed) -> bool:
    """Is target reachable from source with `removed` node deleted?"""
    if source == removed or target == removed:
        return False
    succ: dict[str, set[str]] = {}
    for u, v in pairs:
        if u == removed or v == removed:
            continue
        succ.setdefault(u, set()).add(v)
    seen = {source}
    q = deque([source])
    while q:
        u = q.popleft()
        if u == target:
            return True
        for v in sorted(succ.get(u, ())):
            if v not in seen:
                seen.add(v)
                q.append(v)
    return target in seen


def dominators(program_nodes, pairs, source, target) -> list[str]:
    """Exact program dominators (§11.14): internal nodes lying on EVERY path from
    source to target — i.e. nodes whose removal disconnects source from target.
    O(V*(V+E)), deterministic."""
    if source == target:
        return []
    if not _reach_excluding(pairs, source, target, removed=None):
        # target unreachable even with nothing removed
        return []
    doms: list[str] = []
    for c in sorted(program_nodes):
        if c in (source, target):
            continue
        if not _reach_excluding(pairs, source, target, removed=c):
            doms.append(c)
    return doms


# --- minimum vertex cut via vertex-split max-flow (§11.15) ------------------
class _MaxFlow:
    def __init__(self):
        self.g: dict[str, dict[str, float]] = {}

    def add(self, u, v, cap):
        self.g.setdefault(u, {})
        self.g.setdefault(v, {})
        self.g[u][v] = self.g[u].get(v, 0) + cap
        self.g[v].setdefault(u, 0)

    def bfs(self, s, t, parent):
        seen = {s}
        q = deque([s])
        while q:
            u = q.popleft()
            for v in sorted(self.g.get(u, {})):
                if v not in seen and self.g[u][v] > 1e-9:
                    seen.add(v)
                    parent[v] = u
                    if v == t:
                        return True
                    q.append(v)
        return False

    def maxflow(self, s, t):
        flow = 0.0
        while True:
            parent = {}
            if not self.bfs(s, t, parent):
                break
            # bottleneck
            path_flow = INF
            v = t
            while v != s:
                u = parent[v]
                path_flow = min(path_flow, self.g[u][v])
                v = u
            v = t
            while v != s:
                u = parent[v]
                self.g[u][v] -= path_flow
                self.g[v][u] += path_flow
                v = u
            flow += path_flow
        return flow

    def reachable(self, s):
        seen = {s}
        q = deque([s])
        while q:
            u = q.popleft()
            for v in sorted(self.g.get(u, {})):
                if v not in seen and self.g[u][v] > 1e-9:
                    seen.add(v)
                    q.append(v)
        return seen


def min_vertex_cut(program_nodes, pairs, source, target,
                   protected: set[str] | None = None):
    """Minimum internal-node cut separating source from target (§11.15).
    Vertex-split: v -> v#in -> v#out (cap 1 for ordinary nodes, INF for
    source/target/protected). Returns (cut_size, example_cut_nodes)."""
    protected = set(protected or set())
    protected |= {source, target}
    if target not in reachable_from(pairs, [source]):
        return (0, [])
    mf = _MaxFlow()
    for n in program_nodes:
        cap = INF if n in protected else 1.0
        mf.add(f"{n}#in", f"{n}#out", cap)
    for u, v in pairs:
        mf.add(f"{u}#out", f"{v}#in", INF)
    s, t = f"{source}#out", f"{target}#in"
    size = mf.maxflow(s, t)
    reach = mf.reachable(s)
    cut: list[str] = []
    for n in sorted(program_nodes):
        if n in protected:
            continue
        if f"{n}#in" in reach and f"{n}#out" not in reach:
            cut.append(n)
    return (int(size) if size != INF else -1, cut)

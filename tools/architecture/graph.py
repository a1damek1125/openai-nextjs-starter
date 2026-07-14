"""Deterministic typed graph algorithms for the architecture twin.

Nodes are strings (capability / module / route / table ids). Edges are typed.
All traversals are deterministic (sorted iteration) so the same graph always
yields the same result (SP0001 INV-0001-12). Stdlib only — no LLM is used for
any dependency-closure computation (D-0001-04 / §12.4).
"""
from __future__ import annotations

from typing import Iterable


class TypedGraph:
    def __init__(self) -> None:
        self._nodes: set[str] = set()
        # edge_type -> {src -> sorted set of dst}
        self._edges: dict[str, dict[str, set[str]]] = {}

    def add_node(self, n: str) -> None:
        self._nodes.add(n)

    def add_edge(self, edge_type: str, src: str, dst: str) -> None:
        self._nodes.add(src)
        self._nodes.add(dst)
        self._edges.setdefault(edge_type, {}).setdefault(src, set()).add(dst)

    def nodes(self) -> list[str]:
        return sorted(self._nodes)

    def edges(self, edge_type: str | None = None) -> list[tuple[str, str, str]]:
        out: list[tuple[str, str, str]] = []
        types = [edge_type] if edge_type else sorted(self._edges)
        for et in types:
            for src in sorted(self._edges.get(et, {})):
                for dst in sorted(self._edges[et][src]):
                    out.append((et, src, dst))
        return out

    def successors(self, edge_types: Iterable[str], src: str) -> list[str]:
        out: set[str] = set()
        for et in edge_types:
            out |= self._edges.get(et, {}).get(src, set())
        return sorted(out)

    # -- SCC (Tarjan, iterative, O(V+E)) -------------------------------------
    def strongly_connected_components(
            self, edge_types: Iterable[str]) -> list[list[str]]:
        edge_types = list(edge_types)
        index: dict[str, int] = {}
        low: dict[str, int] = {}
        on_stack: set[str] = set()
        stack: list[str] = []
        result: list[list[str]] = []
        counter = [0]

        def adj(v: str) -> list[str]:
            return self.successors(edge_types, v)

        # iterative Tarjan to avoid recursion limits on large synthetic graphs
        for root in self.nodes():
            if root in index:
                continue
            work: list[tuple[str, int]] = [(root, 0)]
            while work:
                v, pi = work[-1]
                if pi == 0:
                    index[v] = low[v] = counter[0]
                    counter[0] += 1
                    stack.append(v)
                    on_stack.add(v)
                recursed = False
                neigh = adj(v)
                for i in range(pi, len(neigh)):
                    w = neigh[i]
                    if w not in index:
                        work[-1] = (v, i + 1)
                        work.append((w, 0))
                        recursed = True
                        break
                    if w in on_stack:
                        low[v] = min(low[v], index[w])
                if recursed:
                    continue
                if low[v] == index[v]:
                    comp: list[str] = []
                    while True:
                        w = stack.pop()
                        on_stack.discard(w)
                        comp.append(w)
                        if w == v:
                            break
                    result.append(sorted(comp))
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[v])
        # deterministic order
        return sorted(result, key=lambda c: c[0])

    def has_cycle(self, edge_types: Iterable[str]) -> bool:
        return any(len(c) > 1 for c in
                   self.strongly_connected_components(edge_types))

    # -- reverse reachability (impact cone), O(V+E) -------------------------
    def reverse_reachable(self, edge_types: Iterable[str],
                          seeds: Iterable[str],
                          max_depth: int | None = None) -> list[str]:
        """All nodes that can reach any seed via the given edge types.

        Builds the reverse adjacency then BFS. max_depth bounds ADVISORY
        traversal only; None = full (never silently truncated, SP0001 §11.6).
        """
        edge_types = list(edge_types)
        rev: dict[str, set[str]] = {}
        for et in edge_types:
            for src, dsts in self._edges.get(et, {}).items():
                for dst in dsts:
                    rev.setdefault(dst, set()).add(src)
        seen: set[str] = set(seeds)
        frontier = sorted(seen)
        depth = 0
        while frontier:
            if max_depth is not None and depth >= max_depth:
                break
            nxt: set[str] = set()
            for node in frontier:
                for pred in rev.get(node, set()):
                    if pred not in seen:
                        seen.add(pred)
                        nxt.add(pred)
            frontier = sorted(nxt)
            depth += 1
        return sorted(seen)

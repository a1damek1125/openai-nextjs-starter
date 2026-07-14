"""Deterministic semantic relationship graph (SP0002 §11.6).

Typed edges only (no free-form). Reverse reachability powers the semantic impact
cone. Stdlib only, deterministic (sorted traversal). No LLM in any closure.
"""
from __future__ import annotations

from typing import Iterable


class SemGraph:
    def __init__(self) -> None:
        self.nodes: set[str] = set()
        self.edges: dict[str, dict[str, set[str]]] = {}   # type -> src -> {dst}

    def add(self, edge_type: str, src: str, dst: str) -> None:
        self.nodes.add(src)
        self.nodes.add(dst)
        self.edges.setdefault(edge_type, {}).setdefault(src, set()).add(dst)

    def reverse_reachable(self, edge_types: Iterable[str],
                          seeds: Iterable[str]) -> list[str]:
        rev: dict[str, set[str]] = {}
        for et in edge_types:
            for s, dsts in self.edges.get(et, {}).items():
                for d in dsts:
                    rev.setdefault(d, set()).add(s)
        seen = set(seeds)
        frontier = sorted(seen)
        while frontier:
            nxt: set[str] = set()
            for n in frontier:
                for p in rev.get(n, set()):
                    if p not in seen:
                        seen.add(p)
                        nxt.add(p)
            frontier = sorted(nxt)
        return sorted(seen)

    def forward_reachable(self, edge_types: Iterable[str],
                          seeds: Iterable[str]) -> list[str]:
        seen = set(seeds)
        frontier = sorted(seen)
        while frontier:
            nxt: set[str] = set()
            for n in frontier:
                for et in edge_types:
                    for d in self.edges.get(et, {}).get(n, set()):
                        if d not in seen:
                            seen.add(d)
                            nxt.add(d)
            frontier = sorted(nxt)
        return sorted(seen)


def build_graph(registry: dict) -> SemGraph:
    g = SemGraph()
    for c in registry.get("concepts", []):
        g.nodes.add(c["canonical_key"])
        for rel in c.get("relationships", []):
            g.add(rel["type"], c["canonical_key"], rel["target"])
    return g

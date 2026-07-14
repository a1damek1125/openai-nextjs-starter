"""Temporal Constraint Layer — first-class, SEPARATE from precedence
(SP0003 D-0003-24/25/26, §11, INV-0003 temporal).

Not every relationship is simple precedence: "B within 30 days after A",
"C not before date X", "D before deadline Y", "E and F overlap". These are
represented as difference constraints x_j - x_i <= c over timepoints, and their
consistency is decided EXACTLY by negative-cycle detection (Bellman-Ford) — never
by an LLM (D-0003-25). A CONTINGENT duration/timepoint (provider/regulatory/human
review) stays explicitly distinguishable from a controlled internal duration
(D-0003-26); SP0003 only records controllability, it does not claim dynamic
controllability it has not implemented.
"""
from __future__ import annotations

from .model import (Finding, P0, P1, TEMPORAL_TYPES,
                    TEMPORAL_CONSTRAINT_INCONSISTENCY, INVALID_PROGRAM_SCHEMA)

ZERO = "__ZERO__"   # time origin timepoint for absolute bounds


def difference_edges(program: dict) -> list[tuple[str, str, float]]:
    """Translate temporal constraints into difference-constraint edges
    (i -> j weight c meaning t_j - t_i <= c). A [lower, upper] window on
    (t_to - t_from) yields two edges."""
    edges: list[tuple[str, str, float]] = []
    for c in program.get("temporal_constraints", []):
        i = c.get("from_timepoint") or ZERO
        j = c.get("to_timepoint") or ZERO
        lo = c.get("lower_bound")
        hi = c.get("upper_bound")
        if hi is not None:
            # t_j - t_i <= hi
            edges.append((i, j, float(hi)))
        if lo is not None:
            # t_j - t_i >= lo  <=>  t_i - t_j <= -lo
            edges.append((j, i, -float(lo)))
    return edges


def timepoints(program: dict, edges) -> list[str]:
    pts = {ZERO}
    for c in program.get("temporal_constraints", []):
        pts.add(c.get("from_timepoint") or ZERO)
        pts.add(c.get("to_timepoint") or ZERO)
    for i, j, _ in edges:
        pts.add(i)
        pts.add(j)
    return sorted(pts)


def negative_cycle(nodes, edges) -> list[str] | None:
    """Bellman-Ford from a virtual source. Returns a node on a negative cycle
    (deterministic) or None if the difference system is consistent."""
    dist = {n: 0.0 for n in nodes}   # virtual source with 0-weight to all
    order = sorted(nodes)
    relaxed_node = None
    for _ in range(len(order)):
        relaxed_node = None
        for (u, v, w) in sorted(edges):
            if u in dist and dist[u] + w < dist[v] - 1e-9:
                dist[v] = dist[u] + w
                relaxed_node = v
        if relaxed_node is None:
            break
    return relaxed_node  # non-None after |V| passes => negative cycle present


def check_temporal_consistency(program: dict) -> list[Finding]:
    out: list[Finding] = []
    for c in program.get("temporal_constraints", []):
        t = c.get("constraint_type")
        if t is not None and t not in TEMPORAL_TYPES:
            out.append(Finding(INVALID_PROGRAM_SCHEMA, P1,
                               c.get("constraint_id", "-"),
                               f"invalid constraint_type {t!r}", {}))
    edges = difference_edges(program)
    pts = timepoints(program, edges)
    culprit = negative_cycle(pts, edges)
    if culprit is not None:
        out.append(Finding(TEMPORAL_CONSTRAINT_INCONSISTENCY, P0, culprit,
                           "temporal difference constraints are inconsistent "
                           "(negative cycle in the constraint graph)", {}))
    return out


def contingent_timepoints(program: dict) -> list[str]:
    """Timepoints/constraints explicitly marked contingent (externally driven)."""
    out: set[str] = set()
    for c in program.get("temporal_constraints", []):
        if c.get("constraint_type") == "CONTINGENT" or c.get("contingent"):
            out.add(c.get("to_timepoint") or c.get("constraint_id", "-"))
    return sorted(out)

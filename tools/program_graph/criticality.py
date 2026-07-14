"""Criticality engines — three DISTINCT modes, never silently substituted
(SP0003 D-0003-18, §11.6/§11.7/§11.8).

STRUCTURAL  : no durations; every node costs 1 unit; measures unavoidable
              dependency depth / serialization (§11.6).
ESTIMATED   : forward/backward CPM over explicit duration estimates → ES/EF/LS/LF
              and slack; a node is critical iff slack == 0 (§11.7). Reports ALL
              critical nodes/edges, not one fabricated unique path (§11.8).

An UNKNOWN duration never becomes a fake number (D-0003-11/§11.7): estimate-based
CPM runs only over nodes with a real numeric duration (duration.py); a node whose
duration is UNKNOWN cannot be given a phantom estimate here.
"""
from __future__ import annotations

from .graphalgo import (precedence_pairs, node_ids, topo_order, adjacency,
                        reachable_from)
from .hypergraph import default_active


def structural_depth(program: dict, active=default_active) -> dict:
    """Longest-path depth (in nodes) to each node; unit weights (§11.6)."""
    nodes = node_ids(program)
    pairs = precedence_pairs(program, active)
    order = topo_order(nodes, pairs)
    if order is None:
        return {"error": "cyclic", "depth": {}, "critical_depth": None}
    succ, pred = adjacency(nodes, pairs)
    depth = {n: 1 for n in nodes}
    for u in order:
        for v in sorted(succ[u]):
            if depth[u] + 1 > depth[v]:
                depth[v] = depth[u] + 1
    crit = max(depth.values()) if depth else 0
    critical_nodes = sorted(n for n, d in depth.items() if d == crit)
    return {"depth": depth, "critical_depth": crit,
            "deepest_nodes": critical_nodes}


def cpm(program: dict, durations: dict[str, float], active=default_active) -> dict:
    """Estimate-based CPM (§11.7/§11.8). `durations` maps node_id -> numeric
    duration; nodes absent from it are treated as 0-duration MILESTONE joins
    (never fabricated). Returns ES/EF/LS/LF/slack and the full critical set."""
    nodes = node_ids(program)
    pairs = precedence_pairs(program, active)
    order = topo_order(nodes, pairs)
    if order is None:
        return {"error": "cyclic"}
    succ, pred = adjacency(nodes, pairs)
    d = {n: float(durations.get(n, 0.0)) for n in nodes}
    ES = {n: 0.0 for n in nodes}
    EF = {n: 0.0 for n in nodes}
    for u in order:
        ES[u] = max((EF[p] for p in pred[u]), default=0.0)
        EF[u] = ES[u] + d[u]
    project = max(EF.values(), default=0.0)
    LF = {n: project for n in nodes}
    LS = {n: project for n in nodes}
    for u in reversed(order):
        LF[u] = min((LS[s] for s in succ[u]), default=project)
        LS[u] = LF[u] - d[u]
    slack = {n: round(LS[n] - ES[n], 6) for n in nodes}
    critical = sorted(n for n in nodes if abs(slack[n]) < 1e-9)
    critical_edges = sorted((u, v) for (u, v) in pairs
                            if u in critical and v in critical
                            and abs(EF[u] - ES[v]) < 1e-9)
    return {"project_duration": round(project, 6),
            "ES": {k: round(v, 6) for k, v in ES.items()},
            "EF": {k: round(v, 6) for k, v in EF.items()},
            "LS": {k: round(v, 6) for k, v in LS.items()},
            "LF": {k: round(v, 6) for k, v in LF.items()},
            "slack": slack, "critical_nodes": critical,
            "critical_edges": critical_edges,
            "num_critical_nodes": len(critical)}


def display_critical_path(cpm_result: dict, program: dict,
                          active=default_active) -> list[str]:
    """One canonical display path through the critical nodes (deterministic);
    NOT a claim that it is the unique critical path (§11.8)."""
    critical = set(cpm_result.get("critical_nodes", []))
    if not critical:
        return []
    pairs = [(u, v) for (u, v) in precedence_pairs(program, active)
             if u in critical and v in critical]
    succ: dict[str, list[str]] = {}
    preds: set[str] = set()
    for u, v in pairs:
        succ.setdefault(u, []).append(v)
        preds.add(v)
    starts = sorted(critical - preds)
    if not starts:
        return sorted(critical)
    path = [starts[0]]
    cur = starts[0]
    while succ.get(cur):
        cur = sorted(succ[cur])[0]
        path.append(cur)
    return path

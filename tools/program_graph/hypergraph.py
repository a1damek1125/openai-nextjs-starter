"""Typed AND/OR/threshold prerequisite hypergraph + readiness (SP0003 D-0003-01
..03, §11.1/§11.2).

A prerequisite hyperedge e = (T_e, h_e) is satisfied according to its own logic:

  ALL_OF          -> every tail complete                 (conjunction)
  ANY_OF          -> at least one tail complete          (disjunction)
  AT_LEAST_K_OF_N -> at least k of the tails complete    (threshold)

Multiple hyperedges sharing a head are ALTERNATIVE prerequisite paths, combined
disjunctively (D-0003-02):

    ReadyPrereq(v) = OR over incoming edges e of Satisfied(e)

so (A AND B) OR (C AND D) is two ALL_OF hyperedges {A,B}->X and {C,D}->X — a joint
prerequisite is NEVER collapsed into ambiguous independent pairwise edges
(INV-0003-03). A source node (no incoming active edge) is prerequisite-ready.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

from .model import BLOCKING_DEPENDENCY_STATES


def default_active(edge: dict) -> bool:
    """Only an ACTIVE dependency blocks/participates in canonical readiness
    (D-0003-34). Scenario compilation supplies its own predicate."""
    return edge.get("status") in BLOCKING_DEPENDENCY_STATES


def incoming(program: dict, active: Callable[[dict], bool] = default_active
             ) -> dict[str, list[dict]]:
    """Map head_node -> list of active incoming hyperedges."""
    idx: dict[str, list[dict]] = {}
    for e in program.get("hyperedges", []):
        if not active(e):
            continue
        idx.setdefault(e["head_node"], []).append(e)
    return idx


def edge_satisfied(edge: dict, complete: set[str]) -> bool:
    # DISTINCT tails only: duplicate tail_nodes must never inflate a threshold
    # (red-team SWARM-L Finding 2). A "2-of-N" gate needs 2 distinct completions.
    tails = set(edge.get("tail_nodes", []))
    if not tails:
        return False
    n_done = len(tails & complete)
    logic = edge.get("logic", "ALL_OF")
    if logic == "ALL_OF":
        return n_done == len(tails)
    if logic == "ANY_OF":
        return n_done >= 1
    if logic == "AT_LEAST_K_OF_N":
        k = edge.get("threshold_k", len(tails))
        return n_done >= k
    return False


def prerequisite_ready(program: dict, node_id: str, complete: set[str],
                       active: Callable[[dict], bool] = default_active) -> bool:
    """ReadyPrereq(v): a source node is ready; otherwise at least one incoming
    active hyperedge must be satisfied (disjunction over alternatives)."""
    edges = incoming(program, active).get(node_id, [])
    if not edges:
        return True
    return any(edge_satisfied(e, complete) for e in edges)


def ready_prereq_set(program: dict, complete: set[str],
                     active: Callable[[dict], bool] = default_active
                     ) -> set[str]:
    """All nodes whose prerequisite expression is satisfied under `complete`."""
    inc = incoming(program, active)
    out: set[str] = set()
    for n in program.get("nodes", []):
        nid = n["node_id"]
        edges = inc.get(nid, [])
        if not edges or any(edge_satisfied(e, complete) for e in edges):
            out.add(nid)
    return out


def threshold_gate_satisfied(gate: dict, complete: set[str]) -> bool:
    """Explicit THRESHOLD_GATE (D-0003-03 / §11.2): sum I(complete) >= k."""
    cands = gate.get("candidate_nodes", [])
    k = gate.get("threshold_k", len(cands))
    return sum(1 for c in cands if c in complete) >= k


def alternative_groups(program: dict,
                       active: Callable[[dict], bool] = default_active
                       ) -> list[str]:
    """Heads that have more than one active incoming hyperedge (alternatives),
    plus edges whose own logic is disjunctive/threshold."""
    inc = incoming(program, active)
    groups = [h for h, edges in inc.items() if len(edges) > 1]
    for h, edges in inc.items():
        if h in groups:
            continue
        if any(e.get("logic") in ("ANY_OF", "AT_LEAST_K_OF_N") for e in edges):
            groups.append(h)
    return sorted(groups)


def hyperedge_arity_stats(program: dict) -> dict:
    """Average / max tail arity across all hyperedges (§19 observability)."""
    edges = program.get("hyperedges", [])
    arities = [len(e.get("tail_nodes", [])) for e in edges]
    if not arities:
        return {"count": 0, "avg_arity": 0.0, "max_arity": 0, "incidences": 0}
    return {"count": len(arities),
            "avg_arity": round(sum(arities) / len(arities), 4),
            "max_arity": max(arities),
            "incidences": sum(arities)}

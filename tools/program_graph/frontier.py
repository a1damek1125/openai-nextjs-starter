"""Parallelization Frontier + advisory robust portfolio (SP0003 D-0003-27/28,
§11.16..§11.19, INV-0003-05/06).

RAW_READY_SET (prerequisite-ready) is filtered by hard gates, resource
exclusivity/capacity, temporal feasibility and explicit concurrency barriers to
yield the SAFE_PARALLEL_FRONTIER. A robust portfolio selector is ADVISORY and may
never override a hard constraint (INV-0003-05/06, D-0003-28): scheduling authority
is not granted by SP0003.
"""
from __future__ import annotations

from itertools import combinations

from .readiness import ready_nodes
from .conflict import resource_batch_ok, conflicts_with
from .graphalgo import precedence_pairs, reachable_from
from .hypergraph import default_active


def safe_ready_set(program: dict, *, complete=None, gate_state=None,
                   active=default_active) -> set[str]:
    """Gate + prerequisite ready nodes (resource conflicts applied at batch
    formation, not here)."""
    return ready_nodes(program, complete=complete, gate_state=gate_state,
                       active=active)


def safe_parallel_batches(program: dict, *, complete=None, gate_state=None,
                          active=default_active) -> list[list[str]]:
    """Greedy conflict-free batches over the ready set (deterministic). Each batch
    respects exclusive resources; nodes that mutually conflict land in different
    batches (§11.16/§11.17)."""
    ready = sorted(safe_ready_set(program, complete=complete,
                                  gate_state=gate_state, active=active))
    batches: list[list[str]] = []
    remaining = list(ready)
    while remaining:
        batch: list[str] = []
        for n in list(remaining):
            trial = set(batch) | {n}
            ok, _ = resource_batch_ok(program, trial)
            if ok and not (conflicts_with(program, n) & set(batch)):
                batch.append(n)
                remaining.remove(n)
        if not batch:               # safety: avoid infinite loop
            batch = [remaining.pop(0)]
        batches.append(sorted(batch))
    return batches


def downstream_unlock(program: dict, node_id: str, active=default_active) -> int:
    """|ReachableFutureNodes(v)| — structural leverage, NOT business value
    (§11.19)."""
    pairs = precedence_pairs(program, active)
    return len(reachable_from(pairs, [node_id]))


def portfolio_utility(program: dict, batch: set[str], weights: dict,
                      active=default_active) -> dict:
    """Advisory bounded utility (§11.18). Every term is explicitly normalized;
    incomparable raw scores are never silently summed. Returns the breakdown so
    the advisory nature is auditable."""
    a = weights.get("alpha", 1.0)
    b = weights.get("beta", 0.0)
    g = weights.get("gamma", 0.0)
    d = weights.get("delta", 0.0)
    total_nodes = max(1, len(program.get("nodes", [])))
    unlock = sum(downstream_unlock(program, n, active) for n in batch)
    unlock_norm = unlock / (total_nodes * max(1, len(batch)))
    ok, conflict_findings = resource_batch_ok(program, set(batch))
    conflict_cost = len(conflict_findings) / max(1, len(batch))
    utility = a * unlock_norm - d * conflict_cost + b * 0.0 + g * 0.0
    return {"utility": round(utility, 6), "unlock_norm": round(unlock_norm, 6),
            "conflict_cost": round(conflict_cost, 6),
            "feasible": ok, "advisory": True}

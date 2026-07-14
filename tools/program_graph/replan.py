"""Closed-Loop Program Replanning + incremental recomputation (SP0003
D-0003-38/39, §11.24, INV-0003-19).

A change event (SP completed/failed, architecture/semantic epoch changed,
technology decision changed, new dependency discovered, duration evidence
updated) triggers recomputation of the AFFECTED analyses only. Incremental
recomputation must equal FULL recompute for supported analyses (AC-0003-81); a
full-recompute reference mode is always preserved for validation. Reverse indexes
scope the invalidation.
"""
from __future__ import annotations

from .graphalgo import precedence_pairs, reachable_from, reachable_to
from .hypergraph import default_active
from .rework import rework_impact


def reverse_dependency_index(program: dict, active=default_active
                             ) -> dict[str, list[str]]:
    """node -> nodes that (transitively) depend on it (downstream closure)."""
    pairs = precedence_pairs(program, active)
    idx: dict[str, list[str]] = {}
    for n in program.get("nodes", []):
        nid = n["node_id"]
        idx[nid] = sorted(reachable_from(pairs, [nid]))
    return idx


def affected_closure(program: dict, changed: set[str], active=default_active
                     ) -> dict:
    """The set of nodes whose derived analyses must be invalidated when `changed`
    changes: downstream dependency closure ∪ rework reach (D-0003-39)."""
    pairs = precedence_pairs(program, active)
    downstream = reachable_from(pairs, sorted(changed))
    rework = rework_impact(program, set(changed))
    affected = set(changed) | downstream | rework
    return {"changed": sorted(changed),
            "downstream": sorted(downstream),
            "rework": sorted(rework),
            "affected": sorted(affected),
            "affected_count": len(affected)}


def replan_events(program: dict, event: dict) -> dict:
    """Given a change event, return which analyses to recompute (advisory)."""
    changed = set(event.get("changed_nodes", []))
    closure = affected_closure(program, changed)
    recompute = ["readiness", "critical_path", "criticality", "dominators",
                 "cut_set", "frontier"]
    return {"event_type": event.get("event_type", "UNKNOWN"),
            "affected": closure["affected"],
            "recompute": recompute if changed else [],
            "incremental_scope": closure["affected_count"]}

"""Semantic Impact Cone (SP0002 D-0002 §11.6).

Impact(S) = S ∪ ReverseReachable(S) ∪ ProjectionDependents(S) over the semantic
relationship graph. Deterministic; never uses an LLM for closure.
"""
from __future__ import annotations

from typing import Any

from .graph import build_graph

# relationship types along which a meaning change propagates to dependents
PROPAGATING = ["IS_A", "PART_OF", "SPECIALIZES", "REQUIRES", "SATISFIES",
               "PRODUCES", "PRECEDES", "SUPERSEDES", "CONTRADICTS"]


def impact_cone(registry: dict, changed: list[str]) -> dict[str, Any]:
    g = build_graph(registry)
    keys = {c["canonical_key"] for c in registry.get("concepts", [])}
    seeds = [k for k in changed if k in keys]
    unknown = sorted(set(changed) - keys)
    # dependents = concepts that reverse-reach a changed concept
    cone = set(g.reverse_reachable(PROPAGATING, seeds))
    # projection dependents: any concept whose projection_refs mention a seed
    proj_dependents = []
    by_key = {c["canonical_key"]: c for c in registry.get("concepts", [])}
    affected_projections: set[str] = set()
    for k in cone:
        c = by_key.get(k, {})
        for target, ref in c.get("projection_refs", {}).items():
            affected_projections.add(target)
    for s in seeds:
        for target in by_key.get(s, {}).get("projection_refs", {}):
            affected_projections.add(target)
    return {
        "changed": sorted(seeds),
        "unknown_concepts": unknown,
        "dependent_concepts": sorted(cone - set(seeds)),
        "full_cone": sorted(cone),
        "affected_projections": sorted(affected_projections),
        "cone_size": len(cone),
    }

"""Change Impact Cone — deterministic reverse reachability (SP0001 D-0001-08).

Impact(S) = S ∪ ReverseReachable(S) over the capability DEPENDS_ON graph.
Never uses an LLM for dependency closure (§12.4). max_depth bounds ADVISORY
output only; the safety-relevant full closure is never silently truncated.
"""
from __future__ import annotations

from typing import Any

from .graph import TypedGraph
from .model import ObservedSnapshot
from .ownership import module_owner


def capability_graph(twin: dict, observed: ObservedSnapshot) -> TypedGraph:
    caps = [{"id": c["capability_id"], "paths": c["canonical_paths"]}
            for c in twin["capabilities"]]
    shared = twin.get("shared_module_owners", {})
    g = TypedGraph()
    for c in caps:
        g.add_node(c["id"])
    for frm, to in observed.import_edges:
        fo, _ = module_owner(frm, caps, shared)
        to_o, _ = module_owner(to, caps, shared)
        if fo and to_o and fo != to_o:
            g.add_edge("DEPENDS_ON", fo, to_o)
    return g


def impact_cone(twin: dict, observed: ObservedSnapshot,
                changed: list[str], max_depth: int | None = None) -> dict[str, Any]:
    g = capability_graph(twin, observed)
    valid = {c["capability_id"] for c in twin["capabilities"]}
    seeds = [c for c in changed if c in valid]
    unknown = sorted(set(changed) - valid)
    # dependents = who reverse-reaches the seeds (i.e. who DEPENDS_ON them)
    full = g.reverse_reachable(["DEPENDS_ON"], seeds, max_depth=None)
    direct = g.reverse_reachable(["DEPENDS_ON"], seeds, max_depth=1)
    downstream = sorted(set(full) - set(seeds))
    # protected contracts potentially affected
    affected_contracts = []
    for c in twin["capabilities"]:
        if c["capability_id"] in full and c["classification"].startswith("governance"):
            affected_contracts.append(c["capability_id"])
    # candidate test domains: test anchors of every capability in the cone
    test_domains = []
    for c in twin["capabilities"]:
        if c["capability_id"] in full:
            test_domains.extend(c.get("test_anchors", []))
    return {
        "changed": sorted(seeds),
        "unknown_capabilities": unknown,
        "direct_impact": sorted(set(direct) - set(seeds)),
        "downstream_impact": downstream,
        "full_cone": sorted(full),
        "affected_governance_contracts": sorted(affected_contracts),
        "candidate_test_domains": sorted(set(test_domains)),
        "cone_size": len(full),
    }

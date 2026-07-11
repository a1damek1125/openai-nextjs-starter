"""Diff-aware architecture validation (SP0001 D-0001-05, §11.5).

Delta mode compares the DECLARED baseline recorded in the twin (base_commit =
twin.baseline_head) with the CURRENT observed tree, and classifies every
architecture-significant delta. Unexplained delta is UNDECLARED_ARCHITECTURE_DRIFT.
"""
from __future__ import annotations

from typing import Any

from .impact import capability_graph
from .model import ObservedSnapshot
from .ownership import module_owner, route_owner, table_owner


def _capability_edges(twin: dict, observed: ObservedSnapshot) -> set[tuple[str, str]]:
    g = capability_graph(twin, observed)
    return {(s, d) for _, s, d in g.edges("DEPENDS_ON")}


def architecture_delta(twin: dict, observed: ObservedSnapshot) -> dict[str, Any]:
    caps = [{"id": c["capability_id"], "paths": c["canonical_paths"]}
            for c in twin["capabilities"]]
    shared = twin.get("shared_module_owners", {})

    base_edges = {tuple(e) for e in
                  twin.get("dependency_baseline", {}).get("edges", [])}
    cur_edges = _capability_edges(twin, observed)

    base_versions = {v for v, _ in twin["migration_integrity"]["baseline_digests"]}
    base_digests = {v: h for v, h in twin["migration_integrity"]["baseline_digests"]}
    cur_digests = {v: h for v, h in observed.migration_digests}

    base_tables = set(twin.get("table_baseline", []))
    cur_tables = {t for t, _ in observed.data_ownership}
    base_routes = set(twin.get("route_baseline", []))
    cur_routes = {r[0] for r in observed.route_edges}

    # new/removed capability nodes vs declared
    declared_caps = {c["capability_id"] for c in twin["capabilities"]}
    observed_caps: set[str] = set()
    for m in observed.modules:
        o, _ = module_owner(m, caps, shared)
        if o:
            observed_caps.add(o)

    new_routes = []
    route_owner_map: dict[str, str] = {}
    for r in sorted(set(x[0] for x in observed.route_edges)):
        o, _ = route_owner(r, twin["capabilities"])
        if o:
            route_owner_map[r] = o

    # migration changes
    mutated = [{"version": v, "expected": base_digests[v],
                "observed": cur_digests.get(v)}
               for v in base_versions if cur_digests.get(v) != base_digests[v]]
    appended = sorted((v for v in cur_digests if v not in base_versions),
                      key=int)

    # effect delta
    base_effect = {(o["module"], o["kind"], o["target"])
                   for o in twin["effect_gates"]["baseline_effect_observations"]}
    cur_effect = {(o["module"], o["kind"], o["target"])
                  for o in observed.effect_observations}
    new_effects = sorted(list(cur_effect - base_effect))

    return {
        "base_commit": twin.get("baseline_head"),
        "source_commit": observed.commit,
        "new_capability_edges": sorted([list(e) for e in cur_edges - base_edges]),
        "removed_capability_edges": sorted([list(e) for e in base_edges - cur_edges]),
        "new_capabilities": sorted(observed_caps - declared_caps),
        "removed_capabilities": sorted(declared_caps - observed_caps),
        "migration_mutations": mutated,
        "appended_migrations": appended,
        "new_effect_observations": [list(e) for e in new_effects],
        "route_owner": route_owner_map,
        "new_routes": sorted(cur_routes - base_routes),
        "removed_routes": sorted(base_routes - cur_routes),
        "new_tables": sorted(cur_tables - base_tables),
        "removed_tables": sorted(base_tables - cur_tables),
    }

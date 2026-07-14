"""Technology Survivability Analysis + Decision Impact Cone (SP0004 D-0004-58/59/
74, §11.15, INV-0004-13).

Survivability keeps its dimensions SEPARATE — not one magic score (D-0004-59):
replacement availability, state/data portability, operational independence,
failure-domain diversity, protocol openness, team knowledge. The impact cone
combines references from the Architecture (SP0001), Semantic (SP0002) and Program
(SP0003) graphs plus the Technology graph to find everything a technology change
touches (§11.15).
"""
from __future__ import annotations

from .depgraph import upstream_closure

SURVIVABILITY_DIMS = ("replacement_availability", "state_portability",
                      "data_portability", "operational_independence",
                      "failure_domain_diversity", "protocol_openness",
                      "team_knowledge")

SURVIVABILITY_SCENARIOS = ("provider_unavailable", "provider_price_shock",
                           "provider_security_incident", "protocol_deprecation",
                           "license_change", "maintainer_collapse",
                           "region_restriction", "replacement_unavailable")


def survivability_profile(tech: dict) -> dict:
    """Per-dimension survivability; missing dims are UNKNOWN (never averaged into
    a single deceptive score)."""
    s = tech.get("survivability", {})
    dims = {d: s.get(d, "UNKNOWN") for d in SURVIVABILITY_DIMS}
    scenarios = {sc: tech.get("survivability_scenarios", {}).get(sc, "UNKNOWN")
                 for sc in SURVIVABILITY_SCENARIOS}
    return {"technology_id": tech.get("technology_id"), "dimensions": dims,
            "scenarios": scenarios}


def impact_cone(tech_graph: dict, decision: dict, *,
                arch_refs=None, semantic_refs=None, program_refs=None) -> dict:
    """Everything affected by changing a technology decision (§11.15,
    D-0004-74). Technology-graph downstream = nodes whose upstream closure
    contains the changed technologies; cross-graph refs are declared on the
    decision so the cone spans architecture / semantics / program."""
    changed = set(decision.get("affected_technologies", []))
    downstream = []
    for n in tech_graph.get("nodes", []):
        nid = n["node_id"]
        if nid in changed:
            continue
        if upstream_closure(tech_graph, nid) & changed:
            downstream.append(nid)
    return {
        "changed_technologies": sorted(changed),
        "technology_downstream": sorted(downstream),
        "affected_architecture": sorted(decision.get("affected_architecture",
                                                     arch_refs or [])),
        "affected_semantics": sorted(decision.get("affected_semantics",
                                                 semantic_refs or [])),
        "affected_program": sorted(decision.get("affected_program",
                                              program_refs or [])),
        "affected_contracts": sorted(decision.get("affected_contracts", [])),
        "cone_size": len(changed) + len(downstream),
    }

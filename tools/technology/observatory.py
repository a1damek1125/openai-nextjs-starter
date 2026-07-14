"""Technology Fitness Observatory (SP0004 D-0004-47, §19).

Deterministic longitudinal snapshot: decision age, stale/invalidated decisions,
exit readiness, substitution drill age, provider concentration, protocol age,
provider-specific leakage, common-mode dependencies, portability gaps. Advisory
metrics never become automatic hard blockers (INV-0004-22).
"""
from __future__ import annotations

from .inventory import inventory_stats, provider_leakage, critical
from .depgraph import graph_stats
from .exit_readiness import profile_for


def snapshot(program: dict, *, today: str = "2026-07-11") -> dict:
    inv = program.get("inventory", {})
    reg = program.get("decision_registry", {})
    decisions = reg.get("decisions", [])
    exit_profiles = program.get("exit_profiles", [])
    crit = critical(inv)
    exit_gaps = [t["technology_id"] for t in crit
                 if profile_for(exit_profiles, t["technology_id"]) is None]
    return {
        "classification": "ADVISORY_NOT_A_GATE",
        **inventory_stats(inv),
        "graph": graph_stats(program.get("dependency_graph", {})),
        "decisions_total": len(decisions),
        "decisions_active": sum(1 for d in decisions
                                if d.get("status") == "ACTIVE"),
        "decisions_deferred": sum(1 for d in decisions
                                  if d.get("status") == "DEFERRED"),
        "decisions_review_due": sum(1 for d in decisions
                                    if d.get("status") == "REVIEW_DUE"),
        "decisions_invalidated": sum(1 for d in decisions
                                     if d.get("status") == "INVALIDATED"),
        "provider_contracts": len(program.get("contracts", {}).get(
            "contracts", [])),
        "provider_specific_leakage": len(provider_leakage(inv)),
        "critical_dependencies": len(crit),
        "exit_readiness_gaps": sorted(exit_gaps),
        "protocols": len(program.get("protocols", {}).get("protocols", [])),
        "fitness_functions": len(program.get("fitness_defs", [])),
        "golden_workloads": len(program.get("golden_corpus", [])),
        "substitution_evidence": len(program.get("substitution_evidence", [])),
    }

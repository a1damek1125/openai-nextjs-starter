"""Program Drift Observatory (SP0003 D-0003-42, INV-0003-12/§19).

A deterministic longitudinal snapshot vector. Uncalibrated drift metrics are
ADVISORY and must never become automatic hard blockers (D-0003-42, AC-0003-87).
"""
from __future__ import annotations

from .hypergraph import hyperedge_arity_stats, alternative_groups
from .rework import feedback_clusters, rework_pairs
from .evidence import evidence_coverage
from .criticality import structural_depth
from .scenario import compile_scenario


def snapshot_vector(program: dict, scenario_id: str = "BASELINE") -> dict:
    active, _ = compile_scenario(program, scenario_id)
    arity = hyperedge_arity_stats(program)
    depth = structural_depth(program, active)
    unknown_deps = sum(1 for e in program.get("hyperedges", [])
                       if e.get("status") == "UNDER_RESEARCH")
    return {
        "classification": "ADVISORY_NOT_A_GATE",
        "node_count": len(program.get("nodes", [])),
        "hard_dependency_count": sum(
            1 for e in program.get("hyperedges", [])
            if e.get("status") == "ACTIVE"),
        "avg_hyperedge_arity": arity["avg_arity"],
        "max_hyperedge_arity": arity["max_arity"],
        "conditional_dependency_count": sum(
            1 for e in program.get("hyperedges", [])
            if e.get("scenario_condition")),
        "unknown_dependency_count": unknown_deps,
        "alternative_prerequisite_groups": len(alternative_groups(program, active)),
        "resource_conflict_count": len(program.get("conflicts", [])),
        "rework_edge_count": len(rework_pairs(program)),
        "feedback_scc_count": len(feedback_clusters(program)),
        "critical_path_depth": depth.get("critical_depth"),
        "completion_evidence_coverage": evidence_coverage(program)["coverage"],
        "dependency_uncertainty_count": len(program.get("uncertainties", [])),
    }

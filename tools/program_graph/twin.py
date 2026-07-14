"""Program Digital Twin (SP0003 D-0003-41, INV-0003-15/16/17).

A repository-grounded twin of the DEVELOPMENT program: canonical structure,
completion evidence, active scenario, gate state, current derived analyses and
model provenance. It is DISTINCT from the Architecture Digital Twin (SP0001) and
the Semantic Domain Twin (SP0002), and it is for development-program planning
only — never reused as runtime business state (§8). Canonical truth and derived
analytics are kept separate (INV-0003-17): derived results carry their input
hashes.
"""
from __future__ import annotations

from .canon import core_hash
from .registry import registry_hash
from .evidence import evidence_coverage, evidence_derived_complete_set
from .hypergraph import hyperedge_arity_stats, alternative_groups
from .rework import feedback_clusters
from .scenario import compile_scenario

TWIN_KIND = "PROGRAM_DIGITAL_TWIN"
DISTINCT_FROM = ["ARCHITECTURE_DIGITAL_TWIN", "SEMANTIC_DOMAIN_TWIN",
                 "OPERATIONAL_WORLD_STATE"]


def build_twin(program: dict, scenario_id: str = "BASELINE") -> dict:
    active, _ = compile_scenario(program, scenario_id)
    complete = sorted(evidence_derived_complete_set(program))
    arity = hyperedge_arity_stats(program)
    return {
        "twin_kind": TWIN_KIND,
        "distinct_from": DISTINCT_FROM,
        "active_scenario": scenario_id,
        "node_count": len(program.get("nodes", [])),
        "hyperedge_count": len(program.get("hyperedges", [])),
        "avg_hyperedge_arity": arity["avg_arity"],
        "alternative_prerequisite_groups": alternative_groups(program, active),
        "threshold_gates": len(program.get("threshold_gates", [])),
        "conditional_dependencies": sum(
            1 for e in program.get("hyperedges", [])
            if e.get("scenario_condition")),
        "hard_gates": len(program.get("gates", [])),
        "resource_conflicts": len(program.get("conflicts", [])),
        "rework_edges": len(program.get("rework_edges", [])),
        "rework_feedback_clusters": feedback_clusters(program),
        "temporal_constraints": len(program.get("temporal_constraints", [])),
        "dependency_uncertainties": len(program.get("uncertainties", [])),
        "completion_evidence_coverage": evidence_coverage(program),
        "complete_nodes": complete,
        "canonical_registry_hash": registry_hash(program),
        # canonical vs derived kept separate: this is a structural snapshot only
        "classification": "CANONICAL_STRUCTURE_SNAPSHOT",
    }

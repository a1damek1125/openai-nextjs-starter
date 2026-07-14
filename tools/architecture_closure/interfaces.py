"""Constitutional interfaces for SP0000-SP0009 (SP0010 FUNCTION C, §10.1,
D-0010-06, AC-0010-031..040).

For each constitution this records what it OWNS, what it ASSUMES from
predecessors, what it GUARANTEES to successors, its hard INVARIANTS, its FAILURE
states, and the REAL repository EVIDENCE (tools/ package + docs/ artifacts) that
grounds those guarantees. Assumptions reference predecessor guarantee claims by
id, so the interfaces compose into the assurance hypergraph (interfaces.py ->
hypergraph.py). A missing assumption never defaults to satisfied (D-0010-06):
an assumption with no matching predecessor guarantee is a dangling premise.

The evidence refs point at paths whose EXISTENCE is verified on disk, so a
guarantee cannot claim support from an artifact that is not there.
"""
from __future__ import annotations

from pathlib import Path

from .canon import core_hash, hash_obj
from .model import Finding, P0, P1

# Each guarantee/assumption is a claim id "CL-<SP>-<slug>".
# assumptions reference a predecessor guarantee claim id (its dependency).
CONSTITUTIONS = {
    "SP0000": {
        "title": "Architecture Lock",
        "commit": "e1b6b5c",
        "owned_concepts": ["entity_of_interest", "architecture_baseline",
                           "capability_map"],
        "guarantees": ["CL-SP0000-architecture-baseline-fixed"],
        "assumptions": [],
        "invariants": ["repository_truth_authoritative"],
        "failure_states": ["ARCHITECTURE_DRIFT"],
        "evidence": ["docs/roadmap/ROADMAP_LOCK_1_FINALIS_AI_EMPLOYEE_OS.md",
                     "docs/architecture"],
    },
    "SP0001": {
        "title": "Architecture Immune System",
        "commit": "19413f2",
        "owned_concepts": ["architecture_conformance", "drift_detection"],
        "guarantees": ["CL-SP0001-architecture-conformance-checked"],
        "assumptions": ["CL-SP0000-architecture-baseline-fixed"],
        "invariants": ["architecture_and_description_distinct"],
        "failure_states": ["CONFORMANCE_VIOLATION"],
        "evidence": ["tools/architecture", "docs/architecture"],
    },
    "SP0002": {
        "title": "Semantic Operating Constitution",
        "commit": "3eacdb0",
        "owned_concepts": ["semantic_epoch", "canonical_identity",
                           "control_language"],
        "guarantees": ["CL-SP0002-semantics-versioned",
                       "CL-SP0002-historical-epoch-interpretable"],
        "assumptions": ["CL-SP0000-architecture-baseline-fixed"],
        "invariants": ["semantic_changes_versioned",
                       "historical_interpretability"],
        "failure_states": ["SEMANTIC_EPOCH_BREAK"],
        "evidence": ["tools/semantics", "docs/semantics"],
    },
    "SP0003": {
        "title": "Program Dependency & Uncertainty Constitution",
        "commit": "1ffb4e4",
        "owned_concepts": ["program_digital_twin", "dependency_admission",
                           "uncertainty"],
        "guarantees": ["CL-SP0003-program-admission-verified"],
        "assumptions": ["CL-SP0000-architecture-baseline-fixed"],
        "invariants": ["no_parallel_authority"],
        "failure_states": ["PROGRAM_DEPENDENCY_BLOCKED"],
        "evidence": ["tools/program_graph",
                     "docs/program/FINALIS_1000_PROGRAM_REGISTRY.json"],
    },
    "SP0004": {
        "title": "Technology Sovereignty Constitution",
        "commit": "e82ca87",
        "owned_concepts": ["technology_registry", "provider_replaceability"],
        "guarantees": ["CL-SP0004-provider-replaceable"],
        "assumptions": ["CL-SP0000-architecture-baseline-fixed"],
        "invariants": ["provider_replaceability_executable"],
        "failure_states": ["TECHNOLOGY_LOCK_IN"],
        "evidence": ["tools/technology", "docs/technology"],
    },
    "SP0005": {
        "title": "Safety Kernel, Assurance & Regulatory Truth",
        "commit": "610e1e3",
        "owned_concepts": ["safety_admission", "safety_control",
                           "safety_dominator"],
        "guarantees": ["CL-SP0005-safety-dominates-protected-effects"],
        "assumptions": ["CL-SP0002-semantics-versioned",
                        "CL-SP0000-architecture-baseline-fixed"],
        "invariants": ["safety_dominator", "control_effectiveness_required"],
        "failure_states": ["SAFETY_ADMISSION_BYPASSED"],
        "evidence": ["tools/safety", "docs/safety"],
    },
    "SP0006": {
        "title": "Governed Work, Delegated Autonomy & Outcome Accountability",
        "commit": "d6ac046",
        "owned_concepts": ["owned_work", "approval_binding",
                           "delegation_attenuation", "outcome_evidence"],
        "guarantees": ["CL-SP0006-authority-conserved",
                       "CL-SP0006-zero-lost-work",
                       "CL-SP0006-approval-context-bound"],
        "assumptions": ["CL-SP0005-safety-dominates-protected-effects"],
        "invariants": ["authority_conservation", "delegation_attenuation",
                       "approval_context_bound", "zero_lost_work",
                       "outcome_evidence_required"],
        "failure_states": ["AUTHORITY_AMPLIFICATION", "ORPHANED_WORK"],
        "evidence": ["tools/governed_work", "docs/governed_work"],
    },
    "SP0007": {
        "title": "Compatibility, Migration & Contract Evolution",
        "commit": "4eda536",
        "owned_concepts": ["compatibility_twin", "migration_directionality",
                           "contract_version"],
        "guarantees": ["CL-SP0007-contract-evolution-directional",
                       "CL-SP0007-historical-envelope-epoch-bound"],
        "assumptions": ["CL-SP0002-historical-epoch-interpretable"],
        "invariants": ["contract_evolution_directional",
                       "up_migration_not_rollback"],
        "failure_states": ["INCOMPATIBLE_CONTRACT_ADMITTED"],
        "evidence": ["tools/compatibility", "docs/compatibility"],
    },
    "SP0008": {
        "title": "Contract Inventory & Contract Genome",
        "commit": "bb80912",
        "owned_concepts": ["contract_surface", "contract_genome",
                           "effect_reachability"],
        "guarantees": ["CL-SP0008-contract-surfaces-inventoried",
                       "CL-SP0008-contract-genome-sealed"],
        "assumptions": ["CL-SP0007-contract-evolution-directional"],
        "invariants": ["inventory_populates_registry_no_parallel"],
        "failure_states": ["HIDDEN_CONTRACT_SURFACE"],
        "evidence": ["tools/contracts_inventory",
                     "docs/contracts_inventory/FINALIS_CONTRACT_GENOME.json"],
    },
    "SP0009": {
        "title": "Release Assurance, Quality Gates & Definition of Done",
        "commit": "1e29581",
        "owned_concepts": ["release_candidate", "quality_gate",
                           "definition_of_done", "release_proof"],
        "guarantees": ["CL-SP0009-release-proof-not-runtime-authority",
                       "CL-SP0009-non-compensatory-gates"],
        "assumptions": ["CL-SP0008-contract-genome-sealed",
                        "CL-SP0006-approval-context-bound"],
        "invariants": ["proof_not_authority",
                       "release_runtime_separation",
                       "non_compensatory_gates"],
        "failure_states": ["RELEASE_PROOF_GRANTS_AUTHORITY"],
        "evidence": ["tools/release", "docs/release/FINALIS_RELEASE_TWIN.json"],
    },
}


def build_interfaces(root: Path) -> dict:
    """Materialize the constitutional interface registry with grounded evidence
    (each evidence ref's on-disk existence is recorded)."""
    out = {}
    for sp, spec in sorted(CONSTITUTIONS.items()):
        ev = []
        for rel in spec["evidence"]:
            ev.append({"ref": rel, "present": (root / rel).exists()})
        iface = {
            "constitution_id": sp,
            "version": spec["commit"],
            "commit": spec["commit"],
            "owned_concepts": spec["owned_concepts"],
            "assumption_refs": spec["assumptions"],
            "guarantee_refs": spec["guarantees"],
            "invariant_refs": spec["invariants"],
            "failure_states": spec["failure_states"],
            "evidence_refs": ev,
            "valid_from": spec["commit"],
            "valid_to": None,
        }
        iface["interface_hash"] = core_hash(iface)
        out[sp] = iface
    return out


def all_guarantee_claims(interfaces: dict) -> set:
    return {g for iface in interfaces.values()
            for g in iface["guarantee_refs"]}


def interface_findings(interfaces: dict) -> list[Finding]:
    """Every assumption must reference a real predecessor guarantee, and every
    guarantee must have at least one present evidence ref (D-0010-06)."""
    out: list[Finding] = []
    provided = all_guarantee_claims(interfaces)
    for sp, iface in sorted(interfaces.items()):
        for a in iface["assumption_refs"]:
            if a not in provided:
                out.append(Finding(
                    "CONSTITUTION_INTERFACE_INVALID", P0, sp,
                    f"assumption {a!r} references no predecessor guarantee: a "
                    "missing assumption is never satisfied (D-0010-06)",
                    {"assumption": a}))
        if not any(e["present"] for e in iface["evidence_refs"]):
            out.append(Finding(
                "CONSTITUTION_INTERFACE_INVALID", P1, sp,
                "no present evidence ref grounds this constitution's "
                "guarantees", {"evidence": iface["evidence_refs"]}))
    return out


def interfaces_root(interfaces: dict) -> str:
    return hash_obj({sp: iface["interface_hash"]
                     for sp, iface in sorted(interfaces.items())})

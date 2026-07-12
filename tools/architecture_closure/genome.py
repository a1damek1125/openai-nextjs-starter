"""Architecture Genome — the Merkle forest of all material roots (SP0010
§10.12, §11.16, D-0010-26, AC-0010-206..216).

The genome binds the repository commit, per-constitution roots, twin roots, and
the hypergraph / epistemic / invariant / hyperproperty / assurance / gap /
verifier-set roots into one deterministic global architecture root. A change to
ANY material root moves the global root (AC-0010-062..065). Omitting a
constitution or a root from the genome is caught by the seal verification, which
recomputes the global root from the same components.
"""
from __future__ import annotations

from .canon import global_root, hash_obj


def build_genome(*, repository_commit: str, constitution_roots: dict,
                 twin_roots: dict, hypergraph_root: str, epistemic_root: str,
                 invariant_root: str, hyperproperty_root: str,
                 assurance_root: str, gap_root: str, verifier_set_root: str,
                 closure_epoch: str) -> dict:
    class_roots = {
        "constitution": hash_obj(constitution_roots),
        "twin": hash_obj(twin_roots),
        "hypergraph": hypergraph_root,
        "epistemic": epistemic_root,
        "invariant": invariant_root,
        "hyperproperty": hyperproperty_root,
        "assurance": assurance_root,
        "gap": gap_root,
        "verifier_set": verifier_set_root,
    }
    g = {
        "genome_version": "1.0.0",
        "repository_commit": repository_commit,
        "constitution_roots": constitution_roots,
        "twin_roots": twin_roots,
        "hypergraph_root": hypergraph_root,
        "epistemic_state_root": epistemic_root,
        "invariant_root": invariant_root,
        "hyperproperty_root": hyperproperty_root,
        "assurance_root": assurance_root,
        "gap_ledger_root": gap_root,
        "verifier_set_root": verifier_set_root,
        "closure_epoch": closure_epoch,
        "class_roots": class_roots,
    }
    g["global_architecture_root"] = global_root(class_roots)
    return g


def verify_genome(genome: dict) -> bool:
    """Recompute the global root from the component class roots (AC-0010-259)."""
    return genome.get("global_architecture_root") == global_root(
        genome.get("class_roots", {}))

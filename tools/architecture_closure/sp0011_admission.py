"""SP0011 admission package (SP0010 FUNCTION S, §26, D-0010-45,
AC-0010-220, 230).

SP0010 produces admission EVIDENCE for SP0011 but NO score (D-0010-45). The
package hands SP0011 the Program Seal, Architecture Genome, top-level claims,
global invariants, assumptions, evidence provenance, contradictions, critical
unknowns, production gaps, evaluation gaps, formal bounds and known
noninterference limits. SP0011 may EVALUATE these; it may not rewrite them to
obtain a higher score, and no evaluation evidence may be fabricated here (the
admission state is ADMITTED_PENDING_EXECUTION, never a score).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0

ADMISSION_STATE = "ADMITTED_PENDING_EXECUTION"


def build_package(*, program_seal: dict, genome: dict, top_level_claims: list,
                  global_invariants: dict, assumptions: list,
                  evidence_provenance_root: str, contradictions: list,
                  critical_unknowns: list, production_gaps: list,
                  formal_bounds: dict, noninterference_limits: dict) -> dict:
    pkg = {
        "admission_state": ADMISSION_STATE,
        "program_seal_hash": program_seal.get("seal_hash"),
        "architecture_genome_root": genome.get("global_architecture_root"),
        "top_level_claims": sorted(top_level_claims),
        "global_invariants": {k: v.get("status")
                              for k, v in sorted(global_invariants.items())},
        "assumptions": sorted(assumptions),
        "evidence_provenance_root": evidence_provenance_root,
        "contradictions": list(contradictions),
        "critical_unknowns": list(critical_unknowns),
        "production_gaps": list(production_gaps),
        "formal_bounds": formal_bounds,
        "noninterference_limits": noninterference_limits,
        "score": None,          # SP0010 assigns NO score (D-0010-45)
        "evaluation_evidence": None,   # never fabricated
    }
    pkg["package_hash"] = hash_obj(pkg)
    return pkg


def validate_package(pkg: dict) -> list[Finding]:
    out: list[Finding] = []
    if pkg.get("admission_state") != ADMISSION_STATE:
        out.append(Finding(
            "SP0011_EVIDENCE_FABRICATION_REJECTED", P0, "sp0011",
            f"admission state must be {ADMISSION_STATE}", {}))
    if pkg.get("score") is not None:
        out.append(Finding(
            "SP0011_EVIDENCE_FABRICATION_REJECTED", P0, "sp0011",
            "SP0010 must assign no Finalis 1000 score (D-0010-45)", {}))
    if pkg.get("evaluation_evidence") is not None:
        out.append(Finding(
            "SP0011_EVIDENCE_FABRICATION_REJECTED", P0, "sp0011",
            "evaluation evidence cannot exist before SP0011 runs — "
            "fabrication rejected", {}))
    return out

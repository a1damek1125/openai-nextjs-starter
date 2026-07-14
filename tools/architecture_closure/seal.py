"""The Program Seal (SP0010 §10.13, §11.16, §12.11, FUNCTION R, D-0010-26/27,
AC-0010-217..219).

The seal identifies ONE verified snapshot: it binds the repository commit,
branch, migration frontier, the Architecture Genome root, the predecessor twin
roots, the closure state, and the counts that gate closure (critical BOTH /
NEITHER, constitutional blockers, production gaps). It creates NO production
authority (INV-0010-60, D-0010-28). A material root change invalidates it
(D-0010-27); historical seals are immutable and superseded, never overwritten
(D-0010-26). CONSTITUTIONAL_ARCHITECTURE_CLOSED requires zero critical BOTH,
zero critical NEITHER, and zero constitutional blockers.
"""
from __future__ import annotations

from .canon import core_hash

CLOSED = "CONSTITUTIONAL_ARCHITECTURE_CLOSED"
CLOSED_WITH_GAPS = "CONSTITUTIONAL_ARCHITECTURE_CLOSED_WITH_NONBLOCKING_" \
    "PRODUCTION_GAPS"
BLOCKED = "BLOCKED"


def closure_state(*, critical_both: int, critical_neither: int,
                  constitutional_blockers: int, production_gaps: int,
                  hard_finding_count: int = 0) -> str:
    # Fail-closed on the FULL hard finding set (red-team P0-1): the seal is
    # BLOCKED if ANY P0/P1 finding exists, not merely the four hand-picked
    # counters. Many P0 kinds (FROZEN_VERIFIER_MODIFIED, verifier disagreement,
    # GLOBAL_INVARIANT_GAP, provider-account leak, SP0011 fabrication) are not
    # 'constitutional blockers' in the gap taxonomy yet must still block.
    if (critical_both or critical_neither or constitutional_blockers
            or hard_finding_count):
        return BLOCKED
    return CLOSED_WITH_GAPS if production_gaps else CLOSED


def program_seal(*, repository_commit: str, branch: str,
                 migration_frontier: int, genome_root: str,
                 twin_roots: dict, release_assurance_root: str,
                 test_evidence_root: str, verifier_results: list,
                 critical_both: int, critical_neither: int,
                 constitutional_blockers: int, production_gap_count: int,
                 sp0011_admission_state: str, sealed_at: str,
                 hard_finding_count: int = 0) -> dict:
    state = closure_state(critical_both=critical_both,
                          critical_neither=critical_neither,
                          constitutional_blockers=constitutional_blockers,
                          production_gaps=production_gap_count,
                          hard_finding_count=hard_finding_count)
    seal = {
        "seal_version": "1.0.0",
        "repository_commit": repository_commit,
        "branch": branch,
        "migration_frontier": migration_frontier,
        "architecture_genome_root": genome_root,
        "twin_roots": twin_roots,
        "release_assurance_root": release_assurance_root,
        "test_evidence_root": test_evidence_root,
        "verifier_results": verifier_results,
        "closure_state": state,
        "critical_both_count": critical_both,
        "critical_neither_count": critical_neither,
        "constitutional_blockers": constitutional_blockers,
        "hard_finding_count": hard_finding_count,
        "production_gap_count": production_gap_count,
        "sp0011_admission_state": sp0011_admission_state,
        "sealed_at": sealed_at,
        "grants_production_authority": False,   # never (D-0010-28)
        "status": "CANDIDATE",
    }
    seal["seal_hash"] = core_hash(seal)
    return seal


def verify_seal(seal: dict, *, expected_commit: str) -> list:
    """A seal must bind the exact repository commit and re-hash consistently
    (AC-0010-218/259). Returns a list of problem strings (empty = valid)."""
    problems = []
    if seal.get("repository_commit") != expected_commit:
        problems.append("seal repository_commit does not match the current "
                        "snapshot")
    recomputed = core_hash({k: seal[k] for k in seal if k != "seal_hash"})
    if seal.get("seal_hash") != recomputed:
        problems.append("seal hash does not match its content")
    if seal.get("grants_production_authority") is not False:
        problems.append("seal must not grant production authority")
    if seal.get("closure_state") == BLOCKED:
        problems.append("closure state is BLOCKED")
    return problems

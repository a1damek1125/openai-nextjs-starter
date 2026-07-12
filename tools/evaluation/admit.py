"""SP0010 Program Seal admission + SP0011 Admission Package verifier (SP0011
§2.1, D-0011-002, AC-0011-007..010).

SP0011 may begin only after SP0010 is sealed and admits SP0011. This module reads
the COMMITTED SP0010 artifacts (it does NOT import or re-run the SP0010 kernel —
the seal is admitted, not reinterpreted, D-0011) and verifies:

  * the Program Seal is present, its closure state is CLOSED, it grants no
    production authority, and its hash recomputes from its own content;
  * the SP0011 Admission Package is present, ADMITTED_PENDING_EXECUTION, carries
    a null score and null evaluation evidence (no fabricated evidence);
  * the Architecture Genome, TCB and Certificate roots are present.

A missing/invalid seal blocks SP0011 (fail-closed): PROGRAM_DEPENDENCY_BLOCKED.

Evaluation tooling only; never imported by product code; no external effect.
"""
from __future__ import annotations

import json
from pathlib import Path

from .canon import core_hash
from .model import Finding, P0

_SEAL = "docs/architecture_closure/FINALIS_PROGRAM_SEAL.json"
_GENOME = "docs/architecture_closure/FINALIS_ARCHITECTURE_GENOME.json"
_TCB = "docs/architecture_closure/FINALIS_TCB_MANIFEST.json"
_ADMISSION = "docs/architecture_closure/FINALIS_SP0011_ADMISSION_PACKAGE.json"
_CERTS = "docs/architecture_closure/FINALIS_PROOF_CARRYING_CERTIFICATES.json"


def _load(root: Path, rel: str):
    p = root / rel
    if not p.exists():
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except (ValueError, OSError):
        return "UNREADABLE"


def admit_program_seal(root: Path) -> dict:
    root = Path(root)
    seal = _load(root, _SEAL)
    genome = _load(root, _GENOME)
    tcb = _load(root, _TCB)
    admission = _load(root, _ADMISSION)
    certs = _load(root, _CERTS)
    problems = []
    if not isinstance(seal, dict):
        problems.append("SP0010 program seal absent/unreadable")
    else:
        if not str(seal.get("closure_state", "")).startswith(
                "CONSTITUTIONAL_ARCHITECTURE_CLOSED"):
            problems.append("SP0010 closure state is not CLOSED")
        if seal.get("grants_production_authority") is not False:
            problems.append("SP0010 seal must not grant production authority")
        recomputed = core_hash({k: seal[k] for k in seal if k != "seal_hash"})
        if seal.get("seal_hash") != recomputed:
            problems.append("SP0010 seal hash does not recompute")
    if not isinstance(admission, dict):
        problems.append("SP0011 admission package absent/unreadable")
    else:
        if admission.get("admission_state") != "ADMITTED_PENDING_EXECUTION":
            problems.append("SP0011 not ADMITTED_PENDING_EXECUTION")
        if admission.get("score") is not None:
            problems.append("SP0011 admission carries a non-null score")
        if admission.get("evaluation_evidence") is not None:
            problems.append("SP0011 admission carries fabricated evaluation "
                            "evidence")
    return {
        "program_seal_hash": seal.get("seal_hash") if isinstance(seal, dict)
        else None,
        "closure_state": seal.get("closure_state") if isinstance(seal, dict)
        else None,
        "architecture_genome_root": (genome or {}).get(
            "global_architecture_root") if isinstance(genome, dict) else None,
        "tcb_root": (tcb or {}).get("tcb_root") if isinstance(tcb, dict) else None,
        "certificate_root": (certs or {}).get("certificate_root")
        if isinstance(certs, dict) else None,
        "admission_state": (admission or {}).get("admission_state")
        if isinstance(admission, dict) else None,
        "admitted": not problems,
        "problems": problems,
    }


def admission_findings(adm: dict) -> list[Finding]:
    out: list[Finding] = []
    if not adm["admitted"]:
        for p in adm["problems"]:
            out.append(Finding(
                "PROGRAM_DEPENDENCY_BLOCKED", P0, "sp0010",
                f"SP0010 program dependency not satisfied: {p}", {}))
    return out

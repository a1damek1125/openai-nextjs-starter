"""The minimal Trusted Evaluation Kernel (SP0011 §2.1.B, §11.3, D-0011-005/006,
AC-0011-024..029).

The kernel is the small, trusted checker set the whole score depends on. It does
NOT generate scenarios, run agents, or judge — it CHECKS certificates produced by
the untrusted stack (D-0011-006). It is deterministic (same inputs → same
verdict) and its identity is content-hashed (kernel substitution is detectable).
The kernel checks, per awarded credit: schema, configuration root, Program Seal,
maturity, hard gates, statistical scope, freshness, and the certificate hash;
then it checks score arithmetic, the genome recomputation, and the seal.
"""
from __future__ import annotations

from pathlib import Path

from .canon import hash_obj, sha256_hex
from .model import Finding, P0
from . import credits as credits_mod, score as score_mod, genome as genome_mod

KERNEL_VERSION = "sp0011-tek-1.0"
# the checker modules whose bytes define the kernel identity
KERNEL_FILES = ("kernel.py", "credits.py", "score.py", "genome.py",
                "hardgates.py", "canon.py", "model.py")


def kernel_identity(root: Path) -> dict:
    root = Path(root)
    parts = {}
    for rel in KERNEL_FILES:
        p = root / "tools" / "evaluation" / rel
        parts[rel] = (sha256_hex(p.read_text(encoding="utf-8", errors="replace"))
                      if p.exists() else "MISSING")
    return {"kernel_version": KERNEL_VERSION, "files": parts,
            "kernel_root": hash_obj(parts)}


def check_credits(certificates: list, *, configuration_root: str,
                  program_seal: str) -> dict:
    """Independently check every credit certificate; return the awards map and the
    checked verdicts. This is the ONLY path that awards credits."""
    awards, checked = {}, []
    for cert in certificates:
        v = credits_mod.check_certificate(
            cert, expected_configuration_root=configuration_root,
            expected_program_seal=program_seal)
        awards[cert["claim_id"]] = {"awarded": v["awarded"],
                                    "credits": v["credits"]}
        checked.append(v)
    return {"awards": awards, "checked": checked,
            "awarded_count": sum(1 for a in awards.values() if a["awarded"])}


def verify_all(*, certificates: list, configuration_root: str,
               program_seal: str, scorecard: dict, awards: dict,
               genome: dict, seal: dict, expected_commit: str) -> dict:
    """Full trusted verification: credits + score arithmetic + genome + seal."""
    findings: list[Finding] = []
    findings.extend(credits_mod.credit_findings(
        [credits_mod.check_certificate(
            c, expected_configuration_root=configuration_root,
            expected_program_seal=program_seal) or {} for c in certificates]))
    findings.extend(score_mod.verify_score_arithmetic(scorecard, awards))
    if not genome_mod.verify_genome(genome):
        findings.append(Finding("EVALUATION_GENOME_MISMATCH", P0, "genome",
                               "evaluation genome root does not recompute", {}))
    for p in genome_mod.verify_seal(seal, expected_commit=expected_commit):
        findings.append(Finding("EVALUATION_SEAL_MISMATCH", P0, "seal", p, {}))
    return {"findings": findings, "valid": not any(
        f.severity in (P0, "P1") for f in findings)}

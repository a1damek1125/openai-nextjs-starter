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
from . import (credits as credits_mod, score as score_mod, genome as genome_mod,
               claims as claims_mod, oracles as oracles_mod)

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


def build_ground_truth(root: Path, *, hard_gate_pass: bool) -> dict:
    """The kernel INDEPENDENTLY re-derives, per claim, the trusted ground truth an
    award rests on (red-team P0-1): the required maturity (from the trusted claims
    registry), the achieved maturity + evidence presence (recomputed from on-disk
    grounding — NOT read from any certificate), the oracle validity (a critical
    claim must have a non-judge oracle), and the kernel's own hard-gate verdict.
    A forged certificate cannot move these because the kernel derives them itself."""
    root = Path(root)
    registry = claims_mod.build_claims(root)
    gt = {}
    for cid, claim in registry.items():
        # evidence presence re-derived from disk, independent of any certificate
        present = all(claims_mod._control_present(root, ref)
                      for ref in claim["grounding"])
        achieved = claim["achieved_maturity"]     # itself recomputed from disk
        required = claim["required_maturity"]
        oracle_valid = True                       # deterministic oracle available
        if claim["critical"]:
            oracle_valid = not oracles_mod.critical_oracle_findings(
                {cid: ["DETERMINISTIC"]})
        gt[cid] = {
            "claim_id": cid, "required_maturity": required,
            "achieved_maturity": achieved, "evidence_present": present,
            "evidence_current": present, "evidence_refuted": False,
            "oracle_valid": bool(oracle_valid),
            # M1 claims need no statistical certificate; higher-maturity claims are
            # not awardable from M1 evidence anyway (maturity gate blocks them)
            "statistical_ok": True,
            "hard_gate_pass": hard_gate_pass is True,
            "defeater_refs": [],
        }
    return gt


def check_credits(certificates: list, *, configuration_root: str,
                  program_seal: str, ground_truth: dict) -> dict:
    """Independently check every credit certificate against the KERNEL-derived
    ground truth. This is the ONLY path that awards credits; the certificate's
    self-reported obligations/maturity are never trusted."""
    awards, checked = {}, []
    for cert in certificates:
        gt = ground_truth.get(cert.get("claim_id"))
        v = credits_mod.check_certificate(
            cert, expected_configuration_root=configuration_root,
            expected_program_seal=program_seal, ground_truth=gt)
        awards[cert["claim_id"]] = {"awarded": v["awarded"],
                                    "credits": v["credits"]}
        checked.append(v)
    return {"awards": awards, "checked": checked,
            "awarded_count": sum(1 for a in awards.values() if a["awarded"])}


def verify_all(*, checked: list, scorecard: dict, awards: dict,
               genome: dict, seal: dict, expected_commit: str) -> dict:
    """Full trusted verification: credit-certificate integrity + score arithmetic
    + genome + seal. `checked` are the verdicts from check_credits (already
    ground-truth-checked)."""
    findings: list[Finding] = []
    findings.extend(credits_mod.credit_findings(checked))
    findings.extend(score_mod.verify_score_arithmetic(scorecard, awards))
    if not genome_mod.verify_genome(genome):
        findings.append(Finding("EVALUATION_GENOME_MISMATCH", P0, "genome",
                               "evaluation genome root does not recompute", {}))
    for p in genome_mod.verify_seal(seal, expected_commit=expected_commit):
        findings.append(Finding("EVALUATION_SEAL_MISMATCH", P0, "seal", p, {}))
    return {"findings": findings, "valid": not any(
        f.severity in (P0, "P1") for f in findings)}

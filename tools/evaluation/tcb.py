"""Evaluation Trusted Computing Base manifest + Minimal Trusted Evaluation Kernel
(SP0011 §2.1.B, §11.2, D-0011-005/006/007, AC-0011-021..023).

The evaluation verdict's trustworthiness rests on a SMALL, EXPLICIT set of
modules — the Evaluation TCB. Everything else (scenario generators, run
harnesses, judges, statistical generators) is UNTRUSTED and re-checked by a TCB
member. The Trusted Evaluation Kernel must be materially smaller than the full
generator/execution stack. This manifest content-hashes the TCB members, names
the minimal kernel, and records the trusted inputs the Evaluation Seal consumes.

A declared TCB member absent on disk is fail-closed P0 (the trusted base is
incomplete). Trust is pinned to exact bytes.
"""
from __future__ import annotations

from pathlib import Path

from .canon import hash_obj, sha256_hex
from .model import Finding, P0

_PKG = "tools/evaluation"

# The Evaluation TCB: modules whose correctness the seal depends on. Deliberately
# small — the checkers + the accounting + the seal, NOT the generators/runners.
TCB_MEMBERS = (
    "canon.py",          # canonical hashing / Merkle forest (all roots)
    "model.py",          # closed vocabularies + maturity + accounting
    "kernel.py",         # the independent checkers (the gate)
    "credits.py",        # proof-carrying credit certificate + checker
    "hardgates.py",      # non-compensatory hard-gate lattice
    "score.py",          # score arithmetic + envelope + maturity
    "genome.py",         # evaluation genome + seal
    "admit.py",          # SP0010 program-seal admission
    "freeze.py",         # baseline identity
    "configuration.py",  # configuration identity
)

# The Minimal Trusted Evaluation Kernel: the irreducible core. If these are
# correct, an untrusted generator/runner/judge cannot forge a credit (its output
# is re-checked by credits.py, hashed by canon.py, accounted by model.py, gated
# by hardgates.py + score.py).
MINIMAL_KERNEL = ("canon.py", "model.py", "kernel.py", "credits.py",
                  "hardgates.py", "score.py")

SEAL_TRUSTED_INPUTS = {
    "configuration_root": "configuration.py:configuration_root",
    "credit_certificate_root": "credits.py:credit_root",
    "scorecard_root": "score.py:scorecard",
    "hard_gate_state": "hardgates.py:evaluate_hard_gates",
    "trusted_kernel_root": "tcb.py:tcb_root",
    "global_evaluation_root": "genome.py:build_genome",
}


def _member_hash(root: Path, rel: str) -> str:
    p = root / _PKG / rel
    if not p.exists():
        return "MISSING"
    try:
        return sha256_hex(p.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return "UNREADABLE"


def build_manifest(root: Path) -> dict:
    root = Path(root)
    members = {rel: _member_hash(root, rel) for rel in TCB_MEMBERS}
    missing = sorted(rel for rel, h in members.items()
                     if h in ("MISSING", "UNREADABLE"))
    # generator/runner modules deliberately OUTSIDE the TCB (untrusted, rechecked)
    untrusted = ("scenarios.py", "oracles.py", "judges.py", "statistics.py",
                 "robust.py", "longhorizon.py", "causal.py", "calibration.py",
                 "invariance.py", "providers.py", "fidelity.py", "drift.py",
                 "coverage.py", "contamination.py", "claims.py")
    return {
        "tcb_version": "1.0", "package": _PKG,
        "members": members,
        "minimal_trusted_kernel": list(MINIMAL_KERNEL),
        "untrusted_rechecked_modules": list(untrusted),
        "seal_trusted_inputs": SEAL_TRUSTED_INPUTS,
        "member_count": len(members),
        "untrusted_count": len(untrusted),
        "kernel_smaller_than_stack": len(members) < len(members) + len(untrusted),
        "missing_members": missing,
        "complete": not missing,
        "tcb_root": hash_obj(members),
    }


def tcb_findings(manifest: dict) -> list[Finding]:
    out: list[Finding] = []
    for rel in manifest["missing_members"]:
        out.append(Finding(
            "EVALUATION_TCB_INCOMPLETE", P0, rel,
            "a declared Evaluation TCB member is absent/unreadable: the trusted "
            "base is incomplete, seal cannot be trusted (D-0011-007)",
            {"member": rel}))
    return out


def tcb_root(manifest: dict) -> str:
    return manifest["tcb_root"]

"""Trusted Computing Base manifest + Minimal Trusted Assurance Kernel
(SP0010 V5 FUNCTION Y, §0, D-0010-91..95).

The Program Seal's trustworthiness rests on a SMALL, EXPLICIT set of modules — the
Trusted Computing Base. Everything else in the kernel is either untrusted (its
output is re-checked by a TCB member — e.g. the solver is re-checked by the
independent certificate checker) or non-load-bearing. This manifest:

  * enumerates the TCB members and content-hashes each (so a change to a trusted
    module moves the tcb_root and is visible),
  * names the MINIMAL TRUSTED ASSURANCE KERNEL — the smallest subset that must be
    correct for the verdict to mean anything: canonical hashing, the epistemic
    lattice, the independent certificate checker, and the seal gate,
  * records the trusted INPUTS the seal consumes (each produced by a TCB member),
    so no module OUTSIDE the TCB can silently move the seal.

A declared TCB member that is absent on disk is a fail-closed P0 (the trusted
base is incomplete). The manifest never trusts a module merely because it exists;
it records its content hash so the trust is pinned to exact bytes.

Governance/analysis tooling only; never imported by product code; no external
effect; emits no secret values.
"""
from __future__ import annotations

from pathlib import Path

from .canon import hash_obj, sha256_hex
from .model import Finding, P0

_PKG = "tools/architecture_closure"

# The Trusted Computing Base: modules whose correctness the seal depends on.
TCB_MEMBERS = (
    "canon.py",          # canonical hashing / Merkle forest (all roots)
    "model.py",          # the four-valued lattice + closed vocabularies
    "freeze.py",         # baseline identity + frozen verifier constant
    "certificates.py",   # the INDEPENDENT certificate checker (the gate)
    "seal.py",           # the fail-closed closure-state + seal gate
    "bootstrap_verify.py",  # N-version ceremony (verifier diversity)
    "federated.py",      # federated backend convergence gate
    "dual_graph.py",     # declared-vs-real conformance
    "extraction.py",     # extraction uncertainty firewall
    "epistemic.py",      # four-valued classification
    "hypergraph.py",     # conjunctive positive-support closure
)

# The Minimal Trusted Assurance Kernel: the irreducible core. If these four are
# correct, an untrusted solver cannot forge a closure (its output is re-checked
# by certificates.py, hashed by canon.py, classified by model.py, gated by
# seal.py). Everything else can be wrong-but-caught.
MINIMAL_KERNEL = ("canon.py", "model.py", "certificates.py", "seal.py")

# The trusted inputs the seal consumes and the TCB member that produces each.
SEAL_TRUSTED_INPUTS = {
    "architecture_genome_root": "canon.py:global_root",
    "certificate_root": "certificates.py:certify_closure",
    "dual_graph_root": "dual_graph.py:compare",
    "verifier_set_root": "bootstrap_verify.py:verifier_set_root",
    "federation_root": "federated.py:federate",
    "closure_state": "seal.py:closure_state",
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
    return {
        "tcb_version": "1.0",
        "package": _PKG,
        "members": members,
        "minimal_trusted_kernel": list(MINIMAL_KERNEL),
        "seal_trusted_inputs": SEAL_TRUSTED_INPUTS,
        "member_count": len(members),
        "missing_members": missing,
        "complete": not missing,
        "tcb_root": hash_obj(members),
    }


def tcb_findings(manifest: dict) -> list[Finding]:
    out: list[Finding] = []
    for rel in manifest["missing_members"]:
        out.append(Finding(
            "TCB_MEMBER_MISSING", P0, rel,
            "a declared Trusted Computing Base member is absent/unreadable: the "
            "trusted base is incomplete, seal cannot be trusted (D-0010-91)",
            {"member": rel}))
    return out


def tcb_root(manifest: dict) -> str:
    return manifest["tcb_root"]

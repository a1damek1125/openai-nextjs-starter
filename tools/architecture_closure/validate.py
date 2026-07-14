"""Whole-closure validation (SP0010): determinism, genome, seal, boundary,
models.

Valid iff no P0 and no P1 — honest UNKNOWNs (P2) never invalidate a correct
closure; a broken/stale one always fails. The determinism gate re-derives the
closure from source and compares digests (a committed closure that does not
byte-match a fresh build is stale or non-deterministic).
"""
from __future__ import annotations

import json
from pathlib import Path

from .model import Finding, P0, P1, report, REASON_CODES
from . import closure as closure_mod, genome as genome_mod, seal as seal_mod, \
    boundary, modelcheck, freeze as freeze_mod

REQUIRED_KEYS = ("twin_version", "freeze", "constitutional_interfaces",
                 "assurance_hypergraph", "epistemic_states", "program_seal",
                 "architecture_genome", "sp0011_admission", "closure_digest")


def validate_closure(twin: dict, root: Path):
    findings: list[Finding] = []
    for k in REQUIRED_KEYS:
        if k not in twin:
            findings.append(Finding("PROGRAM_SEAL_MISMATCH", P1, "closure",
                                    f"closure missing required key {k}", {}))
    if findings:
        return report(findings)

    # fold the twin's OWN hard findings into validation (red-team P0-1): a
    # closure carrying P0/P1 findings is invalid regardless of determinism.
    for f in twin.get("findings", []):
        if f.get("severity") in (P0, P1):
            kind = f.get("kind") if f.get("kind") in REASON_CODES \
                else "PROGRAM_SEAL_MISMATCH"
            findings.append(Finding(
                kind, f.get("severity"), str(f.get("subject", "-")),
                "closure carries a hard finding: " + str(f.get("message"))[:120],
                {}))

    fresh = closure_mod.build_closure(root)
    if fresh["closure_digest"] != twin["closure_digest"]:
        findings.append(Finding(
            "PROGRAM_SEAL_MISMATCH", P0, "closure",
            "committed closure digest does not match a fresh build: stale or "
            "non-deterministic (D-0010-27)",
            {"committed": twin["closure_digest"],
             "fresh": fresh["closure_digest"]}))

    if not genome_mod.verify_genome(twin["architecture_genome"]):
        findings.append(Finding(
            "ARCHITECTURE_GENOME_MISMATCH", P0, "genome",
            "genome global root does not recompute from its class roots", {}))

    frz = freeze_mod.freeze(root)
    for problem in seal_mod.verify_seal(twin["program_seal"],
                                        expected_commit=frz["head"]):
        findings.append(Finding("PROGRAM_SEAL_MISMATCH", P0, "seal",
                                problem, {}))

    findings.extend(boundary.check_boundary(root))
    findings.extend(modelcheck.run_models()["findings"])
    return report(findings)


def load_closure(path: Path) -> dict:
    return json.load(open(path, encoding="utf-8"))

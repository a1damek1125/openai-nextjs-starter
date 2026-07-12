"""Whole-evaluation validation (SP0011): determinism, genome, seal, boundary,
kernel, score arithmetic.

Valid iff no P0 and no P1 — honest UNKNOWNs / M1-only maturity (P2) never
invalidate a correct evaluation; a broken/stale one always fails. The determinism
gate re-derives the evaluation from source and compares digests.
"""
from __future__ import annotations

import json
from pathlib import Path

from .model import Finding, P0, P1, report, REASON_CODES
from . import (evaluation as eval_mod, genome as genome_mod, boundary,
               freeze as freeze_mod)

REQUIRED_KEYS = ("twin_version", "freeze", "configuration", "claims",
                 "scorecard", "evaluation_genome", "evaluation_seal",
                 "qualification_envelope", "evaluation_digest")


def validate_evaluation(twin: dict, root: Path):
    findings: list[Finding] = []
    for k in REQUIRED_KEYS:
        if k not in twin:
            findings.append(Finding("SCORECARD_INVALID", P1, "evaluation",
                                    f"evaluation missing required key {k}", {}))
    if findings:
        return report(findings)

    for f in twin.get("findings", []):
        if f.get("severity") in (P0, P1):
            kind = f.get("kind") if f.get("kind") in REASON_CODES \
                else "SCORECARD_INVALID"
            findings.append(Finding(
                kind, f.get("severity"), str(f.get("subject", "-")),
                "evaluation carries a hard finding: " + str(f.get("message"))[:120],
                {}))

    fresh = eval_mod.build_evaluation(root)
    if fresh["evaluation_digest"] != twin["evaluation_digest"]:
        findings.append(Finding(
            "EVALUATION_SEAL_MISMATCH", P0, "evaluation",
            "committed evaluation digest does not match a fresh build: stale or "
            "non-deterministic", {"committed": twin["evaluation_digest"],
                                  "fresh": fresh["evaluation_digest"]}))
    if not genome_mod.verify_genome(twin["evaluation_genome"]):
        findings.append(Finding("EVALUATION_GENOME_MISMATCH", P0, "genome",
                                "evaluation genome root does not recompute", {}))
    frz = freeze_mod.freeze(root)
    for p in genome_mod.verify_seal(twin["evaluation_seal"],
                                    expected_commit=frz["starting_head"]):
        findings.append(Finding("EVALUATION_SEAL_MISMATCH", P0, "seal", p, {}))
    findings.extend(boundary.check_boundary(root))
    return report(findings)


def load_evaluation(path: Path) -> dict:
    return json.load(open(path, encoding="utf-8"))

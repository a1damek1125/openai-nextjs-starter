"""Whole-twin validation (SP0009): determinism, envelope, boundary, models.

Valid iff no P0 and no P1 — honest UNKNOWNs (P2) never invalidate a correct
twin, a broken/stale one always fails. The determinism gate re-derives the twin
from source and compares digests: a committed twin that does not byte-match a
fresh build is stale or non-deterministic (P0).
"""
from __future__ import annotations

import json
from pathlib import Path

from .model import Finding, P0, P1, report
from . import bootstrap, envelope as envelope_mod, boundary, modelcheck

REQUIRED_KEYS = ("twin_version", "candidate", "gate_ledger", "gate_verdict",
                 "dod_closure", "execution_ledger", "artifact",
                 "artifact_closure", "release_envelope", "twin_digest")


def validate_twin(twin: dict, root: Path):
    findings: list[Finding] = []
    for k in REQUIRED_KEYS:
        if k not in twin:
            findings.append(Finding("RELEASE_PROOF_MISMATCH", P1, "twin",
                                    f"twin missing required key {k}", {}))
    if findings:
        return report(findings)
    fresh = bootstrap.build_twin(root)
    if fresh["twin_digest"] != twin["twin_digest"]:
        findings.append(Finding(
            "RELEASE_PROOF_MISMATCH", P0, "twin",
            "committed twin digest does not match a fresh build: stale or "
            "non-deterministic", {"committed": twin["twin_digest"],
                                  "fresh": fresh["twin_digest"]}))
    findings.extend(envelope_mod.validate_envelope(twin["release_envelope"]))
    findings.extend(boundary.check_boundary(root))
    findings.extend(modelcheck.run_models()["findings"])
    return report(findings)


def load_twin(path: Path) -> dict:
    return json.load(open(path, encoding="utf-8"))

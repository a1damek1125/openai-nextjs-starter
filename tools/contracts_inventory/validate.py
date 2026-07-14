"""Whole-inventory validation (SP0008 §validate, D-0008-45/46).

Validation re-derives the inventory from source and checks the load-bearing
properties: the build is DETERMINISTIC (a fresh build byte-matches the committed
one), the Contract Genome re-verifies, the proof envelope re-verifies, the
boundary invariants hold, and every bounded model HOLDs. It returns a Report that
is valid iff there are no P0 and no P1 findings — so honest UNKNOWNs (P2) never
make a correct inventory invalid, but a broken one always fails.
"""
from __future__ import annotations

import json
from pathlib import Path

from .model import (Finding, P0, P1, report, NON_DETERMINISTIC_OUTPUT,
                    INVALID_INVENTORY_SCHEMA)
from . import bootstrap, genome as genome_mod, envelope as envelope_mod, \
    closure, modelcheck, normalize, discover

REQUIRED_TOP_KEYS = ("inventory_version", "counts", "surfaces", "genome",
                     "envelope", "findings", "inventory_digest")


def validate_inventory(inv: dict, root: Path) -> object:
    """Validate a materialized inventory object against a fresh build."""
    findings: list[Finding] = []

    # 1. schema shape
    for k in REQUIRED_TOP_KEYS:
        if k not in inv:
            findings.append(Finding(
                INVALID_INVENTORY_SCHEMA, P1, "inventory",
                f"inventory missing required key {k!r}", {}))
    if findings:
        return report(findings)

    # 2. determinism — a fresh build must byte-match
    fresh = bootstrap.build_inventory(root)
    if fresh["inventory_digest"] != inv["inventory_digest"]:
        findings.append(Finding(
            NON_DETERMINISTIC_OUTPUT, P0, "inventory",
            "committed inventory digest does not match a fresh build: the "
            "inventory is stale or non-deterministic",
            {"committed": inv["inventory_digest"],
             "fresh": fresh["inventory_digest"]}))

    # 3. genome re-verification (against a fresh reconcile)
    descriptors = bootstrap._load_descriptors(root)
    surfaces = normalize.reconcile(discover.discover_all(root), descriptors)
    findings.extend(genome_mod.verify_genome(surfaces, inv["genome"]))

    # 4. envelope re-verification
    findings.extend(envelope_mod.validate_envelope(inv["envelope"]))

    # 5. boundary + models
    findings.extend(closure.check_boundary(root))
    findings.extend(modelcheck.run_models()["findings"])

    return report(findings)


def load_inventory(path: Path) -> dict:
    return json.load(open(path, encoding="utf-8"))

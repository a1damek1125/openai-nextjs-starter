"""Bounded model checks over the inventory's core invariants (SP0008 §modelcheck,
D-0008-45).

Small, exhaustive checks that must HOLD for the inventory logic to be trustworthy
— the same discipline SP0007 used. Each model enumerates a bounded input space
and asserts an invariant; a violation is a P0 finding. These guard the properties
the whole mission rests on: identity is stable and label-independent, the genome
moves on material change and only on material change, and UNKNOWN never silently
becomes a positive claim.
"""
from __future__ import annotations

from .canon import surface_id, core_hash, material_fingerprint
from .model import Finding, P0, NON_DETERMINISTIC_OUTPUT
from .criticality import verdict, YES, NO, UNK
from .model import HARD_CRITICALITY_DIMS, CRITICALITY_DIMS


def model_identity_stable() -> list[Finding]:
    """surface_id depends only on (kind, canonical_name) — not label/location."""
    out = []
    a = surface_id("HTTP_ROUTE", "GET /x")
    b = surface_id("HTTP_ROUTE", "GET /x")
    c = surface_id("HTTP_ROUTE", "POST /x")
    d = surface_id("DB_TABLE", "GET /x")
    if a != b:
        out.append(Finding(NON_DETERMINISTIC_OUTPUT, P0, "MODEL/identity",
                          "surface_id is not deterministic", {}))
    if a == c or a == d:
        out.append(Finding(NON_DETERMINISTIC_OUTPUT, P0, "MODEL/identity",
                          "surface_id collides across kind/name", {}))
    return out


def model_material_vs_cosmetic() -> list[Finding]:
    """A cosmetic-only change (display_name/label) must NOT move the material
    fingerprint; a material change MUST move it."""
    out = []
    base = {"surface_kind": "HTTP_ROUTE", "canonical_name": "GET /x",
            "structural_fingerprints": ["f1"], "display_name": "Old",
            "label": "L1"}
    cosmetic = dict(base, display_name="New", label="L2")
    material = dict(base, canonical_name="GET /y")
    if material_fingerprint(base) != material_fingerprint(cosmetic):
        out.append(Finding(NON_DETERMINISTIC_OUTPUT, P0, "MODEL/genome",
                          "cosmetic change moved the material fingerprint", {}))
    if material_fingerprint(base) == material_fingerprint(material):
        out.append(Finding(NON_DETERMINISTIC_OUTPUT, P0, "MODEL/genome",
                          "material change did not move the fingerprint", {}))
    return out


def model_criticality_conjunctive() -> list[Finding]:
    """Any single hard flag YES => CRITICAL; the verdict never averages away a
    hard flag. Exhaustive over each hard dimension in isolation."""
    out = []
    for d in HARD_CRITICALITY_DIMS:
        vec = {dim: NO for dim in CRITICALITY_DIMS}
        vec[d] = YES
        if verdict(vec) != "CRITICAL":
            out.append(Finding(
                NON_DETERMINISTIC_OUTPUT, P0, "MODEL/criticality",
                f"hard flag {d}=YES did not force CRITICAL (was averaged)", {}))
    # all-NO hard flags => not CRITICAL
    allno = {dim: NO for dim in CRITICALITY_DIMS}
    if verdict(allno) == "CRITICAL":
        out.append(Finding(NON_DETERMINISTIC_OUTPUT, P0, "MODEL/criticality",
                          "no hard flag set but verdict is CRITICAL", {}))
    # any hard flag UNKNOWN (rest NO) => ELEVATED, never STANDARD
    for d in HARD_CRITICALITY_DIMS:
        vec = {dim: NO for dim in CRITICALITY_DIMS}
        vec[d] = UNK
        if verdict(vec) != "ELEVATED":
            out.append(Finding(
                NON_DETERMINISTIC_OUTPUT, P0, "MODEL/criticality",
                f"hard flag {d}=UNKNOWN was read as safe (not ELEVATED)", {}))
    return out


def model_hash_deterministic() -> list[Finding]:
    out = []
    obj = {"b": [3, 2, 1], "a": {"y": 2, "x": 1}}
    if core_hash(obj) != core_hash(dict(obj)):
        out.append(Finding(NON_DETERMINISTIC_OUTPUT, P0, "MODEL/hash",
                          "core_hash not stable across equal objects", {}))
    return out


MODELS = (
    ("identity_stable", model_identity_stable),
    ("material_vs_cosmetic", model_material_vs_cosmetic),
    ("criticality_conjunctive", model_criticality_conjunctive),
    ("hash_deterministic", model_hash_deterministic),
)


def run_models() -> dict:
    """Run every bounded model; return {model: HOLD/VIOLATED, findings}."""
    results = {}
    all_findings = []
    for name, fn in MODELS:
        fs = fn()
        results[name] = "HOLD" if not fs else "VIOLATED"
        all_findings.extend(fs)
    return {"models": results, "findings": all_findings,
            "all_hold": all(v == "HOLD" for v in results.values())}

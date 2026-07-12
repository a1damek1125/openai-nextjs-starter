"""The Merkle Contract Genome (SP0008 §12.8, D-0008-41/43, AC-0008-220).

A per-class Merkle root over the MATERIAL fingerprints of every surface of that
kind, plus a global root over the ordered class roots. The property that makes it
a genome: any material change to any contract surface (a new route, a changed
table, a retired event) moves that class's root and therefore the global root,
while a purely cosmetic change (a renamed display label, a comment) does not —
because material fingerprints strip volatile presentation (canon.strip_volatile).
This gives the inventory a single bit-reproducible identity that a downstream
verifier can pin and diff.
"""
from __future__ import annotations

from typing import Iterable

from .canon import material_fingerprint, class_root, global_root, core_hash
from .model import Finding, P0, GENOME_ROOT_MISMATCH


def _material(surface) -> dict:
    """The material contract content of a surface (identity-bearing, volatile
    presentation excluded). Detectors/labels are NOT material; kind, canonical
    name, contract kind, and structural fingerprints ARE."""
    return {
        "surface_kind": surface.surface_kind,
        "canonical_name": surface.canonical_name,
        "contract_kind": surface.contract_kind,
        "parent_contract_id": surface.parent_contract_id,
        "structural_fingerprints": list(surface.structural_fingerprints),
    }


def surface_material_leaf(surface) -> str:
    return material_fingerprint(_material(surface))


def build_genome(surfaces: Iterable) -> dict:
    """Compute per-class roots and the global genome root, deterministically."""
    by_class: dict[str, list] = {}
    for s in surfaces:
        by_class.setdefault(s.surface_kind, []).append(surface_material_leaf(s))
    class_roots = {k: class_root(v) for k, v in by_class.items()}
    return {
        "class_roots": class_roots,
        "global_root": global_root(class_roots),
        "leaf_counts": {k: len(v) for k, v in sorted(by_class.items())},
    }


def verify_genome(surfaces: Iterable, recorded: dict) -> list[Finding]:
    """A recomputed genome that diverges from the recorded one is a material
    drift or a corrupted record (GENOME_ROOT_MISMATCH, P0)."""
    out: list[Finding] = []
    fresh = build_genome(surfaces)
    if fresh["global_root"] != recorded.get("global_root"):
        out.append(Finding(
            GENOME_ROOT_MISMATCH, P0, "GENOME",
            "recomputed global genome root does not match the recorded root: "
            "material contract drift or corrupted inventory",
            {"recorded": recorded.get("global_root"),
             "recomputed": fresh["global_root"]}))
    for cls, root in fresh["class_roots"].items():
        if root != (recorded.get("class_roots") or {}).get(cls):
            out.append(Finding(
                GENOME_ROOT_MISMATCH, P0, f"GENOME/{cls}",
                f"class root for {cls} diverges from the recorded root",
                {"recorded": (recorded.get("class_roots") or {}).get(cls),
                 "recomputed": root}))
    return out


def genome_digest(genome: dict) -> str:
    return core_hash(genome)

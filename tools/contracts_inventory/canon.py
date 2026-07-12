"""Deterministic canonical JSON, SHA-256 hashing and Merkle forest for the
Canonical Contract Surface Inventory (SP0008 §11.20, §12.8, D-0008-41/43).

Every surface identity, evidence claim, provenance edge, behavioral witness and
proof envelope digests a CANONICAL serialization (sorted keys, no whitespace, no
NaN) with volatile presentation stripped, so the whole inventory and its Contract
Genome are bit-reproducible (AC-0008-219/224). A material contract change changes
the relevant class Merkle root and the global root (AC-0008-220).

Governance/analysis tooling only; product runtime never imports it (INV-0008-53).
It opens no external effect (INV-0008-52) and never emits secret values.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_obj(obj: Any) -> str:
    return sha256_hex(canonical_json(obj))


# volatile / presentation keys excluded from hashed cores
VOLATILE_KEYS = frozenset({
    "display_name", "display_names", "label", "notes", "_comment",
    "description", "observed_at", "generated_at", "last_verified",
    "last_observed", "ui_hint", "color",
    # the Python handler FUNCTION name is not part of the HTTP contract:
    # renaming it must not move the material fingerprint / genome root
    # (red-team P1 cosmetic false-positive).
    "handler",
})


def strip_volatile(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: strip_volatile(v) for k, v in obj.items()
                if k not in VOLATILE_KEYS}
    if isinstance(obj, list):
        return [strip_volatile(v) for v in obj]
    return obj


def core_hash(obj: Any) -> str:
    return sha256_hex(canonical_json(strip_volatile(obj)))


# --- stable opaque surface identity (D-0008-06) ------------------------------
def surface_id(kind: str, canonical_name: str) -> str:
    """An immutable opaque id independent of display label and file location
    (D-0008-06): derived only from the surface kind + canonical name."""
    return "CS-" + sha256_hex(f"{kind}\x1f{canonical_name}")[:20]


def structural_fingerprint(shape: Any) -> str:
    """Structural (syntax) fingerprint — equal shape => equal fingerprint, but
    NOT proof of semantic identity (D-0008-07)."""
    return core_hash(shape)


def material_fingerprint(material: Any) -> str:
    """The material contract content whose change must move the Genome root."""
    return core_hash(material)


# --- Merkle forest (§11.20, §12.8) -------------------------------------------
def _pair_hash(a: str, b: str) -> str:
    return sha256_hex("\x00".join(("N", a, b)))


def merkle_root(leaves: list[str]) -> str:
    """Deterministic binary Merkle root over ordered leaf hashes. Empty => a
    fixed empty-root sentinel; a single leaf is its own root."""
    if not leaves:
        return sha256_hex("EMPTY_MERKLE_ROOT")
    level = list(leaves)
    while len(level) > 1:
        nxt: list[str] = []
        for i in range(0, len(level), 2):
            if i + 1 < len(level):
                nxt.append(_pair_hash(level[i], level[i + 1]))
            else:
                nxt.append(_pair_hash(level[i], level[i]))   # promote odd leaf
        level = nxt
    return level[0]


def class_root(material_leaves: list[str]) -> str:
    """Per-class root over material leaves, sorted for determinism (§12.8)."""
    return merkle_root(sorted(material_leaves))


def global_root(class_roots: dict[str, str]) -> str:
    """Global Genome root from ordered class roots (§12.8): a change to any class
    root changes the global root."""
    ordered = [f"{k}={class_roots[k]}" for k in sorted(class_roots)]
    return sha256_hex(canonical_json(ordered))

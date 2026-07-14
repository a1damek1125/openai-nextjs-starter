"""Deterministic canonical JSON, SHA-256 and the Architecture Merkle Forest
(SP0010 §11.16, §12.11, D-0010-26/27).

Every constitutional interface, assurance hyperedge, evidence atom, epistemic
state, invariant, hyperproperty, gap and the Program Seal digests a CANONICAL
serialization (sorted keys, compact, no NaN) with volatile presentation
stripped, so the Architecture Genome and Program Seal are bit-reproducible and
any material root change moves the global architecture root.

Governance/analysis tooling only; never imported by product code; opens no
external effect; never emits secret values.
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


VOLATILE_KEYS = frozenset({
    "display_name", "label", "notes", "_comment", "description",
    "observed_at", "generated_at", "ui_hint", "color", "statement",
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


# --- Merkle forest (per-class roots + global root) ------------------------------
def _pair(a: str, b: str) -> str:
    return sha256_hex("N\x00" + a + "\x00" + b)


def merkle_root(leaves: list) -> str:
    """Binary Merkle root over ordered leaf hashes; odd leaf promoted; empty =>
    a fixed sentinel."""
    if not leaves:
        return sha256_hex("EMPTY_MERKLE")
    level = list(leaves)
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            if i + 1 < len(level):
                nxt.append(_pair(level[i], level[i + 1]))
            else:
                nxt.append(_pair(level[i], level[i]))
        level = nxt
    return level[0]


def class_root(leaves: list) -> str:
    """Per-class root over SORTED leaves (order-independent within a class)."""
    return merkle_root(sorted(leaves))


def global_root(class_roots: dict) -> str:
    """Global root from ordered class roots: any class root change moves it."""
    ordered = [f"{k}={class_roots[k]}" for k in sorted(class_roots)]
    return sha256_hex(canonical_json(ordered))

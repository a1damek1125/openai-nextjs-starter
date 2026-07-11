"""Deterministic canonical JSON + SHA-256 hashing for the Program Constitution.

SP0003 D-0003-40/43/§11.25. Every derived analysis and every proof-envelope
field digests a CANONICAL serialization (sorted keys, no whitespace, no NaN) so
the same program state always yields the same hash and two independent runs are
bit-identical (AC-0003-92). Volatile display metadata is excluded from hashed
cores by the callers that build them.

Program-planning tooling only; product runtime must never import it (AC-0003-97).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    """Stable serialization: sorted keys, compact separators, UTF-8, no NaN."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_obj(obj: Any) -> str:
    """Canonical hash of an arbitrary JSON-serializable object."""
    return sha256_hex(canonical_json(obj))


# Keys that are presentation-only / volatile and must never enter a hashed core
# (SP0003 §11.25 — "exclude volatile display metadata").
VOLATILE_KEYS = frozenset({
    "display_name", "notes", "editor_notes", "_comment", "description",
    "created_at", "updated_at", "recorded_at", "timestamp", "generated_at",
    "color", "ui_hint", "label",
})


def strip_volatile(obj: Any) -> Any:
    """Recursively drop volatile display keys so hashing sees only substance."""
    if isinstance(obj, dict):
        return {k: strip_volatile(v) for k, v in obj.items()
                if k not in VOLATILE_KEYS}
    if isinstance(obj, list):
        return [strip_volatile(v) for v in obj]
    return obj


def core_hash(obj: Any) -> str:
    """Hash an object after stripping volatile display metadata."""
    return sha256_hex(canonical_json(strip_volatile(obj)))

"""Deterministic canonical JSON + SHA-256 hashing for the Technology Sovereignty
Constitution (SP0004 §11.16, D-0004-80/81).

Every proof-envelope and evidence hash digests a CANONICAL serialization (sorted
keys, no whitespace, no NaN) with volatile presentation/timestamp fields stripped,
so the same decision/substitution state always yields the same hash (AC-0004-141).

Technology-governance tooling only; product runtime must never import it
(AC-0004-149).
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


# presentation-only / volatile keys excluded from hashed cores (§11.16)
VOLATILE_KEYS = frozenset({
    "display_name", "notes", "editor_notes", "_comment", "description",
    "retrieved_at", "generated_at", "ui_hint", "color", "label",
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

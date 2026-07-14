"""Deterministic canonical JSON + hashing for the Architecture Immune System.

Mirrors the repository's existing proof-carrying convention (canonical JSON,
sorted keys, tight separators, no NaN) so architecture evidence hashes the same
way the runtime governance kernels do — but this module is architecture tooling
only and must never be imported by product runtime (SP0001 INV-0001-09).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

# Semantic-volatile keys excluded from any hashed "core" so the same repository
# tree + manifest always yields the same hash (SP0001 INV-0001-12).
VOLATILE_KEYS = frozenset({
    "generated_at", "created_at", "updated_at", "timestamp", "retrieved_at",
    "wall_clock", "duration_ms", "_comment",
})


def canonical_json(obj: Any) -> str:
    """UTF-8, sorted keys, deterministic separators, no NaN."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strip_volatile(obj: Any) -> Any:
    """Recursively drop VOLATILE_KEYS so hashes are reproducible."""
    if isinstance(obj, dict):
        return {k: strip_volatile(v) for k, v in obj.items()
                if k not in VOLATILE_KEYS}
    if isinstance(obj, list):
        return [strip_volatile(v) for v in obj]
    return obj


def core_hash(obj: Any) -> str:
    """SHA-256 of the canonical, volatile-stripped core of `obj`.

    This establishes CONTENT INTEGRITY of generated architecture artifacts. It
    does NOT establish organizational identity — cryptographic signing belongs
    to future KMS/signing infrastructure (SP0001 D-0001-14).
    """
    return sha256_hex(canonical_json(strip_volatile(obj)))

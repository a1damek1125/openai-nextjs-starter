"""Deterministic canonical JSON, SHA-256 and the Context Merkle Forest (TOOL-B10
§12.19, D-B6-090/091).

Every entitlement, version vector, snapshot, lease, evidence record, claim,
minimal basis, provenance edge, view, ABI rendering, consumption receipt, Context
BOM and the Context Capsule digests a CANONICAL serialization (sorted keys,
compact, no NaN), so capsule roots are bit-reproducible and any material input
change moves the capsule root. Content-addressed, replayable, independently
checkable.

Context-governance reference kernel only; never imported by product runtime;
opens no external effect; never emits secrets, provider tokens or answer keys.
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


# volatile presentation stripped from CORE (identity) hashes
VOLATILE_KEYS = frozenset({
    "display_name", "label", "notes", "_comment", "description", "observed_at",
    "created_at", "issued_at", "consumed_at", "generated_at", "ui_hint",
    "human_readable",
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


# --- Merkle forest -----------------------------------------------------------
def _pair(a: str, b: str) -> str:
    return sha256_hex("N\x00" + a + "\x00" + b)


def merkle_root(leaves: list) -> str:
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
    """Order-independent within a class (sorted leaves)."""
    return merkle_root(sorted(leaves))


def global_root(class_roots: dict) -> str:
    ordered = [f"{k}={class_roots[k]}" for k in sorted(class_roots)]
    return sha256_hex(canonical_json(ordered))


def content_address(content: str) -> str:
    """Content address of an evidence byte string (immutable identity)."""
    return "cid-" + sha256_hex(content)


def commitment(secret: str) -> str:
    """Hiding+binding commitment to a secret (never publishes the secret)."""
    return sha256_hex("COMMIT\x00" + secret)

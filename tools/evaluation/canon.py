"""Deterministic canonical JSON, SHA-256 and the Evaluation Merkle Forest
(SP0011 §11, §12.19, D-0011-114).

Every configuration, claim, estimand, scenario, oracle, run, statistical plan,
credit certificate, scorecard, envelope and the Evaluation Seal digests a
CANONICAL serialization (sorted keys, compact, no NaN) with volatile presentation
stripped, so the Evaluation Genome and Evaluation Seal are bit-reproducible and
any material root change moves the global evaluation root.

Governance/evaluation tooling only; never imported by product code; opens no
external effect; never emits secret values (answer keys, seeds).
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


# --- Merkle forest (per-class roots + global root) ---------------------------
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
    return merkle_root(sorted(leaves))


def global_root(class_roots: dict) -> str:
    ordered = [f"{k}={class_roots[k]}" for k in sorted(class_roots)]
    return sha256_hex(canonical_json(ordered))


def commitment(secret: str) -> str:
    """A hiding+binding commitment to a secret (e.g. a mutation seed / answer
    key) — publishes the hash, never the secret (D-0011-032/033)."""
    return sha256_hex("COMMIT\x00" + secret)

"""Deterministic canonical JSON + SHA-256 hashing for the Safety Kernel &
Assurance Constitution (SP0005 §11.16, D-0005-87/88).

Fingerprints and proof envelopes digest a CANONICAL serialization (sorted keys,
no whitespace, no NaN) with volatile presentation stripped, so an action/context
fingerprint or safety-case envelope is bit-reproducible (AC-0005-210). The action
fingerprint deliberately hashes ONLY safety-material semantics (D-0005-17).

Safety-governance tooling only; product runtime must never import it
(AC-0005-231). It opens NO external effect (INV-0005-27).
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


# volatile / presentation keys excluded from hashed cores (§D-0005-17)
VOLATILE_KEYS = frozenset({
    "display_name", "label", "notes", "editor_notes", "_comment", "description",
    "retrieved_at", "generated_at", "ui_hint", "color",
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


# --- safety-material action fingerprint (D-0005-17) ------------------------
# The declared safety-material fields for an action; volatile metadata is excluded
# so an irrelevant change does not spuriously invalidate a lease, while a material
# change (target, parameters, authority, ...) always changes the fingerprint.
ACTION_MATERIAL_FIELDS = ("action_type", "target", "parameters", "tenant",
                          "authority", "policy_version", "safety_context")
TARGET_MATERIAL_FIELDS = ("target_type", "target_id", "recipient", "account",
                          "file", "phone_number", "amount")


def action_fingerprint(action: dict) -> str:
    """Fail-CLOSED fingerprint: hash the whole action minus known-volatile keys,
    so a material value placed at the action root OUTSIDE the declared whitelist
    still changes the fingerprint (SWARM-N E6, "UNKNOWN IS NOT SAFE"). A pure
    whitelist would silently ignore rogue top-level fields."""
    return core_hash(action if isinstance(action, dict) else {"_action": action})


def target_fingerprint(action: dict) -> str:
    tgt = action.get("target", action)
    core = {f: tgt.get(f) if isinstance(tgt, dict) else None
            for f in TARGET_MATERIAL_FIELDS}
    return core_hash(core)

"""Deterministic canonical JSON + SHA-256 hashing for the Backward Compatibility,
Migration, Versioning & Contract Evolution Constitution (SP0007).

Contract/version/fixture/claim identities and proof envelopes digest a CANONICAL
serialization (sorted keys, no whitespace, no NaN) with volatile presentation
stripped, so every identity and envelope is bit-reproducible (AC-0007-194). A
change to a contract's material content changes its hash (AC-0007-195); a change
to a transformer changes the migration proof (AC-0007-196).

Governance tooling only; product runtime must never import it (INV-0007-48). It
performs no live migration and opens no external effect (INV-0007-47).
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
    "display_name", "label", "notes", "editor_notes", "_comment", "description",
    "retrieved_at", "generated_at", "ui_hint", "color", "tested_at",
    "last_observed", "announced_at",
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


# --- contract-material hashing (D-0007-06, AC-0007-035/195) -----------------
# The material content of a released contract version. Volatile presentation is
# excluded; ANY change to these fields is a NEW contract version, never a
# mutation of a released one.
VERSION_MATERIAL_FIELDS = ("contract_id", "version", "semantic_epoch",
                           "schema", "behavior_contract", "security_contract",
                           "proof_contract", "supersedes")


def schema_hash(schema: Any) -> str:
    """Hash of a contract's structural schema (fields/types/constraints)."""
    return core_hash(schema)


def version_content_hash(version: dict) -> str:
    """Hash over the material content of a contract version — the immutability
    witness (D-0007-06). Recorded at release; any later divergence is
    CONTRACT_VERSION_MUTATED."""
    core = {f: version.get(f) for f in VERSION_MATERIAL_FIELDS}
    return core_hash(core)


def fixture_hash(fixture: dict) -> str:
    """Hash of a historical fixture's payload + expected behavior — the corpus
    integrity witness (D-0007-29)."""
    core = {"contract_id": fixture.get("contract_id"),
            "contract_version": fixture.get("contract_version"),
            "fixture_kind": fixture.get("fixture_kind"),
            "payload": fixture.get("payload"),
            "expected_behavior": fixture.get("expected_behavior"),
            "semantic_epoch": fixture.get("semantic_epoch")}
    return core_hash(core)


def environment_hash(env: dict | None) -> str:
    """Hash of the evaluation environment a compatibility claim binds to
    (D-0007-07)."""
    return core_hash(env or {})


def transformer_hash(transformer: dict) -> str:
    """Hash of a migration transformer's declared identity + rules — a change
    changes every migration proof that references it (AC-0007-196)."""
    core = {"transformer_id": transformer.get("transformer_id"),
            "from_version": transformer.get("from_version"),
            "to_version": transformer.get("to_version"),
            "rules": transformer.get("rules"),
            "loss_vector": transformer.get("loss_vector")}
    return core_hash(core)

"""Deterministic canonical JSON + Meaning Hash for the Semantic Constitution.

The Meaning Hash (SP0002 D-0002-13/§11.3) digests the SEMANTIC CORE of a concept
— identity, normative definition, invariants, authority/epistemic/temporal
semantics, world assumption, normative relationships — and EXCLUDES labels,
formatting, editor notes and timestamps, so a label-only or translation change
never changes the hash (AC-0002-23) while a normative change does (AC-0002-24).

Semantics tooling only; product runtime must never import it.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

# Keys excluded from the hashed semantic core (presentation / volatile).
NON_SEMANTIC_KEYS = frozenset({
    "labels", "aliases", "deprecated_aliases", "display_name", "editor_notes",
    "notes", "_comment", "created_at", "updated_at", "recorded_at", "timestamp",
    "meaning_hash", "projection_refs", "examples",
})

# The ordered fields that DO constitute the semantic core of a concept.
SEMANTIC_CORE_FIELDS = (
    "concept_id", "canonical_key", "concept_kind", "owner_capability",
    "semantic_revision", "normative_definition", "world_assumption",
    "epistemic_rules", "semantic_invariants", "authority_semantics",
    "temporal_semantics", "state_semantics", "relationships",
    "forbidden_aliases",
    # `models` is the denotational set that drives mechanically-decidable
    # compatibility (compatibility.classify_models). It MUST be hashed, else a
    # model-set widening would be invisible to the Meaning Hash and the
    # transaction gate (red-team B1).
    "models",
)


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def semantic_core(concept: dict) -> dict:
    """Extract the normative core used for the Meaning Hash."""
    core: dict[str, Any] = {}
    for f in SEMANTIC_CORE_FIELDS:
        if f in concept:
            core[f] = concept[f]
    return core


def meaning_hash(concept: dict) -> str:
    return sha256_hex(canonical_json(semantic_core(concept)))


def core_hash(obj: Any) -> str:
    """Generic content-integrity hash (proof envelopes, epochs) — strips
    presentation/volatile keys recursively."""
    def strip(o: Any) -> Any:
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items()
                    if k not in NON_SEMANTIC_KEYS}
        if isinstance(o, list):
            return [strip(v) for v in o]
        return o
    return sha256_hex(canonical_json(strip(obj)))

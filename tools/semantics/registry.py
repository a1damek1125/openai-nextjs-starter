"""Canonical Concept Registry loader + deterministic validator (SP0002 §20.1).

Validates: one immutable concept_id each (P0), unique canonical_key (P0), owner
resolves to an SP0001 architecture capability (P1), typed relationships to
existing concepts (P1), valid world assumption / epistemic rules / concept kind
(P1), forbidden-alias / cross-concept alias collision (P0 ambiguity), Meaning
Hash matches the stored hash (P1), BCP47-ish label tags (P2). Same registry =>
same findings (deterministic).
"""
from __future__ import annotations

import json
import os
from typing import Any

from .canon import meaning_hash
from .model import (Finding, Report, P0, P1, P2, WORLD_ASSUMPTIONS, CONCEPT_KINDS,
                    EPISTEMIC_TYPES, RELATIONSHIP_TYPES,
                    DUPLICATE_CONCEPT_ID, DUPLICATE_CANONICAL_KEY, UNKNOWN_OWNER,
                    INVALID_RELATIONSHIP, MEANING_HASH_MISMATCH, FORBIDDEN_ALIAS,
                    AMBIGUOUS_CONCEPT, INVALID_WORLD_ASSUMPTION,
                    INVALID_LANGUAGE_TAG)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_LANGS = {"en", "pl", "de", "es"}   # SP0002 initial languages (BCP47 primary tags)


def sp0001_capability_ids() -> set[str]:
    path = os.path.join(REPO_ROOT, "docs", "architecture",
                        "FINALIS_1000_ARCHITECTURE_TWIN.json")
    try:
        twin = json.load(open(path, encoding="utf-8"))
        return {c["capability_id"] for c in twin["capabilities"]}
    except (OSError, KeyError, json.JSONDecodeError):
        return set()


def _valid_bcp47_primary(tag: str) -> bool:
    # minimal BCP47 primary-subtag check (RFC 5646): 2-3 alpha, optional -REGION
    parts = tag.split("-")
    return bool(parts[0]) and parts[0].isalpha() and 2 <= len(parts[0]) <= 3


def validate_registry(registry: dict, *, check_owner: bool = True) -> Report:
    rep = Report()
    concepts = registry.get("concepts", [])
    owners = sp0001_capability_ids() if check_owner else None
    keys = {c["canonical_key"] for c in concepts}

    seen_ids: dict[str, str] = {}
    seen_keys: dict[str, str] = {}
    # active alias/label surface -> concept (for ambiguity detection)
    surface: dict[str, list[str]] = {}
    forbidden_by_concept: dict[str, set[str]] = {}

    for c in concepts:
        cid = c.get("concept_id")
        key = c.get("canonical_key")
        # duplicate identity (P0)
        if cid in seen_ids:
            rep.add(Finding(DUPLICATE_CONCEPT_ID, P0, cid,
                            f"concept_id {cid} used by {seen_ids[cid]} and {key}",
                            {"concept_id": cid}))
        seen_ids[cid] = key
        if key in seen_keys:
            rep.add(Finding(DUPLICATE_CANONICAL_KEY, P0, key,
                            f"canonical_key {key} used twice",
                            {"canonical_key": key}))
        seen_keys[key] = cid

        # owner resolves to an SP0001 capability (P1)
        if owners is not None and c.get("owner_capability") not in owners:
            rep.add(Finding(UNKNOWN_OWNER, P1, key,
                            f"owner_capability {c.get('owner_capability')} is not "
                            f"a declared SP0001 capability", {"key": key}))

        # concept kind / world assumption (P1)
        if c.get("concept_kind") not in CONCEPT_KINDS:
            rep.add(Finding(INVALID_RELATIONSHIP, P1, key,
                            f"invalid concept_kind {c.get('concept_kind')}", {}))
        if c.get("world_assumption") not in WORLD_ASSUMPTIONS:
            rep.add(Finding(INVALID_WORLD_ASSUMPTION, P1, key,
                            f"invalid world_assumption {c.get('world_assumption')}",
                            {}))
        # epistemic rules must reference known epistemic types (advisory tokens
        # like human sentences are allowed; bare uppercase tokens are checked)
        for r in c.get("epistemic_rules", []):
            for tok in str(r).replace(",", " ").split():
                if tok.isupper() and tok.isalpha() and len(tok) > 3 \
                        and tok not in EPISTEMIC_TYPES and tok not in {"OR", "AND", "NOT"}:
                    rep.add(Finding(INVALID_RELATIONSHIP, P2, key,
                                    f"epistemic_rule references unknown token {tok}",
                                    {"token": tok}))

        # relationships: typed + target exists (P1)
        for rel in c.get("relationships", []):
            if rel.get("type") not in RELATIONSHIP_TYPES:
                rep.add(Finding(INVALID_RELATIONSHIP, P1, key,
                                f"invalid relationship type {rel.get('type')}", rel))
            if rel.get("target") not in keys:
                rep.add(Finding(INVALID_RELATIONSHIP, P1, key,
                                f"relationship target {rel.get('target')} not found",
                                rel))

        # meaning hash matches (P1) — only if a hash is stored
        if c.get("meaning_hash"):
            expected = meaning_hash(c)
            if expected != c["meaning_hash"]:
                rep.add(Finding(MEANING_HASH_MISMATCH, P1, key,
                                "stored meaning_hash does not match semantic core",
                                {"expected": expected, "stored": c["meaning_hash"]}))

        # labels: BCP47-ish tags (P2)
        for tag in c.get("labels", {}):
            if tag not in _LANGS and not _valid_bcp47_primary(tag):
                rep.add(Finding(INVALID_LANGUAGE_TAG, P2, key,
                                f"label tag {tag} is not a valid BCP47 primary tag",
                                {"tag": tag}))

        # own active surface forms of THIS concept (aliases + unqualified key tail)
        own_surface = set(c.get("aliases", [])) | {key.split(".")[-1]}
        forbidden_by_concept[key] = set(c.get("forbidden_aliases", []))
        # FORBIDDEN_ALIAS (P0): this concept CLAIMS a term it declared forbidden
        # (e.g. work.task adds "owned_work" as its own alias). The term legitimately
        # existing on ANOTHER concept is expected — that is why it is forbidden here.
        for term in forbidden_by_concept[key] & own_surface:
            rep.add(Finding(FORBIDDEN_ALIAS, P0, key,
                            f"'{key}' claims term '{term}' it declared forbidden "
                            f"(alias laundering / concept squatting)",
                            {"term": term}))
        for a in c.get("aliases", []):
            surface.setdefault(a, []).append(key)
        surface.setdefault(key.split(".")[-1], []).append(key)

    # ambiguity: any surface term mapping to >1 concept without qualification (P1)
    for term, owners_list in surface.items():
        uniq = sorted(set(owners_list))
        if len(uniq) > 1:
            rep.add(Finding(AMBIGUOUS_CONCEPT, P1, "|".join(uniq),
                            f"surface term '{term}' resolves to {uniq} — requires "
                            f"namespace qualification", {"term": term, "concepts": uniq}))

    rep.metrics.update({
        "concepts": len(concepts),
        "aliases": sum(len(c.get("aliases", [])) for c in concepts),
        "forbidden_aliases": sum(len(c.get("forbidden_aliases", [])) for c in concepts),
        "relationships": sum(len(c.get("relationships", [])) for c in concepts),
        "languages": sorted(_LANGS),
    })
    return rep


def load_registry(path: str) -> dict:
    return json.load(open(path, encoding="utf-8"))

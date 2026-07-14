"""Multilingual labels (SP0002 D-0002-10, §20.13).

Labels (PL/EN/DE/ES) are PROJECTIONS/presentation. A translation cannot redefine
a concept's identity or its Meaning Hash (INV-0002-08). Detects: invalid BCP47
tags, translation conflicts (same label -> two concepts in one language), and
confirms translation does not change the Meaning Hash.
"""
from __future__ import annotations

from typing import Any

from .canon import meaning_hash
from .model import (Finding, P1, P2, TRANSLATION_SEMANTIC_CONFLICT,
                    INVALID_LANGUAGE_TAG)

REQUIRED_LANGS = {"en", "pl", "de", "es"}


def valid_bcp47(tag: str) -> bool:
    parts = tag.split("-")
    if not parts[0].isalpha() or not (2 <= len(parts[0]) <= 3):
        return False
    for p in parts[1:]:
        if not (p.isalnum() and 2 <= len(p) <= 8):
            return False
    return True


def validate_labels(registry: dict) -> list[Finding]:
    out: list[Finding] = []
    # same label string -> multiple concepts in the same language = conflict
    per_lang: dict[str, dict[str, list[str]]] = {}
    for c in registry.get("concepts", []):
        for tag, label in c.get("labels", {}).items():
            if not valid_bcp47(tag):
                out.append(Finding(INVALID_LANGUAGE_TAG, P1, c["canonical_key"],
                                   f"invalid BCP47 tag {tag}", {"tag": tag}))
            per_lang.setdefault(tag, {}).setdefault(label.lower(), []).append(
                c["canonical_key"])
    for tag, labels in per_lang.items():
        for label, keys in labels.items():
            uniq = sorted(set(keys))
            if len(uniq) > 1:
                out.append(Finding(TRANSLATION_SEMANTIC_CONFLICT, P1,
                                   "|".join(uniq),
                                   f"label '{label}' [{tag}] denotes multiple "
                                   f"concepts {uniq}", {"label": label, "lang": tag}))
    return out


def translation_preserves_meaning(concept: dict, new_labels: dict) -> bool:
    """Changing labels must NOT change the Meaning Hash (AC-0002-66)."""
    before = meaning_hash(concept)
    mutated = dict(concept)
    mutated["labels"] = new_labels
    return meaning_hash(mutated) == before


def coverage(registry: dict) -> dict[str, Any]:
    missing = {}
    for c in registry.get("concepts", []):
        have = set(c.get("labels", {}))
        miss = sorted(REQUIRED_LANGS - have)
        if miss:
            missing[c["canonical_key"]] = miss
    return {"languages": sorted(REQUIRED_LANGS), "missing": missing}

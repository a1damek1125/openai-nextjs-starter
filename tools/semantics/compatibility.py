"""Semantic Compatibility Algebra (SP0002 D-0002-12, §11.5).

For MECHANICALLY-DECIDABLE concepts (those declaring an explicit denotational
model set — the set of world-states satisfying the concept) compatibility is
computed by set relations:
    EQUIVALENT  iff  ⟦A⟧ = ⟦B⟧
    NARROWING(B,A) iff ⟦B⟧ ⊂ ⟦A⟧      (B is stricter than A — backward compatible)
    WIDENING(B,A)  iff ⟦A⟧ ⊂ ⟦B⟧      (B is looser — BREAKING)
For natural-language-only definitions we DO NOT pretend set inclusion is proven:
the result is REVIEW_REQUIRED / UNKNOWN, decided by human review + historical
replay (INV: never falsely certify unknown compatibility, AC-0002-39).
"""
from __future__ import annotations

from typing import Any

from .model import BREAKING_COMPATIBILITY


def classify_models(models_a: set, models_b: set) -> str:
    """Classify B relative to A by their denotational model sets."""
    if models_a == models_b:
        return "EQUIVALENT"
    if models_b < models_a:
        return "NARROWING"          # B stricter subset of A -> backward compatible
    if models_a < models_b:
        return "WIDENING"           # B superset of A -> breaking
    if models_a.isdisjoint(models_b):
        return "INCOMPATIBLE"
    return "CONDITIONALLY_COMPATIBLE"   # overlap but neither contains the other


def classify(concept_a: dict, concept_b: dict) -> dict[str, Any]:
    """Classify concept_b's meaning relative to concept_a's.

    Uses `models` (a list of state tokens) when BOTH declare it — the only path
    that yields an exact class. Otherwise REVIEW_REQUIRED (never fabricated).
    """
    ma = concept_a.get("models")
    mb = concept_b.get("models")
    if ma is not None and mb is not None:
        cls = classify_models(set(ma), set(mb))
        return {"class": cls, "decidable": True,
                "breaking": cls in BREAKING_COMPATIBILITY}
    # non-formal: do not claim set inclusion; require review / replay evidence
    return {"class": "REVIEW_REQUIRED", "decidable": False, "breaking": None,
            "note": "no denotational model set declared; use review + replay"}


def is_breaking(classification: dict) -> bool | None:
    return classification.get("breaking")

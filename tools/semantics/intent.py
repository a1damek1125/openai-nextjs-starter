"""Semantic Change Intent (SP0002 D-0002-14, §10.4).

Declares intended semantic evolution. Intent is NOT authority: a breaking change
still requires a new epoch (INV-0002-10) and a partial rollout is forbidden
(INV-0002-11) regardless of what the intent claims.
"""
from __future__ import annotations

from typing import Any

from .model import COMPATIBILITY_CLASSES

CHANGE_CLASSES = {"EDITORIAL", "LABEL_ONLY", "NARROWING", "WIDENING",
                  "NEW_CONCEPT", "DEPRECATION", "RELATIONSHIP_CHANGE",
                  "WORLD_ASSUMPTION_CHANGE", "EPISTEMIC_CHANGE"}
BREAKING_CLASSES = {"WIDENING", "WORLD_ASSUMPTION_CHANGE", "EPISTEMIC_CHANGE"}
REQUIRED_FIELDS = ["change_id", "base_epoch", "target_concepts", "change_classes"]


def validate_intent(intent: dict) -> list[str]:
    errs: list[str] = []
    for f in REQUIRED_FIELDS:
        if f not in intent:
            errs.append(f"missing required field: {f}")
    for cc in intent.get("change_classes", []):
        if cc not in CHANGE_CLASSES:
            errs.append(f"invalid change_class: {cc}")
    comp = intent.get("expected_compatibility", {})
    for k, v in comp.items():
        if v not in COMPATIBILITY_CLASSES:
            errs.append(f"invalid expected_compatibility for {k}: {v}")
    return errs


def is_breaking(intent: dict) -> bool:
    return bool(set(intent.get("change_classes", [])) & BREAKING_CLASSES) or \
        any(v in ("WIDENING", "INCOMPATIBLE")
            for v in intent.get("expected_compatibility", {}).values())

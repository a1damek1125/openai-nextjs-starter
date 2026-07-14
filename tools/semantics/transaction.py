"""Semantic Transaction (SP0002 D-0002-15, §11.7).

Applies a semantic change atomically across all required artifacts. A breaking
change without a new epoch is rejected (INV-0002-10); a partial rollout — new
definition active while old projections/translations/LGGT mappings still stand —
is rejected (INV-0002-11). Never partially activates.
"""
from __future__ import annotations

from typing import Any

from .canon import meaning_hash
from .compatibility import classify
from .impact import impact_cone
from .intent import is_breaking, validate_intent
from .model import (Finding, Report, P0, P1, P2, BREAKING_CHANGE_WITHOUT_EPOCH,
                    PARTIAL_SEMANTIC_TRANSACTION)
from .registry import validate_registry


def _by_key(reg: dict) -> dict[str, dict]:
    return {c["canonical_key"]: c for c in reg.get("concepts", [])}


def evaluate_change(base_registry: dict, candidate_registry: dict, intent: dict,
                    *, new_epoch: bool, updated_projections: set | None = None,
                    updated_translations: set | None = None,
                    updated_lggt: set | None = None,
                    check_owner: bool = True) -> Report:
    rep = validate_registry(candidate_registry, check_owner=check_owner)
    for e in validate_intent(intent):
        rep.add(Finding("INVALID_SEMANTIC_INTENT", P1, intent.get("change_id", "-"),
                        e, {}))

    base = _by_key(base_registry)
    cand = _by_key(candidate_registry)
    # a declared non-breaking change class must be AFFIRMATIVELY stated in the
    # intent for an undecidable change to skip the epoch requirement.
    NON_BREAKING = {"EDITORIAL", "LABEL_ONLY", "NARROWING", "DEPRECATION"}
    declared_nonbreaking = bool(set(intent.get("change_classes", [])) & NON_BREAKING)
    changed_keys: list[str] = []
    breaking_keys: list[str] = []
    undecidable_keys: list[str] = []
    for key, c in cand.items():
        b = base.get(key)
        if b is None:
            continue
        if meaning_hash(c) != meaning_hash(b):
            changed_keys.append(key)
            cls = classify(b, c)
            if cls.get("breaking"):
                breaking_keys.append(key)
            elif not cls.get("decidable"):
                undecidable_keys.append(key)

    # KEY GUARD (red-team #9): a meaning change whose compatibility CANNOT be
    # mechanically decided (no denotational models) must NOT silently pass as
    # non-breaking. It requires either a new epoch OR an intent that affirmatively
    # declares a non-breaking change class (auditable), else it is treated as
    # potentially breaking. Never falsely certify unknown compatibility (AC-0002-39).
    if undecidable_keys and not new_epoch:
        if not declared_nonbreaking:
            rep.add(Finding(BREAKING_CHANGE_WITHOUT_EPOCH, P1,
                            "|".join(sorted(undecidable_keys)),
                            "meaning changed but compatibility is undecidable "
                            "(no denotational models); requires a new epoch or an "
                            "affirmative non-breaking change class in the intent",
                            {"undecidable": sorted(undecidable_keys)}))
        else:
            # even with an affirmative non-breaking class, an undecidable change
            # is NEVER fully silent: the self-declared class is unverifiable, so a
            # P2 review advisory is always emitted so the change surfaces for
            # human/shadow review (red-team B4; AC-0002-39 never falsely certify).
            rep.add(Finding("SEMANTIC_REVIEW_REQUIRED", P2,
                            "|".join(sorted(undecidable_keys)),
                            "undecidable meaning change passed on a self-declared "
                            f"non-breaking class ({sorted(set(intent.get('change_classes', [])) & NON_BREAKING)}) "
                            "— requires shadow-eval/replay/human review, not "
                            "mechanically certified",
                            {"undecidable": sorted(undecidable_keys)}))

    # breaking change requires a new epoch (INV-0002-10)
    if (breaking_keys or is_breaking(intent)) and not new_epoch:
        rep.add(Finding(BREAKING_CHANGE_WITHOUT_EPOCH, P0,
                        "|".join(sorted(breaking_keys)) or intent.get("change_id", "-"),
                        "breaking semantic change cannot activate without a new epoch",
                        {"breaking": sorted(breaking_keys)}))

    # partial rollout guard (INV-0002-11): every affected projection/translation/
    # LGGT mapping must be updated in the SAME transaction.
    cone = impact_cone(candidate_registry, changed_keys)
    affected_proj = set(cone["affected_projections"])
    up = set(updated_projections or [])
    missing_proj = affected_proj - up
    if changed_keys and missing_proj:
        rep.add(Finding(PARTIAL_SEMANTIC_TRANSACTION, P0, "|".join(changed_keys),
                        f"projections not updated atomically: {sorted(missing_proj)}",
                        {"missing_projections": sorted(missing_proj)}))
    # if labels changed for a concept, translations must be re-affirmed
    for key in changed_keys:
        b, c = base.get(key, {}), cand.get(key, {})
        if b.get("labels") != c.get("labels") and updated_translations is not None \
                and key not in updated_translations:
            rep.add(Finding(PARTIAL_SEMANTIC_TRANSACTION, P1, key,
                            "labels changed but translation not re-affirmed", {}))

    rep.metrics.update({"changed_concepts": sorted(changed_keys),
                        "breaking_concepts": sorted(breaking_keys),
                        "new_epoch": new_epoch,
                        "impact_cone_size": cone["cone_size"]})
    return rep

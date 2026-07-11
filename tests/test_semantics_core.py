"""Registry, identity, epistemic, world, epochs, compatibility, impact.

Covers SP0002 AC 04-25, 35-41.
"""
from __future__ import annotations

import pytest

from tools.semantics.canon import meaning_hash
from tools.semantics.compatibility import classify, classify_models
from tools.semantics.epistemic import (validate_transition, distinct_from_confidence,
                                       certified_is_not_fact, is_valid_transition)
from tools.semantics.epochs import (registry_hash, epoch_hash, interpret_under,
                                    detect_epoch_downgrade, is_valid_epoch_transition)
from tools.semantics.impact import impact_cone
from tools.semantics.registry import validate_registry
from tools.semantics.world import evaluate_absence, TRUE, FALSE, UNKNOWN
from tests._sem_helpers import concept, registry


# ============================ REGISTRY (AC-06..09,25..27) ===================
def test_valid_registry_passes():
    reg = registry([concept("c-0001", "work.task"), concept("c-0002", "case.case")])
    assert validate_registry(reg, check_owner=False).valid


def test_duplicate_concept_id_fails():
    reg = registry([concept("c-0001", "work.task"), concept("c-0001", "case.case")])
    rep = validate_registry(reg, check_owner=False)
    assert any(f.kind == "DUPLICATE_CONCEPT_ID" and f.severity == "P0"
               for f in rep.findings)


def test_duplicate_canonical_key_fails():
    reg = registry([concept("c-0001", "work.task"), concept("c-0002", "work.task")])
    rep = validate_registry(reg, check_owner=False)
    assert any(f.kind == "DUPLICATE_CANONICAL_KEY" for f in rep.findings)


def test_unknown_owner_fails():
    reg = registry([concept("c-0001", "work.task", owner="not_a_capability")])
    rep = validate_registry(reg, check_owner=True)
    assert any(f.kind == "UNKNOWN_OWNER" for f in rep.findings)


def test_invalid_relationship_fails():
    reg = registry([concept("c-0001", "work.task",
                            rels=[{"type": "WAT", "target": "case.case"}])])
    assert any(f.kind == "INVALID_RELATIONSHIP"
               for f in validate_registry(reg, check_owner=False).findings)


def test_relationship_target_must_exist():
    reg = registry([concept("c-0001", "work.task",
                            rels=[{"type": "IS_A", "target": "ghost.thing"}])])
    assert any("not found" in f.message
               for f in validate_registry(reg, check_owner=False).findings)


# ============================ IDENTITY / MEANING HASH (AC-22..24) ===========
def test_label_change_preserves_meaning_hash():
    c = concept("c-0001", "work.task", labels={"en": "Task"})
    h1 = meaning_hash(c)
    c2 = dict(c); c2["labels"] = {"en": "Job", "pl": "Zadanie"}
    assert meaning_hash(c2) == h1


def test_alias_change_preserves_meaning_hash():
    c = concept("c-0001", "work.task")
    h1 = meaning_hash(c)
    c2 = dict(c); c2["aliases"] = ["new_alias"]
    assert meaning_hash(c2) == h1


def test_normative_change_changes_meaning_hash():
    c = concept("c-0001", "work.task", definition="A")
    c2 = concept("c-0001", "work.task", definition="B — materially different")
    assert meaning_hash(c) != meaning_hash(c2)


def test_world_assumption_change_changes_hash():
    a = concept("c-0001", "x.y", world="OPEN_WORLD")
    b = concept("c-0001", "x.y", world="CLOSED_WORLD")
    assert meaning_hash(a) != meaning_hash(b)


def test_meaning_hash_deterministic():
    c = concept("c-0001", "work.task")
    assert meaning_hash(c) == meaning_hash(dict(c))


# ============================ EPISTEMIC (AC-13..17) =========================
def test_claim_cannot_silently_become_fact():
    assert validate_transition("CLAIM", "ADMITTED_FACT")  # skips corroboration
    assert not is_valid_transition("CLAIM", "ADMITTED_FACT")


def test_llm_output_cannot_become_admitted_fact():
    f = validate_transition("CLAIM", "ADMITTED_FACT", source="LLM")
    assert f and f[0].kind == "LLM_CONCEPT_ADMISSION" and f[0].severity == "P0"


def test_certified_conclusion_distinct_from_fact():
    assert certified_is_not_fact("CERTIFIED_CONCLUSION", "ADMITTED_FACT")


def test_confidence_does_not_alter_epistemic_status():
    rec = {"epistemic_status": "CLAIM", "confidence": 0.99, "truth_degree": 0.8}
    assert distinct_from_confidence(rec)
    # status stays categorical CLAIM regardless of the high numbers
    assert rec["epistemic_status"] == "CLAIM"


def test_valid_epistemic_promotion_chain():
    for a, b in [("SIGNAL", "OBSERVATION"), ("OBSERVATION", "CLAIM"),
                 ("CLAIM", "CORROBORATED_CLAIM"),
                 ("CORROBORATED_CLAIM", "ADMITTED_FACT")]:
        assert is_valid_transition(a, b)


# ============================ WORLD ASSUMPTIONS (AC-18..21) =================
def test_open_world_absence_is_unknown():
    assert evaluate_absence("OPEN_WORLD", present=False) == UNKNOWN


def test_closed_world_bounded_absence_is_false():
    assert evaluate_absence("CLOSED_WORLD", present=False) == FALSE


def test_partial_world_requires_scope():
    assert evaluate_absence("PARTIAL_WORLD", present=False, scope_declared=False) == UNKNOWN
    assert evaluate_absence("PARTIAL_WORLD", present=False, scope_declared=True) == FALSE


def test_presence_is_true_under_any_world():
    for wa in ("OPEN_WORLD", "CLOSED_WORLD", "PARTIAL_WORLD"):
        assert evaluate_absence(wa, present=True) == TRUE


# ============================ EPOCHS (AC-11,12,05.x) ========================
def test_epoch_hash_deterministic():
    reg = registry([concept("c-0001", "work.task")])
    assert registry_hash(reg) == registry_hash(dict(reg))


def test_epoch_hash_changes_on_normative_change():
    r1 = registry([concept("c-0001", "x.y", definition="A")])
    r2 = registry([concept("c-0001", "x.y", definition="B different")])
    assert registry_hash(r1) != registry_hash(r2)


def test_epoch_hash_stable_under_label_change():
    r1 = registry([concept("c-0001", "x.y", labels={"en": "A"})])
    r2 = registry([concept("c-0001", "x.y", labels={"en": "B"})])
    assert registry_hash(r1) == registry_hash(r2)


def test_historical_record_interprets_under_original_epoch():
    epochs = [{"semantic_epoch_id": "e1", "valid_from": "2026-01-01"},
              {"semantic_epoch_id": "e2", "valid_from": "2026-06-01"}]
    rec = {"semantic_epoch_id": "e1", "recorded_at": "2026-02-01"}
    assert interpret_under(rec, epochs) == "e1"  # not the current e2


def test_epoch_downgrade_detected():
    epochs = [{"semantic_epoch_id": "e1", "valid_from": "2026-01-01"},
              {"semantic_epoch_id": "e2", "valid_from": "2026-06-01"}]
    assert detect_epoch_downgrade("e2", "e1", epochs)   # request older than active
    assert not detect_epoch_downgrade("e1", "e2", epochs)


def test_epoch_lifecycle_transitions():
    assert is_valid_epoch_transition("SHADOW", "REPLAYED")
    assert not is_valid_epoch_transition("DRAFT", "ACTIVE")   # must pass gates


# ============================ COMPATIBILITY (AC-35..39) =====================
def test_equivalent_models():
    assert classify_models({"a", "b"}, {"a", "b"}) == "EQUIVALENT"


def test_narrowing_models():
    assert classify_models({"a", "b", "c"}, {"a", "b"}) == "NARROWING"


def test_widening_models_is_breaking():
    a = concept("c-0001", "x.y", models=["a", "b"])
    b = concept("c-0001", "x.y", models=["a", "b", "c"])
    cls = classify(a, b)
    assert cls["class"] == "WIDENING" and cls["breaking"] is True


def test_incompatible_models():
    assert classify_models({"a"}, {"z"}) == "INCOMPATIBLE"


def test_unknown_compatibility_not_falsely_certified():
    # no denotational model set -> REVIEW_REQUIRED, never a fabricated exact class
    a = concept("c-0001", "x.y")
    b = concept("c-0001", "x.y", definition="different narrative")
    cls = classify(a, b)
    assert cls["class"] == "REVIEW_REQUIRED" and cls["decidable"] is False


# ============================ IMPACT CONE (AC-41) ==========================
def test_impact_cone_matches_reference():
    # customer IS_A party ; person IS_A party -> changing party impacts both
    reg = registry([
        concept("c-0001", "party.party"),
        concept("c-0002", "party.customer", rels=[{"type": "IS_A", "target": "party.party"}]),
        concept("c-0003", "party.person", rels=[{"type": "IS_A", "target": "party.party"}]),
    ])
    out = impact_cone(reg, ["party.party"])
    assert set(out["full_cone"]) == {"party.party", "party.customer", "party.person"}
    assert out["dependent_concepts"] == ["party.customer", "party.person"]


def test_impact_cone_unknown_reported():
    reg = registry([concept("c-0001", "work.task")])
    assert impact_cone(reg, ["nope.x"])["unknown_concepts"] == ["nope.x"]

"""Regression tests for SWARM-K red-team findings (SP0002 repair round)."""
from __future__ import annotations

from tools.semantics.canon import meaning_hash, SEMANTIC_CORE_FIELDS
from tools.semantics.epochs import detect_epoch_downgrade
from tools.semantics.transaction import evaluate_change
from tests._sem_helpers import concept, registry


def _kinds(rep):
    return {f.kind for f in rep.findings}


def _sev(rep, kind):
    return [f.severity for f in rep.findings if f.kind == kind]


# ---- B1: models is part of the hashed semantic core ------------------------
def test_models_is_in_semantic_core():
    assert "models" in SEMANTIC_CORE_FIELDS


def test_models_widening_changes_meaning_hash():
    a = concept("c-0001", "x.y", models=["a", "b"])
    b = concept("c-0001", "x.y", models=["a", "b", "c"])
    assert meaning_hash(a) != meaning_hash(b)


def test_models_widening_detected_as_breaking_in_transaction():
    base = registry([concept("c-0001", "x.y", models=["a", "b"])])
    cand = registry([concept("c-0001", "x.y", models=["a", "b", "c"])])  # WIDENING
    intent = {"change_id": "c1", "base_epoch": "e1", "target_concepts": ["x.y"],
              "change_classes": ["EDITORIAL"]}   # mislabeled — but now decidable
    rep = evaluate_change(base, cand, intent, new_epoch=False, check_owner=False)
    # with models hashed, the change is DECIDABLE and WIDENING -> hard P0
    assert "BREAKING_CHANGE_WITHOUT_EPOCH" in _kinds(rep)
    assert "P0" in _sev(rep, "BREAKING_CHANGE_WITHOUT_EPOCH")


# ---- B4: undecidable change is never fully silent --------------------------
def test_undecidable_change_declared_editorial_still_surfaces_p2():
    base = registry([concept("c-0001", "x.y", definition="original")])
    cand = registry([concept("c-0001", "x.y", definition="broadened meaning")])
    intent = {"change_id": "c1", "base_epoch": "e1", "target_concepts": ["x.y"],
              "change_classes": ["EDITORIAL"]}   # self-declared non-breaking
    rep = evaluate_change(base, cand, intent, new_epoch=False, check_owner=False)
    # no P1 breaking (declared non-breaking) but NEVER fully silent -> P2 review
    assert "BREAKING_CHANGE_WITHOUT_EPOCH" not in _kinds(rep)
    assert "SEMANTIC_REVIEW_REQUIRED" in _kinds(rep)


def test_undecidable_change_undeclared_is_p1():
    base = registry([concept("c-0001", "x.y", definition="a")])
    cand = registry([concept("c-0001", "x.y", definition="b broader")])
    intent = {"change_id": "c1", "base_epoch": "e1", "target_concepts": ["x.y"],
              "change_classes": ["RELATIONSHIP_CHANGE"]}
    rep = evaluate_change(base, cand, intent, new_epoch=False, check_owner=False)
    assert "BREAKING_CHANGE_WITHOUT_EPOCH" in _kinds(rep)


def test_undecidable_change_with_epoch_is_clean():
    base = registry([concept("c-0001", "x.y", definition="a")])
    cand = registry([concept("c-0001", "x.y", definition="b")])
    intent = {"change_id": "c1", "base_epoch": "e1", "target_concepts": ["x.y"],
              "change_classes": ["NARROWING"]}
    rep = evaluate_change(base, cand, intent, new_epoch=True, check_owner=False)
    assert "BREAKING_CHANGE_WITHOUT_EPOCH" not in _kinds(rep)


# ---- B2/B3: epoch downgrade fails closed + deterministic -------------------
def test_epoch_downgrade_fails_closed_on_unknown_current():
    epochs = [{"semantic_epoch_id": "e1", "valid_from": "2026-01-01"},
              {"semantic_epoch_id": "e2", "valid_from": "2026-06-01"}]
    # current epoch not in the list -> suspicious -> True (fail closed)
    assert detect_epoch_downgrade("e_ghost", "e1", epochs) is True


def test_epoch_downgrade_deterministic_on_equal_timestamps():
    epochs = [{"semantic_epoch_id": "eB", "valid_from": "2026-01-01", "recorded_at": "2026-01-02"},
              {"semantic_epoch_id": "eA", "valid_from": "2026-01-01", "recorded_at": "2026-01-01"}]
    # deterministic order by (valid_from, recorded_at, id): eA before eB
    r1 = detect_epoch_downgrade("eB", "eA", epochs)
    r2 = detect_epoch_downgrade("eB", "eA", list(reversed(epochs)))
    assert r1 == r2   # input ordering must not change the verdict
    assert r1 is True  # requesting eA (older) while eB active = downgrade

"""Projections/anti-corruption, capsule, LGGT bridge, multilingual.

Covers SP0002 AC 51-69.
"""
from __future__ import annotations

from tools.semantics.capsule import generate, CRITICAL_SEMANTIC_INVARIANTS
from tools.semantics.lggt_bridge import (validate_mapping, detect_collisions,
                                         validate_epoch_binding)
from tools.semantics.multilingual import (validate_labels, valid_bcp47,
                                          translation_preserves_meaning, coverage)
from tools.semantics.projections import (map_external, detect_takeover,
                                         validate_projections, projection_contract)
from tests._sem_helpers import concept, registry


# ============================ PROJECTIONS / ACL (AC-51..55,75) =============
def test_openapi_remains_projection():
    c = concept("c-0001", "tool.tool")
    pc = projection_contract(c, "openapi")
    assert pc["authority"] == "PROJECTION_NOT_AUTHORITY"
    assert pc["source_of_truth"] == "FINALIS_SEMANTIC_CONSTITUTION"


def test_mcp_external_term_mapped_explicitly():
    out = map_external("tool", {"tool": "tool.tool"}, "mcp")
    assert out["status"] == "MAPPED" and out["canonical_key"] == "tool.tool"
    assert out["authority"] == "EXTERNAL_NOT_AUTHORITY"


def test_a2a_unmapped_external_quarantined():
    out = map_external("weird_skill", {}, "a2a")
    assert out["status"] == "UNMAPPED_EXTERNAL_SEMANTIC" and out["quarantine"]


def test_external_field_cannot_become_canonical():
    takeover = detect_takeover({"external": "provider_status", "canonical": True})
    assert takeover and takeover[0].kind == "EXTERNAL_SEMANTIC_TAKEOVER"
    assert takeover[0].severity == "P0"


def test_authority_labeled_external_is_takeover():
    t = detect_takeover({"external": "x", "authority": "INTERNAL_AUTHORITY"})
    assert t and t[0].severity == "P0"


def test_unknown_projection_target_flagged():
    reg = registry([concept("c-0001", "x.y", projections={"weird": "ref"})])
    f = validate_projections(reg)
    assert f and f[0].kind == "UNMAPPED_PROJECTION"


# ============================ CAPSULE (AC-58,59) ===========================
def _cap_reg():
    return registry([
        concept("c-0001", "work.owned_work", forbidden=["task"],
                labels={"en": "Owned Work"}),
        concept("c-0002", "work.task", forbidden=["owned_work"], labels={"en": "Task"}),
        concept("c-0003", "party.customer", labels={"en": "Customer"}),
    ])


def test_capsule_includes_critical_invariants():
    out = generate(_cap_reg(), ["work.owned_work"], epoch_id="e1")
    for inv in CRITICAL_SEMANTIC_INVARIANTS:
        assert inv in out["critical_invariants"]


def test_capsule_includes_epoch_and_forbidden_confusions():
    out = generate(_cap_reg(), ["work.owned_work"], epoch_id="e1")
    assert out["semantic_epoch_id"] == "e1"
    assert "task" in out["forbidden_confusions"]


def test_capsule_excludes_unrelated_concepts():
    out = generate(_cap_reg(), ["work.owned_work"], epoch_id="e1")
    blob = str(out["concepts"])
    assert "party.customer" not in blob and "Customer" not in blob


def test_progressive_disclosure_still_includes_critical_invariants():
    # even at level 0, critical invariants are never omitted (AC-0002-59)
    out = generate(_cap_reg(), ["work.owned_work"], epoch_id="e1", level=0)
    assert out["critical_invariants"] == list(CRITICAL_SEMANTIC_INVARIANTS)
    # level 0 concept node has no relationships block
    assert "relationships" not in out["concepts"][0]


# ============================ LGGT BRIDGE (AC-67..69) ======================
def _mapping(cid="c-0001", fam="completed", epoch="e1"):
    return {"concept_id": cid, "canonical_key": "lifecycle.completion",
            "semantic_epoch_id": epoch, "predicate_family": fam,
            "argument_types": ["subject:string"], "world_assumption": "CLOSED_WORLD",
            "rule_pack_version": "v0"}


def test_lggt_mapping_explicit_valid():
    assert validate_mapping(_mapping()) == []


def test_lggt_mapping_missing_field_fails():
    m = _mapping(); del m["predicate_family"]
    assert validate_mapping(m)


def test_lggt_predicate_collision_detected():
    m1 = _mapping(cid="c-0001", fam="completed")
    m2 = _mapping(cid="c-0002", fam="completed")   # same family, different concept
    f = detect_collisions([m1, m2])
    assert f and f[0].kind == "LGGT_MAPPING_COLLISION" and f[0].severity == "P0"


def test_lggt_epoch_binding_checked():
    f = validate_epoch_binding([_mapping(epoch="e_old")], active_epoch="e_new")
    assert f and f[0].kind == "SEMANTIC_EPOCH_MISMATCH"


# ============================ MULTILINGUAL (AC-60..66) =====================
def test_bcp47_valid_and_invalid():
    assert valid_bcp47("en") and valid_bcp47("de-DE") and valid_bcp47("es")
    assert not valid_bcp47("123") and not valid_bcp47("e")


def test_all_initial_languages_supported():
    reg = registry([concept("c-0001", "work.task",
                            labels={"en": "Task", "pl": "Zadanie", "de": "Aufgabe",
                                    "es": "Tarea"})])
    assert coverage(reg)["missing"] == {}


def test_translation_conflict_detected():
    reg = registry([concept("c-0001", "a.x", labels={"en": "Same"}),
                    concept("c-0002", "b.y", labels={"en": "Same"})])
    f = validate_labels(reg)
    assert any(x.kind == "TRANSLATION_SEMANTIC_CONFLICT" for x in f)


def test_translation_does_not_change_meaning_hash():
    c = concept("c-0001", "work.task", labels={"en": "Task"})
    assert translation_preserves_meaning(c, {"en": "Job", "de": "Aufgabe"})


def test_invalid_language_tag_flagged():
    reg = registry([concept("c-0001", "work.task", labels={"123": "x"})])
    assert any(f.kind == "INVALID_LANGUAGE_TAG" for f in validate_labels(reg))

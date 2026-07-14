"""Adversarial Semantic Mutation Campaign (SP0002 §20.15, AC-0002-81).

Each injected semantic corruption must be caught — nothing silently passes.
"""
from __future__ import annotations

from tools.semantics.epistemic import validate_transition
from tools.semantics.lggt_bridge import detect_collisions
from tools.semantics.projections import detect_takeover
from tools.semantics.registry import validate_registry
from tools.semantics.resolve import Resolver
from tools.semantics.transaction import evaluate_change
from tools.semantics.quarantine import quarantine_item, resolve_item, creates_authority
from tests._sem_helpers import concept, registry


def _kinds(rep):
    return {f.kind for f in rep.findings}


# M1: completed = tool finished  (lexical squatting: a concept claims a term it
#     declared forbidden)
def test_mutation_completed_squatting():
    reg = registry([concept("c-0001", "action.action", forbidden=["completed"],
                            aliases=["completed"])])  # claims its own forbidden term
    rep = validate_registry(reg, check_owner=False)
    assert "FORBIDDEN_ALIAS" in _kinds(rep) and not rep.valid


# M2: fact = model guess  (LLM output promoted to ADMITTED_FACT)
def test_mutation_fact_is_model_guess():
    f = validate_transition("CLAIM", "ADMITTED_FACT", source="LLM")
    assert f and f[0].kind == "LLM_CONCEPT_ADMISSION" and f[0].severity == "P0"


# M3: employee = worker  (two concepts collapsed via alias)
def test_mutation_employee_equals_worker():
    reg = registry([
        concept("c-0001", "employee.employee", forbidden=["worker"], aliases=["worker"]),
        concept("c-0002", "employee.worker"),
    ])
    rep = validate_registry(reg, check_owner=False)
    # employee claims 'worker' which it forbids -> FORBIDDEN_ALIAS; and 'worker'
    # now resolves ambiguously
    assert "FORBIDDEN_ALIAS" in _kinds(rep)


# M4: worker = agent  (ambiguous surface term)
def test_mutation_worker_equals_agent_ambiguous():
    reg = registry([
        concept("c-0001", "employee.worker", aliases=["specialist"]),
        concept("c-0002", "employee.agent", aliases=["specialist"]),  # same alias
    ])
    rep = validate_registry(reg, check_owner=False)
    assert "AMBIGUOUS_CONCEPT" in _kinds(rep)


# M5: same LGGT predicate for two concepts
def test_mutation_shared_lggt_predicate():
    m = lambda cid: {"concept_id": cid, "predicate_family": "done",
                     "semantic_epoch_id": "e1"}
    f = detect_collisions([m("c-0001"), m("c-0002")])
    assert f and f[0].kind == "LGGT_MAPPING_COLLISION"


# M6: external provider field declared canonical
def test_mutation_external_field_declared_canonical():
    t = detect_takeover({"external": "provider.completed", "canonical": True})
    assert t and t[0].kind == "EXTERNAL_SEMANTIC_TAKEOVER" and t[0].severity == "P0"


# M7: breaking meaning change without epoch
def test_mutation_breaking_without_epoch():
    base = registry([concept("c-0001", "x.y", models=["a"])])
    cand = registry([concept("c-0001", "x.y", models=["a", "b"])])  # WIDENING
    intent = {"change_id": "c1", "base_epoch": "e1", "target_concepts": ["x.y"],
              "change_classes": ["WIDENING"]}
    rep = evaluate_change(base, cand, intent, new_epoch=False, check_owner=False)
    assert "BREAKING_CHANGE_WITHOUT_EPOCH" in _kinds(rep)


# M7b: undecidable widening evasion — change a model-less concept's meaning while
#      NOT declaring a non-breaking class and NOT opening an epoch (red-team #9).
def test_mutation_undecidable_change_cannot_skip_epoch():
    base = registry([concept("c-0001", "x.y", definition="narrow original")])
    cand = registry([concept("c-0001", "x.y", definition="much broader meaning now")])
    intent = {"change_id": "c1", "base_epoch": "e1", "target_concepts": ["x.y"],
              "change_classes": ["RELATIONSHIP_CHANGE"]}   # NOT a non-breaking class
    rep = evaluate_change(base, cand, intent, new_epoch=False, check_owner=False)
    assert "BREAKING_CHANGE_WITHOUT_EPOCH" in _kinds(rep)


def test_undecidable_change_with_epoch_ok():
    base = registry([concept("c-0001", "x.y", definition="a")])
    cand = registry([concept("c-0001", "x.y", definition="b clarified")])
    intent = {"change_id": "c1", "base_epoch": "e1", "target_concepts": ["x.y"],
              "change_classes": ["EDITORIAL"]}   # affirmative non-breaking
    rep = evaluate_change(base, cand, intent, new_epoch=False, check_owner=False)
    assert "BREAKING_CHANGE_WITHOUT_EPOCH" not in _kinds(rep)


# M8: partial semantic rollout
def test_mutation_partial_rollout():
    base = registry([concept("c-0001", "x.y", definition="A",
                             projections={"openapi": "r", "lggt": "r"})])
    cand = registry([concept("c-0001", "x.y", definition="B",
                             projections={"openapi": "r", "lggt": "r"})])
    intent = {"change_id": "c1", "base_epoch": "e1", "target_concepts": ["x.y"],
              "change_classes": ["NARROWING"]}
    rep = evaluate_change(base, cand, intent, new_epoch=True,
                          updated_projections={"openapi"}, check_owner=False)  # lggt missing
    assert "PARTIAL_SEMANTIC_TRANSACTION" in _kinds(rep)


# M9: translation changes legal scope  (a translation edit must not change the
#     meaning hash; if the "translation" actually alters the definition it is a
#     normative change, not a translation)
def test_mutation_translation_changes_meaning():
    from tools.semantics.multilingual import translation_preserves_meaning
    c = concept("c-0001", "compliance.eligible", definition="eligible under EU scope")
    # a mere label change preserves meaning...
    assert translation_preserves_meaning(c, {"de": "berechtigt"})
    # ...but altering the normative definition is caught as a hash change
    c2 = concept("c-0001", "compliance.eligible", definition="eligible under US scope")
    from tools.semantics.canon import meaning_hash
    assert meaning_hash(c) != meaning_hash(c2)


# M10: quarantine bypass  (a quarantined item must never create authority)
def test_mutation_quarantine_bypass_blocked():
    item = quarantine_item("provider_says_paid", "UNMAPPED_EXTERNAL_SEMANTIC")
    # attempt to admit it straight to authority-bearing state
    admitted = resolve_item(item, "ADMITTED_NEW_CONCEPT", concept_key="x.y")
    assert creates_authority(admitted) is False   # bypass impossible by construction


# M11: unknown structured meaning enters authoritative state
def test_mutation_unknown_meaning_quarantined_not_guessed():
    reg = registry([concept("c-0001", "work.task")])
    out = Resolver(reg).resolve("totally_unknown_term")
    assert out["status"] == "UNKNOWN" and out.get("quarantine") == "UNKNOWN_SEMANTIC"


# M12: schema-valid but semantic-invalid  (structurally fine concept that claims a
#      forbidden ambiguous alias)
def test_mutation_schema_valid_semantic_invalid():
    reg = registry([concept("c-0001", "evidence.fact", forbidden=["claim"],
                            aliases=["claim"])])   # a fact aliased as a claim
    rep = validate_registry(reg, check_owner=False)
    assert not rep.valid and "FORBIDDEN_ALIAS" in _kinds(rep)

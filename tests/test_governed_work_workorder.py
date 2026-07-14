"""FINALIS SP0006 — Governed Work: Work Identity & Admission.

Covers acceptance criteria AC-0006-021..050 (candidate intent, canonical work
order compilation, semantic/instance identity, ambiguity & conflict analysis,
and the deterministic work admission gate). Imports ONLY from
tools.governed_work.*.
"""
from __future__ import annotations

from tools.governed_work import intent, workorder, ambiguity, admission, canon
from tools.governed_work.model import (
    INVALID_WORK_SCHEMA, UNDEFINED_OUTCOME, UNDEFINED_ACCOUNTABLE_OWNER,
    CONTEXT_USED_AS_AUTHORITY, MEMORY_USED_AS_AUTHORITY,
    WORK_ORDER_AMBIGUOUS, WORK_ORDER_CONFLICTED,
)


def _k(fs):
    """Set of finding kinds from a list[Finding] or a Report."""
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


def _admit_kinds(res: dict) -> set:
    """Set of finding kinds from an admission result dict (findings are dicts)."""
    return {f["kind"] for f in res["findings"]}


# --- fixtures / builders ----------------------------------------------------
def _candidate(**over) -> dict:
    ci = {
        "work_order_id": "WO-1",
        "candidate_intent_id": "CI-1",
        "tenant_id": "T-1",
        "requester_id": "R-1",
        "source_surface": "chat",
        "source_reference": "msg-1",
        "proposed_goal": {"statement": "reconcile the invoices"},
        "proposed_scope": {"target": "acct-123"},
        "proposed_constraints": [],
    }
    ci.update(over)
    return ci


def _bindings(**over) -> dict:
    b = {
        "accountable_owner_id": "OWNER-1",
        "outcome_contract": {"predicate": "ARTIFACT_EXISTS", "ref": "out-1"},
        "budget_vector": {"financial_cost": {"total": 100}},
        "privacy_purpose": "billing_reconciliation",
        "capability_ceiling": {"risk_ceiling": 3},
        "expires_at": "2026-12-31T00:00:00Z",
    }
    b.update(over)
    return b


def _valid_work(**b_over) -> dict:
    """A COMPLETE, valid canonical work order that admits cleanly (ADMITTED)."""
    return workorder.compile_work_order(_candidate(), bindings=_bindings(**b_over))


# --- sanity: the complete work order admits (baseline for the helper) -------
def test_helper_complete_work_order_is_admitted():  # AC-0006-021..050 baseline
    res = admission.admit(_valid_work())
    assert res["decision"] == "ADMITTED"
    assert res["valid"] is True
    assert res["counts"]["P0"] == 0 and res["counts"]["P1"] == 0


# AC-0006-021 / AC-0006-022 -------------------------------------------------
def test_ac_021_022_candidate_intent_schema_and_untrusted():
    # AC-0006-021: candidate intent is normalized and stamped UNTRUSTED_PROPOSAL
    ci = intent.new_candidate_intent(_candidate())
    assert ci["status"] == "UNTRUSTED_PROPOSAL"
    assert ci["raw_content_hash"]
    # a well-formed candidate intent has no schema findings
    assert intent.validate_candidate_intent(_candidate()) == []
    # AC-0006-022: missing required fields are flagged
    bad = _candidate()
    bad.pop("tenant_id")
    assert INVALID_WORK_SCHEMA in _k(intent.validate_candidate_intent(bad))
    # AC-0006-022: intent may NEVER carry authority/approval/consent; when it
    # illegitimately does, carries_authority() is True and validate flags it.
    assert intent.carries_authority(_candidate()) is False
    for forbidden in ("authority", "approval", "consent"):
        rogue = _candidate(**{forbidden: "yes"})
        assert intent.carries_authority(rogue) is True
        assert INVALID_WORK_SCHEMA in _k(intent.validate_candidate_intent(rogue))


# AC-0006-023 .. AC-0006-027 ------------------------------------------------
def test_ac_023_027_canonical_work_order_hashes_present_and_distinct():
    w = _valid_work()
    # canonical work order compiles cleanly
    assert workorder.validate_work_order(w) == []
    # both identities present
    assert w["semantic_work_hash"]
    assert w["work_instance_hash"]
    # and DISTINCT (semantic meaning vs execution instance, D-0006-02)
    assert w["semantic_work_hash"] != w["work_instance_hash"]
    # recomputable from content
    assert canon.semantic_work_hash(w) == w["semantic_work_hash"]
    assert canon.work_instance_hash(w) == w["work_instance_hash"]


# AC-0006-028 ---------------------------------------------------------------
def test_ac_028_same_semantics_reproduce_same_semantic_hash():
    w1 = _valid_work()
    w2 = _valid_work()  # identical candidate + bindings recompiled
    assert w1["semantic_work_hash"] == w2["semantic_work_hash"]


# AC-0006-029 ---------------------------------------------------------------
def test_ac_029_different_tenant_same_semantic_diff_instance():
    w1 = _valid_work()
    w2 = workorder.compile_work_order(_candidate(tenant_id="T-2"),
                                      bindings=_bindings())
    assert w1["semantic_work_hash"] == w2["semantic_work_hash"]
    assert w1["work_instance_hash"] != w2["work_instance_hash"]


# AC-0006-030 ---------------------------------------------------------------
def test_ac_030_different_recurrence_instance_diff_instance_hash():
    w1 = _valid_work()
    w2 = _valid_work(recurrence_instance="run-2",
                     recurrence_contract_ref="RC-1")
    assert w1["semantic_work_hash"] == w2["semantic_work_hash"]
    assert w1["work_instance_hash"] != w2["work_instance_hash"]


# AC-0006-031 .. AC-0006-034 ------------------------------------------------
def test_ac_031_034_goal_canonicalized_scopes_and_constraints_explicit():
    c = _candidate(
        proposed_goal="  Reconcile invoices  ",
        proposed_constraints=[{"constraint_id": "c2"}, {"constraint_id": "c1"}],
    )
    w = workorder.compile_work_order(
        c, bindings=_bindings(forbidden_scope={"target": "acct-999"}))
    # AC-0006-031: goal canonicalized (trimmed, structured)
    assert w["canonical_goal"] == {"statement": "Reconcile invoices"}
    # AC-0006-032: allowed_scope explicit
    assert w["allowed_scope"].get("target") == "acct-123"
    # AC-0006-033: forbidden_scope explicit
    assert w["forbidden_scope"] == {"target": "acct-999"}
    # AC-0006-034: constraints explicit and deterministically ordered
    assert [x["constraint_id"] for x in w["constraints"]] == ["c1", "c2"]


# AC-0006-035 ---------------------------------------------------------------
def test_ac_035_missing_accountable_owner():
    w = workorder.compile_work_order(
        _candidate(), bindings=_bindings(accountable_owner_id=None))
    assert UNDEFINED_ACCOUNTABLE_OWNER in _k(workorder.validate_work_order(w))


# AC-0006-036 ---------------------------------------------------------------
def test_ac_036_data_processing_missing_privacy_purpose():
    w = workorder.compile_work_order(
        _candidate(), bindings=_bindings(privacy_purpose=None))
    # data-processing work with no privacy purpose is flagged at admission
    assert "PURPOSE_BINDING_FAILURE" in _admit_kinds(admission.admit(w))


# AC-0006-037 ---------------------------------------------------------------
def test_ac_037_missing_outcome_contract():
    w = workorder.compile_work_order(
        _candidate(), bindings=_bindings(outcome_contract=None))
    assert UNDEFINED_OUTCOME in _k(workorder.validate_work_order(w))


# AC-0006-038 / AC-0006-039 -------------------------------------------------
def test_ac_038_039_capability_ceiling_and_budget_required():
    # AC-0006-039: missing budget vector => finding
    w_nobudget = workorder.compile_work_order(
        _candidate(), bindings=_bindings(budget_vector=None))
    assert INVALID_WORK_SCHEMA in _admit_kinds(admission.admit(w_nobudget))
    # AC-0006-038: malformed capability ceiling => finding
    w_badcap = _valid_work()
    w_badcap["capability_ceiling"] = "not-a-dict"
    assert INVALID_WORK_SCHEMA in _admit_kinds(admission.admit(w_badcap))


# AC-0006-044 / AC-0006-045 -------------------------------------------------
def test_ac_044_045_context_and_memory_are_not_authority():
    # AC-0006-044: authority derived from context => CONTEXT_USED_AS_AUTHORITY (P0)
    w_ctx = _valid_work()
    w_ctx["authority_from_context"] = True
    res_ctx = admission.admit(w_ctx)
    assert CONTEXT_USED_AS_AUTHORITY in _admit_kinds(res_ctx)
    assert any(f["kind"] == CONTEXT_USED_AS_AUTHORITY and f["severity"] == "P0"
               for f in res_ctx["findings"])
    assert res_ctx["decision"] in ("CONFLICTED", "REJECTED")
    # AC-0006-045: authority derived from memory => MEMORY_USED_AS_AUTHORITY (P0)
    w_mem = _valid_work()
    w_mem["authority_from_memory"] = True
    res_mem = admission.admit(w_mem)
    assert MEMORY_USED_AS_AUTHORITY in _admit_kinds(res_mem)
    assert any(f["kind"] == MEMORY_USED_AS_AUTHORITY and f["severity"] == "P0"
               for f in res_mem["findings"])
    assert res_mem["decision"] in ("CONFLICTED", "REJECTED")


# AC-0006-046 .. AC-0006-048 ------------------------------------------------
def test_ac_046_048_ambiguity_and_conflict_analyzers():
    # analyzers exist and are callable
    assert callable(ambiguity.analyze_ambiguity)
    assert callable(ambiguity.analyze_conflict)
    assert callable(ambiguity.minimum_clarification_set)
    assert callable(ambiguity.safe_reduced_scope)
    # a work order missing target, outcome, and owner
    c = _candidate(proposed_scope={})
    w = workorder.compile_work_order(
        c, bindings=_bindings(accountable_owner_id=None, outcome_contract=None))
    result = ambiguity.analyze(w)
    # blocking ambiguities recorded and execution blocked
    assert result["execution_blocked"] is True
    assert "target" in result["blocking_fields"]
    kinds = {f["kind"] for f in result["ambiguities"]}
    assert WORK_ORDER_AMBIGUOUS in kinds        # missing target
    assert UNDEFINED_OUTCOME in kinds           # undefined success
    assert UNDEFINED_ACCOUNTABLE_OWNER in kinds  # undefined owner
    # minimum clarification set is non-empty and asks about each blocking field
    mcs = result["minimum_clarification_set"]
    assert mcs
    asked = {q["field"] for q in mcs}
    assert {"target", "outcome_contract", "accountable_owner_id"} <= asked


# AC-0006-049 ---------------------------------------------------------------
def test_ac_049_allowed_forbidden_scope_intersection_conflicts():
    w = workorder.compile_work_order(
        _candidate(proposed_scope={"target": "acct-123"}),
        bindings=_bindings(forbidden_scope={"target": "acct-123"}))
    assert WORK_ORDER_CONFLICTED in _k(ambiguity.analyze_conflict(w))
    assert admission.admit(w)["decision"] == "CONFLICTED"


# AC-0006-050 ---------------------------------------------------------------
def test_ac_050_undefined_outcome_blocks_admission():
    w = workorder.compile_work_order(
        _candidate(), bindings=_bindings(outcome_contract=None))
    res = admission.admit(w)
    assert res["decision"] in ("REQUIRES_CLARIFICATION", "REJECTED")
    assert res["valid"] is False

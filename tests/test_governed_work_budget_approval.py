"""FINALIS SP0006 — AC-0006-081..145.

Accountability conservation, budget vector + reservation ledger + conservation
laws, non-compensatory risk control floor, context-bound approval, plan binding,
goal drift (hard + soft), and purpose/scope/hidden-work binding.

Imports ONLY from ``tools.governed_work.*`` (governance tooling).
Each test comment-maps to the AC id(s) it covers.
"""
from __future__ import annotations

import pytest

from tools.governed_work import (accountability, budget, risk, approval, plan,
                                 drift, purpose)
from tools.governed_work.model import (
    BUDGET_DIMENSIONS, BUDGET_OVERCOMMITMENT, BUDGET_CONSERVATION_FAILURE,
    QUANTITATIVE_RISK_NOT_CALIBRATED, APPROVAL_CLASS_INSUFFICIENT,
    APPROVAL_CONTEXT_MISMATCH, SELF_APPROVAL_DETECTED, HARD_GOAL_DRIFT,
    GOAL_DRIFT_OBSERVED, HIDDEN_WORK_DETECTED, PURPOSE_BINDING_FAILURE,
    ACCOUNTABILITY_CHAIN_BROKEN, INVALID_WORK_SCHEMA)


def _k(fs) -> set:
    """Set of finding kinds from a findings list."""
    return {f.kind for f in fs}


# ---------------------------------------------------------------------------
# Accountability conservation — AC-0006-081..084
# ---------------------------------------------------------------------------
ROOT = "owner:root"


def _work_order():
    return {"work_order_id": "WO-1", "accountable_owner_id": ROOT}


def test_responsibility_chain_exists_ac081():
    # AC-0006-081: a responsibility chain is built with a single accountable owner
    wo = _work_order()
    edges = [{"delegation_id": "d1", "parent_identity": "a",
              "child_identity": "b", "accountable_owner_id": ROOT}]
    chain = accountability.responsibility_chain(wo, edges)
    assert chain["accountable_owner_id"] == ROOT
    assert len(chain["links"]) == 1
    # subagent is RESPONSIBLE while the owner stays accountable (D-0006-22)
    assert chain["links"][0]["responsible"] == "b"
    assert chain["links"][0]["accountable_owner_id"] == ROOT
    assert chain["chain_hash"]


def test_owner_survives_delegation_ac082():
    # AC-0006-082: edges carry accountable_owner_id == root => no findings
    wo = _work_order()
    edges = [{"delegation_id": "d1", "parent_identity": "a",
              "child_identity": "b", "accountable_owner_id": ROOT},
             {"delegation_id": "d2", "parent_identity": "b",
              "child_identity": "c", "accountable_owner_id": ROOT}]
    fs = accountability.conservation_findings(wo, edges, terminal_owner=ROOT)
    assert fs == []


def test_unauthorized_owner_change_breaks_chain_ac083():
    # AC-0006-083: an unauthorized owner change on an edge OR the terminal owner
    # => ACCOUNTABILITY_CHAIN_BROKEN
    wo = _work_order()
    bad_edge = [{"delegation_id": "d1", "parent_identity": "a",
                 "child_identity": "b", "accountable_owner_id": "owner:other"}]
    fs_edge = accountability.conservation_findings(wo, bad_edge)
    assert ACCOUNTABILITY_CHAIN_BROKEN in _k(fs_edge)

    fs_term = accountability.conservation_findings(
        wo, [], terminal_owner="owner:other")
    assert ACCOUNTABILITY_CHAIN_BROKEN in _k(fs_term)


def test_authorized_reassignment_allows_owner_change_ac084():
    # AC-0006-084: an authorized reassignment permits a terminal owner change;
    # validate_reassignment flags an unauthorized reassignment
    wo = _work_order()
    reassignments = [{"reassignment_id": "r1", "from_owner": ROOT,
                      "to_owner": "owner:new", "authorized": True}]
    fs = accountability.conservation_findings(
        wo, [], terminal_owner="owner:new", reassignments=reassignments)
    assert fs == []

    # unauthorized reassignment is flagged
    bad = accountability.validate_reassignment(
        {"reassignment_id": "r2", "from_owner": ROOT, "to_owner": "owner:x",
         "authorized": False})
    assert ACCOUNTABILITY_CHAIN_BROKEN in _k(bad)
    # a fully-authorized reassignment validates clean
    ok = accountability.validate_reassignment(
        {"reassignment_id": "r3", "from_owner": ROOT, "to_owner": "owner:x",
         "authorized": True})
    assert ok == []


# ---------------------------------------------------------------------------
# Budget vector + ledger — AC-0006-085..100
# ---------------------------------------------------------------------------
def _full_budget_vector():
    # 6 additive dimensions ...
    bv = {d: 100.0 for d in BUDGET_DIMENSIONS}
    # ... plus the 2 non-additive dimensions handled specially (risk, deadline)
    bv["risk_vector"] = {"financial": "LOW"}
    bv["deadline"] = 1000
    return bv


def test_budget_vector_eight_dimensions_ac085_093():
    # AC-0006-085..093: 6 additive + 2 non-additive (risk, deadline) = 8 dims
    assert len(BUDGET_DIMENSIONS) == 6
    bv = _full_budget_vector()
    additive = [d for d in BUDGET_DIMENSIONS]
    non_additive = ["risk_vector", "deadline"]
    assert len(additive) + len(non_additive) == 8
    assert all(d in bv for d in additive)
    assert all(d in bv for d in non_additive)


def test_new_ledger_initializes_available_equals_total_ac086():
    # AC-0006-086..093: new_ledger initializes available == total, all else 0
    ledger = budget.new_ledger(_full_budget_vector())
    assert set(ledger["dimensions"]) == set(BUDGET_DIMENSIONS)
    for d in BUDGET_DIMENSIONS:
        s = ledger["dimensions"][d]
        assert s["available"] == s["total"] == 100.0
        assert s["reserved"] == s["consumed"] == 0.0


def test_reserve_is_idempotent_ac094():
    # AC-0006-094: reserve is idempotent on idempotency_key — no double allocation
    ledger = budget.new_ledger(_full_budget_vector())
    ledger, r1 = budget.reserve(ledger, "financial_cost", 40.0,
                                idempotency_key="k1", subject_identity="agent:1")
    assert r1["status"] == "RESERVED"
    assert ledger["dimensions"]["financial_cost"]["available"] == 60.0

    ledger, r2 = budget.reserve(ledger, "financial_cost", 40.0,
                                idempotency_key="k1", subject_identity="agent:1")
    assert r2["status"] == "IDEMPOTENT_REPLAY"
    # available decremented exactly ONCE
    assert ledger["dimensions"]["financial_cost"]["available"] == 60.0
    assert r2["reservation"]["reservation_id"] == r1["reservation"]["reservation_id"]


def test_over_reservation_flags_and_no_mutation_ac095_096():
    # AC-0006-095..096: amount > available => BUDGET_OVERCOMMITMENT, ledger unchanged
    ledger = budget.new_ledger(_full_budget_vector())
    before = dict(ledger["dimensions"]["financial_cost"])
    ledger, res = budget.reserve(ledger, "financial_cost", 150.0,
                                 idempotency_key="k-over",
                                 subject_identity="agent:1")
    assert res["status"] == "OVERCOMMITMENT"
    assert BUDGET_OVERCOMMITMENT in _k(res["findings"])
    assert res["reservation"] is None
    # ledger unchanged
    assert ledger["dimensions"]["financial_cost"] == before
    assert ledger["reservations"] == {}


def test_conservation_after_reserve_consume_and_broken_ledger_ac097():
    # AC-0006-097: after reserve+consume, consumed+reserved <= total => no findings
    ledger = budget.new_ledger(_full_budget_vector())
    ledger, r = budget.reserve(ledger, "model_cost", 50.0,
                               idempotency_key="k2", subject_identity="agent:1")
    rid = r["reservation"]["reservation_id"]
    ledger, _ = budget.consume(ledger, rid, 30.0)
    s = ledger["dimensions"]["model_cost"]
    assert s["consumed"] + s["reserved"] <= s["total"]
    assert budget.conservation_findings(ledger) == []

    # force a broken ledger: consumed+reserved > total
    ledger["dimensions"]["model_cost"]["consumed"] = 80.0
    ledger["dimensions"]["model_cost"]["reserved"] = 40.0
    fs = budget.conservation_findings(ledger)
    assert BUDGET_CONSERVATION_FAILURE in _k(fs)


def test_parent_child_conservation_ac098():
    # AC-0006-098: child allocations summing above parent available => failure
    parent_available = {"financial_cost": 100.0}
    children = [{"allocation": {"financial_cost": 70.0}},
                {"allocation": {"financial_cost": 50.0}}]  # sum 120 > 100
    fs = budget.parent_child_conservation(parent_available, children)
    assert BUDGET_CONSERVATION_FAILURE in _k(fs)

    # within available => none
    ok = budget.parent_child_conservation(
        {"financial_cost": 100.0},
        [{"allocation": {"financial_cost": 40.0}},
         {"allocation": {"financial_cost": 30.0}}])
    assert ok == []


def test_time_conservation_parallel_ac099():
    # AC-0006-099: parallel=True — a child deadline AFTER parent => finding;
    # children within parent deadline => none (summed durations not required)
    fs = budget.time_conservation(100, [50, 120, 90], parallel=True)
    assert BUDGET_CONSERVATION_FAILURE in _k(fs)
    # each within parent deadline, even though summed durations exceed 100
    ok = budget.time_conservation(100, [90, 90, 90], parallel=True)
    assert ok == []


def test_concurrent_over_reservation_detected_ac100():
    # AC-0006-100: two reservations exceeding total => second over-reserves
    ledger = budget.new_ledger(_full_budget_vector())  # total 100
    ledger, r1 = budget.reserve(ledger, "tool_call_quota", 70.0,
                                idempotency_key="c1", subject_identity="a")
    assert r1["status"] == "RESERVED"
    ledger, r2 = budget.reserve(ledger, "tool_call_quota", 50.0,
                                idempotency_key="c2", subject_identity="b")
    assert r2["status"] == "OVERCOMMITMENT"
    assert BUDGET_OVERCOMMITMENT in _k(r2["findings"])
    # first reservation intact; conservation still holds
    assert ledger["dimensions"]["tool_call_quota"]["reserved"] == 70.0
    assert budget.conservation_findings(ledger) == []


# ---------------------------------------------------------------------------
# Risk vector + non-compensatory control floor — AC-0006-101..107
# ---------------------------------------------------------------------------
def test_control_floor_non_compensatory_ac101_103():
    # AC-0006-101..103: dims are separate; the floor is the non-compensatory MAX.
    # One CRITICAL dim (CC4) among otherwise-LOW dims is NOT averaged down.
    rv = {"operational": "LOW", "financial": "LOW", "privacy": "LOW",
          "security": "CRITICAL", "legal": "LOW", "rights": "LOW",
          "reputation": "LOW", "irreversibility": "NONE"}
    assert risk.control_floor(rv) == "CC4"
    assert risk.no_compensation(rv) is True


def test_unknown_maps_to_cc3_not_cc1_ac104():
    # AC-0006-104: UNKNOWN risk maps to CC3 (fail-closed), never CC1
    assert risk.RISK_TO_CC["UNKNOWN"] == "CC3"
    rv = {d: "NONE" for d in ("operational", "financial", "privacy", "security",
                              "legal", "rights", "reputation", "irreversibility")}
    rv["privacy"] = "UNKNOWN"
    assert risk.control_floor(rv) == "CC3"


def test_expected_loss_cvar_only_when_calibrated_ac105_106():
    # AC-0006-105..106: uncalibrated scenarios => NOT_CALIBRATED status
    uncalibrated = [{"probability": 0.5, "loss": "SEVERE"}]  # ordinal loss
    assert risk.expected_loss(uncalibrated)["status"] == "NOT_CALIBRATED"
    assert risk.cvar(uncalibrated, 0.95)["status"] == "NOT_CALIBRATED"
    # calibrated => a numeric advisory value
    calibrated = [{"probability": 0.5, "loss": 100.0},
                  {"probability": 0.5, "loss": 0.0}]
    el = risk.expected_loss(calibrated)
    assert el["status"] == "CALIBRATED" and el["value"] == 50.0
    assert el["advisory"] is True


def test_risk_findings_quantitative_not_calibrated_ac107():
    # AC-0006-107: a quantitative model requested but uncalibrated =>
    # QUANTITATIVE_RISK_NOT_CALIBRATED (advisory), floor still stands
    rv = {"financial": "HIGH"}
    fs = risk.risk_findings(
        rv, expected_loss_scenarios=[{"probability": 0.5, "loss": "BIG"}])
    assert QUANTITATIVE_RISK_NOT_CALIBRATED in _k(fs)
    # no scenarios requested => no quantitative finding
    assert risk.risk_findings(rv) == []


# ---------------------------------------------------------------------------
# Approval topology + context-bound token — AC-0006-108..125
# ---------------------------------------------------------------------------
def _payment_action():
    return {"effect_class": "PAYMENT",
            "target": {"target_type": "account", "target_id": "acct-1",
                       "amount": 100},
            "parameters": {"memo": "invoice-42"}}


def test_approval_floor_conservative_and_class_sufficient_ac108_110():
    # AC-0006-108..110: a PAYMENT / high-risk context yields a high class;
    # class_sufficient is a rank compare
    assert approval.approval_floor({"effect_class": "PAYMENT"}) == "A5"
    assert approval.approval_floor({"risk_level": "CRITICAL"}) == "A5"
    assert approval.approval_floor({"effect_class": "READ"}) == "A0"
    assert approval.class_sufficient("A5", "A4") is True
    assert approval.class_sufficient("A2", "A4") is False


def test_issue_token_binds_material_context_ac111_118():
    # AC-0006-111..118: token binds work_instance_hash / action / target /
    # material params / risk snapshot, and carries expiry + uses
    action = _payment_action()
    token = approval.issue_token(
        work_instance_hash="wih-1", action=action, required_class="A5",
        approver_id="approver:1", approver_class="A5", issued_at=0,
        expires_at=1000, maximum_uses=1,
        risk_snapshot={"financial": "HIGH"}, token_id="tok-1")
    for field in ("work_instance_hash", "action_fingerprint",
                  "target_fingerprint", "material_parameters_hash",
                  "risk_snapshot_hash", "expires_at", "maximum_uses",
                  "current_uses", "integrity_hash"):
        assert field in token
    assert token["work_instance_hash"] == "wih-1"
    # a valid token validates clean
    ok, fs = approval.validate_token(token, action=action,
                                     work_instance_hash="wih-1", now=10)
    assert ok is True and fs == []


def test_changed_target_context_mismatch_ac119():
    # AC-0006-119: a changed target => APPROVAL_CONTEXT_MISMATCH, token void
    action = _payment_action()
    token = approval.issue_token(
        work_instance_hash="wih-1", action=action, required_class="A5",
        approver_id="approver:1", approver_class="A5", issued_at=0,
        expires_at=1000, token_id="tok-1")
    changed = _payment_action()
    changed["target"]["target_id"] = "acct-999"   # different target
    ok, fs = approval.validate_token(token, action=changed,
                                     work_instance_hash="wih-1", now=10)
    assert ok is False
    assert APPROVAL_CONTEXT_MISMATCH in _k(fs)


def test_changed_material_param_context_mismatch_ac120():
    # AC-0006-120: a changed amount / material parameter => APPROVAL_CONTEXT_MISMATCH
    action = _payment_action()
    token = approval.issue_token(
        work_instance_hash="wih-1", action=action, required_class="A5",
        approver_id="approver:1", approver_class="A5", issued_at=0,
        expires_at=1000, token_id="tok-1")
    changed = _payment_action()
    changed["parameters"]["memo"] = "invoice-999"   # material param changed
    ok, fs = approval.validate_token(token, action=changed,
                                     work_instance_hash="wih-1", now=10)
    assert ok is False
    assert APPROVAL_CONTEXT_MISMATCH in _k(fs)


def test_provided_class_below_required_ac121():
    # AC-0006-121: approver class below required => APPROVAL_CLASS_INSUFFICIENT
    action = _payment_action()
    token = approval.issue_token(
        work_instance_hash="wih-1", action=action, required_class="A5",
        approver_id="approver:1", approver_class="A1", issued_at=0,
        expires_at=1000, token_id="tok-1")
    ok, fs = approval.validate_token(token, action=action,
                                     work_instance_hash="wih-1", now=10)
    assert ok is False
    assert APPROVAL_CLASS_INSUFFICIENT in _k(fs)


def test_no_self_approval_ac122_123():
    # AC-0006-122..123: approver == proposer (independence required) =>
    # SELF_APPROVAL_DETECTED
    fs = approval.no_self_approval(proposer="id:x", planner="id:y",
                                   executor="id:z", approver="id:x",
                                   verifier="id:v", independence_required=True)
    assert SELF_APPROVAL_DETECTED in _k(fs)
    # an independent approver is clean
    ok = approval.no_self_approval(proposer="id:x", planner="id:y",
                                   executor="id:z", approver="id:w",
                                   verifier="id:v", independence_required=True)
    assert ok == []


def test_quorum_not_satisfied_ac124_125():
    # AC-0006-124..125: too few approvers, or non-distinct identities => not ok
    ok, fs = approval.quorum_satisfied(
        [{"approver_id": "a1", "role": "risk"}],
        {"policy_id": "q1", "number_of_approvers": 2})
    assert ok is False
    assert APPROVAL_CLASS_INSUFFICIENT in _k(fs)

    ok2, fs2 = approval.quorum_satisfied(
        [{"approver_id": "a1"}, {"approver_id": "a1"}],   # not distinct
        {"policy_id": "q2", "number_of_approvers": 2})
    assert ok2 is False
    assert SELF_APPROVAL_DETECTED in _k(fs2)


# ---------------------------------------------------------------------------
# Plan binding — AC-0006-126..130
# ---------------------------------------------------------------------------
def _plan_work_order():
    return {"work_order_id": "WO-P", "tenant_id": "t1",
            "canonical_goal": "reconcile invoices",
            "allowed_scope": ["ledger"], "constraints": [],
            "outcome_contract": {"goal": "reconciled"},
            "budget_vector": {"financial_cost": 100.0},
            "accountable_owner_id": ROOT}


def test_bind_plan_references_hashes_ac126_127():
    # AC-0006-126..127: bind_plan references semantic + instance hashes
    wo = _plan_work_order()
    plan_env = {"plan_id": "P1", "steps": [{"action": "read"}]}
    rec = plan.bind_plan(wo, plan_env)
    assert rec["binding_kind"] == "PLAN_BINDING"
    assert rec["semantic_work_hash"]
    assert rec["work_instance_hash"]
    assert rec["non_authoritative"] is True

    # a plan carrying the correct identities validates clean
    good_plan = {"plan_id": "P1",
                 "semantic_work_hash": rec["semantic_work_hash"],
                 "work_instance_hash": rec["work_instance_hash"]}
    assert plan.validate_plan_binding(wo, good_plan) == []


def test_validate_plan_binding_flags_wrong_hash_and_grants_ac128_129():
    # AC-0006-128..129: wrong hashes => finding; a plan carrying a grant
    # (plan is not authority) => finding
    wo = _plan_work_order()
    wrong = {"plan_id": "P2", "semantic_work_hash": "WRONG",
             "work_instance_hash": "WRONG"}
    fs = plan.validate_plan_binding(wo, wrong)
    assert INVALID_WORK_SCHEMA in _k(fs)

    rec = plan.bind_plan(wo, {"plan_id": "P3"})
    granting = {"plan_id": "P3",
                "semantic_work_hash": rec["semantic_work_hash"],
                "work_instance_hash": rec["work_instance_hash"],
                "granted_capability": ["PAYMENT"]}   # plan is not authority
    fs2 = plan.validate_plan_binding(wo, granting)
    assert INVALID_WORK_SCHEMA in _k(fs2)


def test_material_plan_change_reopens_revalidations_ac130():
    # AC-0006-130: a material change (steps/targets/effects/budgets) =>
    # material True + the 4 revalidations
    old = {"steps": [{"action": "read"}], "targets": ["a"],
           "effects": ["READ"], "budgets": {"financial_cost": 100.0}}
    new = {"steps": [{"action": "read"}, {"action": "write"}],  # changed
           "targets": ["a"], "effects": ["READ"],
           "budgets": {"financial_cost": 100.0}}
    result = plan.material_plan_change(old, new)
    assert result["material"] is True
    assert "steps" in result["changed_fields"]
    assert set(result["requires"]) == {"impact_analysis", "budget_revalidation",
                                       "lease_revalidation", "approval_revalidation"}
    # no change => not material
    same = plan.material_plan_change(old, dict(old))
    assert same["material"] is False and same["requires"] == []


# ---------------------------------------------------------------------------
# Goal drift — hard + soft — AC-0006-131..140
# ---------------------------------------------------------------------------
def _drift_base():
    return {"work_order_id": "WO-D", "tenant_id": "t1",
            "privacy_purpose": "billing",
            "outcome_contract": {"goal": "x"},
            "capability_ceiling": ["read"]}


def test_hard_drift_tenant_change_ac131():
    # AC-0006-131: tenant change => HARD_GOAL_DRIFT
    base = _drift_base()
    cur = dict(base, tenant_id="t2")
    fs = drift.hard_drift(base, cur)
    assert HARD_GOAL_DRIFT in _k(fs)


def test_hard_drift_purpose_change_ac132():
    # AC-0006-132: purpose change => HARD_GOAL_DRIFT
    base = _drift_base()
    cur = dict(base, privacy_purpose="marketing")
    fs = drift.hard_drift(base, cur)
    assert HARD_GOAL_DRIFT in _k(fs)


def test_hard_drift_forbidden_scope_entry_ac133():
    # AC-0006-133: entering baseline forbidden scope => HARD_GOAL_DRIFT
    base = dict(_drift_base(), forbidden_scope=["payroll"])
    cur = dict(_drift_base(), forbidden_scope=["payroll"],
               allowed_scope=["payroll"])
    fs = drift.hard_drift(base, cur)
    assert HARD_GOAL_DRIFT in _k(fs)


def test_hard_drift_capability_ceiling_exceeded_ac134():
    # AC-0006-134: capability-ceiling violation => HARD_GOAL_DRIFT
    base = _drift_base()
    cur = dict(base, capability_ceiling=["read", "write"])   # exceeds ceiling
    fs = drift.hard_drift(base, cur)
    assert HARD_GOAL_DRIFT in _k(fs)


def test_hard_drift_silent_outcome_redefinition_ac135_136():
    # AC-0006-135..136: silent outcome redefinition (no approved replan) =>
    # HARD_GOAL_DRIFT
    base = _drift_base()
    cur = dict(base, outcome_contract={"goal": "y"})   # redefined, no approval
    fs = drift.hard_drift(base, cur)
    assert HARD_GOAL_DRIFT in _k(fs)
    # an approved replan clears the outcome-redefinition trigger
    cur_ok = dict(base, outcome_contract={"goal": "y"}, approved_replan=True)
    assert HARD_GOAL_DRIFT not in _k(drift.hard_drift(base, cur_ok))


def test_soft_drift_score_band_and_jaccard_ac137_139():
    # AC-0006-137..139: soft_drift returns score + band; both-empty jaccard == 0.0
    assert drift.scope_jaccard([], []) == 0.0
    assert drift.scope_jaccard(["a"], ["a", "b"]) == pytest.approx(0.5)
    base = {"allowed_scope": ["a", "b"]}
    cur = {"allowed_scope": ["a", "c"]}
    soft = drift.soft_drift(base, cur)
    assert "score" in soft and "band" in soft
    assert 0.0 <= soft["score"] <= 1.0
    assert soft["band"] in ("ALIGNED", "DRIFT_OBSERVED", "PAUSE_AND_REPLAN",
                            "BLOCK_AND_ESCALATE")


def test_low_soft_does_not_suppress_hard_ac140():
    # AC-0006-140: drift_findings runs hard predicates FIRST — a hard trigger with
    # a low soft score still yields HARD_GOAL_DRIFT
    base = _drift_base()
    cur = dict(base, tenant_id="t2")   # hard trigger; tenant is not a soft signal
    soft = drift.soft_drift(base, cur)
    assert soft["band"] == "ALIGNED"   # soft score is low
    fs = drift.drift_findings(base, cur)
    assert HARD_GOAL_DRIFT in _k(fs)


# ---------------------------------------------------------------------------
# Purpose / scope / hidden-work binding — AC-0006-141..144
# ---------------------------------------------------------------------------
def test_purpose_binding_flags_incompatible_access_ac141_142():
    # AC-0006-141..142: a purpose-incompatible access => PURPOSE_BINDING_FAILURE
    work = {"privacy_purpose": "billing"}
    accesses = [{"access_id": "acc1", "purpose": "marketing"},   # incompatible
                {"access_id": "acc2", "purpose": "billing"}]     # compatible
    fs = purpose.purpose_binding_findings(accesses, work)
    assert PURPOSE_BINDING_FAILURE in _k(fs)
    assert len(fs) == 1   # only the incompatible access

    # memory/convenience can never manufacture a new purpose
    mem = [{"access_id": "acc3", "purpose": "marketing", "source": "memory"}]
    assert PURPOSE_BINDING_FAILURE in _k(
        purpose.purpose_binding_findings(mem, work))


def test_hidden_work_detected_ac143():
    # AC-0006-143: an executed step with no admitted counterpart =>
    # HIDDEN_WORK_DETECTED
    admitted = [{"step_id": "s1", "action": "read", "target": "ledger"}]
    executed = [{"step_id": "s1", "action": "read", "target": "ledger"},
                {"step_id": "s2", "action": "write", "target": "payroll"}]
    fs = purpose.hidden_work(admitted, executed)
    assert HIDDEN_WORK_DETECTED in _k(fs)
    assert len(fs) == 1
    # execution matching the admitted plan is clean
    assert purpose.hidden_work(admitted, admitted) == []


def test_least_authority_path_returns_preferred_ac144():
    # AC-0006-144: least_authority_path returns a preferred (narrowest) plan
    plans = [{"plan_id": "wide", "effect_classes": ["READ", "PAYMENT"],
              "targets": ["a", "b"]},
             {"plan_id": "narrow", "effect_classes": ["READ"],
              "targets": ["a"]}]
    result = purpose.least_authority_path(plans)
    assert result["preferred_plan_id"] == "narrow"
    assert result["dominance"] == "STRICT"

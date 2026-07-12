"""SP0006 adversarial mutation campaign (§20.16, AC-0006-196).

Each mutation injects one violation of a governed-work invariant into an
otherwise-clean structure and asserts the kernel KILLS it. The dual of the green
baseline: it proves the gates are not vacuous. 16 mutants, one per §20.16 row.
"""
from __future__ import annotations

import copy

import pytest

from tools.governed_work.loader import load_program
from tools.governed_work.validate import validate_all
from tools.governed_work.intent import validate_candidate_intent
from tools.governed_work.workorder import validate_work_order
from tools.governed_work.lease import validate_child_lease, is_attenuation, attenuate
from tools.governed_work.delegation import has_cycle, validate_delegation
from tools.governed_work.budget import new_ledger, reserve
from tools.governed_work.approval import issue_token, validate_token, no_self_approval
from tools.governed_work.drift import drift_findings
from tools.governed_work.cancellation import new_action_allowed, unknown_outcome_findings
from tools.governed_work.outcome import artifact_vs_outcome_findings, verify_outcome
from tools.governed_work.accountability import conservation_findings
from tools.governed_work.recurrence import reauthorize
from tools.governed_work.envelope import work_proof_envelope
from tools.governed_work.model import (
    CONTEXT_USED_AS_AUTHORITY, MEMORY_USED_AS_AUTHORITY,
    DELEGATION_AUTHORITY_AMPLIFICATION, LEASE_ATTENUATION_FAILURE,
    DELEGATION_CYCLE_DETECTED, BUDGET_OVERCOMMITMENT, APPROVAL_CONTEXT_MISMATCH,
    SELF_APPROVAL_DETECTED, HARD_GOAL_DRIFT, UNKNOWN_OUTCOME_RECONCILIATION_REQUIRED,
    OUTPUT_NOT_OUTCOME, ACCOUNTABILITY_CHAIN_BROKEN,
    RECURRENCE_REAUTHORIZATION_FAILED, INVALID_WORK_SCHEMA)


def _k(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


@pytest.fixture()
def prog():
    return load_program()


def _root_lease():
    return {"lease_id": "L-root", "tenant_id": "t", "work_order_id": "W",
            "subject_identity": "root", "purpose": "p",
            "targets": ["a", "b"], "allowed_operations": ["read", "draft"],
            "effect_classes": ["READ", "DRAFT"], "data_classes": ["invoice"],
            "risk_ceiling": {"financial": "LOW"}, "cost_ceiling": {"x": 5},
            "expires_at": "2026-12-31", "maximum_uses": 10, "current_uses": 0,
            "revocation_state": "ACTIVE"}


# M1 — a message grants authority
def test_m1_message_grants_authority_killed():
    ci = {"candidate_intent_id": "c", "tenant_id": "t", "requester_id": "r",
          "source_surface": "slack", "authority": {"grant": "all"}}
    assert INVALID_WORK_SCHEMA in _k(validate_candidate_intent(ci))


# M2 — memory grants approval/authority
def test_m2_memory_grants_authority_killed():
    w = {"work_order_id": "W", "tenant_id": "t", "requester_id": "r",
         "canonical_goal": {"x": 1}, "allowed_scope": {}, "privacy_purpose": "p",
         "accountable_owner_id": "o", "outcome_contract": {"c": 1},
         "authority_from_memory": True}
    assert MEMORY_USED_AS_AUTHORITY in _k(validate_work_order(w))


# M3 — context grants authority
def test_m3_context_grants_authority_killed():
    w = {"work_order_id": "W", "tenant_id": "t", "requester_id": "r",
         "canonical_goal": {"x": 1}, "allowed_scope": {}, "privacy_purpose": "p",
         "accountable_owner_id": "o", "outcome_contract": {"c": 1},
         "authority_from_context": True}
    assert CONTEXT_USED_AS_AUTHORITY in _k(validate_work_order(w))


# M4 — child receives a broader lease
def test_m4_child_broader_lease_killed():
    parent = _root_lease()
    child = attenuate(parent, {"lease_id": "L-c", "subject_identity": "c",
                               "allowed_operations": ["read", "draft", "send"]})
    ok, _ = is_attenuation(parent, child)
    assert not ok
    assert LEASE_ATTENUATION_FAILURE in _k(validate_child_lease(parent, child))
    assert DELEGATION_AUTHORITY_AMPLIFICATION in _k(validate_child_lease(parent, child))


# M5 — child extends expiry
def test_m5_child_extends_expiry_killed():
    parent = _root_lease()
    child = attenuate(parent, {"lease_id": "L-c", "subject_identity": "c",
                               "expires_at": "2027-12-31"})
    assert LEASE_ATTENUATION_FAILURE in _k(validate_child_lease(parent, child))


# M6 — delegation cycle
def test_m6_delegation_cycle_killed():
    edges = [{"parent_identity": "A", "child_identity": "B", "work_order_id": "W"},
             {"parent_identity": "B", "child_identity": "A", "work_order_id": "W"}]
    assert has_cycle(edges)
    ids = [{"execution_identity_id": "A", "work_order_id": "W", "role": "x"},
           {"execution_identity_id": "B", "work_order_id": "W", "role": "x",
            "parent_identity_id": "A", "delegation_depth": 1}]
    f = validate_delegation({"work_order_id": "W", "capability_ceiling": {}},
                            edges, ids, {})
    assert DELEGATION_CYCLE_DETECTED in _k(f)


# M7 — double budget reservation over total
def test_m7_budget_overcommit_killed():
    led = new_ledger({"tool_call_quota": {"total": 5}})
    led, r1 = reserve(led, "tool_call_quota", 4, idempotency_key="k1",
                      subject_identity="s")
    led, r2 = reserve(led, "tool_call_quota", 4, idempotency_key="k2",
                      subject_identity="s")
    # second reservation exceeds remaining -> overcommit finding
    findings = r2 if isinstance(r2, list) else r2.get("findings", [])
    assert BUDGET_OVERCOMMITMENT in {getattr(f, "kind", None) for f in findings} \
        or BUDGET_OVERCOMMITMENT in _k(findings)


# M8 — approval reused after target change
def test_m8_approval_replay_after_target_change_killed():
    action = {"action_type": "send", "target": {"target_id": "X"},
              "parameters": {"amount": 100}}
    tok = issue_token(work_instance_hash="wih", action=action,
                      required_class="A2", approver_id="o", approver_class="A2",
                      issued_at="2026-03-05", expires_at="2026-03-06")
    changed = {"action_type": "send", "target": {"target_id": "Y"},
               "parameters": {"amount": 100}}
    ok, f = validate_token(tok, action=changed, work_instance_hash="wih",
                           now="2026-03-05T12:00:00Z")
    assert not ok and APPROVAL_CONTEXT_MISMATCH in _k(f)


# M9 — self-approval
def test_m9_self_approval_killed():
    f = no_self_approval(proposer="u1", planner="u1", executor="u1",
                         approver="u1", verifier="u2", independence_required=True)
    assert SELF_APPROVAL_DETECTED in _k(f)


# M10 — hard drift hidden by low soft score
def test_m10_hard_drift_not_hidden_by_low_score():
    base = {"tenant_id": "t", "privacy_purpose": "billing",
            "allowed_scope": {"target": ["a"]}, "forbidden_scope": {}}
    cur = {"tenant_id": "OTHER", "privacy_purpose": "billing",
           "allowed_scope": {"target": ["a"]}, "forbidden_scope": {}}
    assert HARD_GOAL_DRIFT in _k(drift_findings(base, cur))


# M11 — recurring run reuses old approval / fails reauthorization
def test_m11_recurrence_reuse_old_approval_killed():
    contract = {"recurrence_contract_id": "RC", "cadence": "MONTHLY",
                "purpose": "p", "scope_ceiling": {}, "capability_ceiling": {},
                "per_run_budget": {}, "expiry": "2026-12-31",
                "termination_policy": {},
                "reauthorization_requirements": ["tenant", "approvals"]}
    instance = {"recurrence_instance": 2, "work_instance_hash": "new"}
    # current is missing the required 'approvals' revalidation
    ok, f = reauthorize(contract, instance, {"tenant": True})
    assert not ok and RECURRENCE_REAUTHORIZATION_FAILED in _k(f)


# M12 — cancellation permits a new action
def test_m12_cancellation_blocks_new_action():
    assert new_action_allowed("OPEN") in (True, False)
    assert not new_action_allowed("NEW_ACTIONS_BLOCKED")
    assert not new_action_allowed("LEASES_REVOKING")


# M13 — unknown outcome retried blindly (non-idempotent)
def test_m13_unknown_outcome_blind_retry_killed():
    f = unknown_outcome_findings([{"unknown_id": "u", "effect_idempotent": False,
                                   "retry_requested": True}])
    assert UNKNOWN_OUTCOME_RECONCILIATION_REQUIRED in _k(f)


# M14 — artifact marked as verified outcome
def test_m14_artifact_not_outcome_killed():
    claim = {"work_order_id": "W", "claims_completion": True,
             "evidence_kinds": ["ARTIFACT_PRODUCED"], "verified_predicates": []}
    assert OUTPUT_NOT_OUTCOME in _k(artifact_vs_outcome_findings(claim))


# M15 — accountable owner lost through delegation
def test_m15_accountability_lost_killed():
    w = {"work_order_id": "W", "accountable_owner_id": "owner"}
    edges = [{"delegation_id": "d", "parent_identity": "r", "child_identity": "c",
              "accountable_owner_id": "SOMEONE_ELSE"}]
    assert ACCOUNTABILITY_CHAIN_BROKEN in _k(conservation_findings(w, edges))


# M16 — proof hash excludes leases (envelope must change when leases change)
def test_m16_proof_envelope_binds_leases():
    w = {"work_order_id": "W", "semantic_work_hash": "s", "work_instance_hash": "i",
         "accountable_owner_id": "o"}
    h0 = work_proof_envelope(w, leases=[{"lease_id": "L1"}])["envelope_hash"]
    h1 = work_proof_envelope(w, leases=[{"lease_id": "L2"}])["envelope_hash"]
    assert h0 != h1   # the lease set is bound into the proof


# campaign completeness: the clean program is valid (mutants are the only failures)
def test_unmutated_program_is_valid(prog):
    assert validate_all(prog).valid

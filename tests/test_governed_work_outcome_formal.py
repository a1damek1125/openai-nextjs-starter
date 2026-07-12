"""FINALIS SP0006 — Recurrence, Cancellation Barrier, Outcome Verification,
Governed-Work State Machine, Bounded Model Checking, and Proof Envelopes.

Covers AC-0006-146..195. Imports ONLY from tools.governed_work.*.
"""
from __future__ import annotations

from tools.governed_work import recurrence
from tools.governed_work import cancellation
from tools.governed_work import outcome
from tools.governed_work import statemachine
from tools.governed_work import modelcheck
from tools.governed_work import envelope
from tools.governed_work.model import (
    RECURRENCE_REAUTHORIZATION_FAILED, CANCELLATION_BARRIER_INCOMPLETE,
    UNKNOWN_OUTCOME_RECONCILIATION_REQUIRED, OUTCOME_EVIDENCE_INCOMPLETE,
    OUTCOME_DISPUTED, OUTCOME_DEFEATER_OPEN, OUTPUT_NOT_OUTCOME,
    SELF_REPORT_AS_SOLE_OUTCOME_ORACLE, INVALID_STATE_TRANSITION,
    PROOF_ENVELOPE_MISMATCH, OUTCOME_STATES, OUTCOME_PREDICATE_TYPES)


def _k(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


# --- fixtures ---------------------------------------------------------------

def _full_contract():
    return {
        "contract_id": "C-DAILY-RECON",
        "cadence": "DAILY",
        "purpose": "reconcile_ledger",
        "scope_ceiling": {"targets": ["ledger:acme"]},
        "capability_ceiling": {"allowed_operations": ["read", "reconcile"]},
        "per_run_budget": {"financial_cost": 10, "tool_call_quota": 5},
        "expiry": "2027-01-01T00:00:00Z",
        "termination_policy": {"on": "expiry_or_owner_stop"},
        "work_skeleton": {"canonical_goal": "reconcile", "tenant_id": "t1"},
    }


# ===========================================================================
# AC-0006-146..148 — recurring contract validates; instance is separate;
# instance_hash differs per occurrence.
# ===========================================================================

def test_ac146_recurring_contract_validates():
    # AC-0006-146: a fully-bounded recurring contract has no findings.
    assert recurrence.validate_contract(_full_contract()) == []


def test_ac147_recurring_instance_is_separate_from_contract():
    # AC-0006-147: an occurrence produces a NEW work instance, distinct identity.
    c = _full_contract()
    occ = {"occurrence_id": "o1", "sequence": 1, "scheduled_time": "2026-07-01"}
    inst = recurrence.new_instance(c, occ)
    assert inst["recurrence_contract_ref"] == c["contract_id"]
    assert inst["work_order_id"] != c["contract_id"]
    assert inst["requires_reauthorization"] is True
    assert inst["work_instance_hash"] == inst["instance_hash"]
    assert inst["recurrence_instance"]["occurrence_id"] == "o1"


def test_ac148_instance_hash_differs_per_occurrence():
    # AC-0006-148: distinct occurrences (different sequence/time) -> distinct hash.
    c = _full_contract()
    occ1 = {"occurrence_id": "o1", "sequence": 1, "scheduled_time": "2026-07-01"}
    occ2 = {"occurrence_id": "o2", "sequence": 2, "scheduled_time": "2026-07-02"}
    assert recurrence.instance_hash(c, occ1) != recurrence.instance_hash(c, occ2)


# ===========================================================================
# AC-0006-149..151 — per-run reauthorization revalidates.
# ===========================================================================

def test_ac149_150_reauthorize_missing_check_fails():
    # AC-0006-149/150: a required reauthorization check missing in `current`
    # blocks the run with RECURRENCE_REAUTHORIZATION_FAILED, ok False.
    c = dict(_full_contract(),
             reauthorization_requirements=["tenant", "policy", "approvals"])
    occ = {"occurrence_id": "o1", "sequence": 1, "scheduled_time": "2026-07-01"}
    inst = recurrence.new_instance(c, occ)
    current = {"tenant": True, "policy": True}  # 'approvals' missing
    ok, findings = recurrence.reauthorize(c, inst, current)
    assert ok is False
    assert RECURRENCE_REAUTHORIZATION_FAILED in _k(findings)


def test_ac151_old_approval_token_cannot_authorize_new_run():
    # AC-0006-151: an approval token bound to a PRIOR work_instance_hash can
    # never authorize a new run.
    c = dict(_full_contract(), reauthorization_requirements=["tenant"])
    occ = {"occurrence_id": "o2", "sequence": 2, "scheduled_time": "2026-07-02"}
    inst = recurrence.new_instance(c, occ)
    current = {
        "tenant": True,
        "approval_tokens": [{"approval_id": "a-old",
                             "work_instance_hash": "PRIOR-OCCURRENCE-HASH"}],
    }
    ok, findings = recurrence.reauthorize(c, inst, current)
    assert ok is False
    assert RECURRENCE_REAUTHORIZATION_FAILED in _k(findings)


# ===========================================================================
# AC-0006-152..159 — cancellation barrier protocol.
# ===========================================================================

def test_ac152_153_new_action_allowed_only_while_open():
    # AC-0006-152/153: once past OPEN, no new action may start.
    assert cancellation.new_action_allowed("OPEN") is True
    assert cancellation.new_action_allowed("NEW_ACTIONS_BLOCKED") is False
    assert cancellation.new_action_allowed("IN_FLIGHT_RECONCILING") is False


def _barrier_state():
    return {
        "work_order_id": "W1",
        "leases": [{"lease_id": "l1", "revocable": True}],
        "approvals": [{"approval_id": "ap1", "consumed": False}],
        "unknown_outcomes": [{"outcome_id": "u1", "reconciled": False}],
        "in_flight": [{"action_id": "f1", "classification": "COMPLETED"}],
        "irreversible_effects": [{"effect_id": "e1"}],
    }


def test_ac154_155_barrier_revokes_leases_and_invalidates_approvals():
    # AC-0006-154/155: barrier revokes eligible leases + invalidates approvals.
    r = cancellation.run_barrier(_barrier_state())
    assert r["revoked_leases"] == ["l1"]
    assert r["invalidated_approvals"] == ["ap1"]
    assert r["new_actions_blocked"] is True


def test_ac156_157_unreconciled_unknown_blocks_cancellation():
    # AC-0006-156/157: unreconciled unknown outcomes -> can_cancel False and
    # CANCELLATION_BARRIER_INCOMPLETE.
    state = _barrier_state()
    r = cancellation.run_barrier(state)
    assert r["can_cancel"] is False
    assert CANCELLATION_BARRIER_INCOMPLETE in _k(cancellation.barrier_findings(state))


def test_ac158_irreversible_effects_recorded():
    # AC-0006-158: irreversible completed effects are recorded by the barrier.
    r = cancellation.run_barrier(_barrier_state())
    assert r["recorded_irreversible"] == ["e1"]


def test_ac159_quarantine_never_self_releases():
    # AC-0006-159: quarantine release requires an authorized independent decision.
    q_bad = {"subject": "agentX", "requested_by": "reqY", "imposed_by": "impZ",
             "independent_release_decision": None}
    assert cancellation.quarantine_release_allowed(q_bad) is False
    q_ok = {"subject": "agentX", "requested_by": "reqY", "imposed_by": "impZ",
            "independent_release_decision": {"authorized": True,
                                             "approver": "independentW"}}
    assert cancellation.quarantine_release_allowed(q_ok) is True


# ===========================================================================
# AC-0006-160..166 — outcome contract + predicate families.
# ===========================================================================

def _full_outcome_contract(**over):
    c = {
        "contract_id": "OC1",
        "expected_outcomes": [{"outcome_id": "eo1"}],
        "acceptance_predicates": [
            {"predicate_id": "p1", "predicate_type": "ARTIFACT_EXISTS"},
            {"predicate_id": "p2", "predicate_type": "SCHEMA_VALID"},
            {"predicate_id": "p3", "predicate_type": "SOURCE_COMPLETE"},
            {"predicate_id": "p4", "predicate_type": "NUMERICAL_RECONCILIATION"},
            {"predicate_id": "p5", "predicate_type": "TARGET_STATE_EQUALS"},
            {"predicate_id": "p6", "predicate_type": "NO_FORBIDDEN_EFFECT"},
        ],
        "verification_mode": "DETERMINISTIC",
        "completion_rule": "ALL",
    }
    c.update(over)
    return c


def test_ac160_166_outcome_contract_validates_with_predicate_families():
    # AC-0006-160..166: required fields + known predicate families validate.
    families = {"ARTIFACT_EXISTS", "SCHEMA_VALID", "SOURCE_COMPLETE",
                "NUMERICAL_RECONCILIATION", "TARGET_STATE_EQUALS",
                "NO_FORBIDDEN_EFFECT"}
    assert families <= OUTCOME_PREDICATE_TYPES
    assert outcome.validate_outcome_contract(_full_outcome_contract()) == []


# ===========================================================================
# AC-0006-167 — output is not outcome.
# ===========================================================================

def test_ac167_artifact_without_verified_predicate_is_not_verified():
    # AC-0006-167: only an artifact, no satisfied predicate -> not VERIFIED.
    contract = _full_outcome_contract()
    r = outcome.verify_outcome(contract, [])  # no evidence at all
    assert r["state"] != "VERIFIED"
    claim = {"work_order_id": "W", "claims_completion": True,
             "evidence_kinds": ["ARTIFACT_PRODUCED"], "verified_predicates": []}
    assert OUTPUT_NOT_OUTCOME in _k(outcome.artifact_vs_outcome_findings(claim))


# ===========================================================================
# AC-0006-168 — partial is not complete.
# ===========================================================================

def test_ac168_partial_verification():
    # AC-0006-168: some SATISFIED + some UNKNOWN -> PARTIALLY_VERIFIED.
    contract = {
        "contract_id": "OC2",
        "acceptance_predicates": [
            {"predicate_id": "p1", "predicate_type": "ARTIFACT_EXISTS"},
            {"predicate_id": "p2", "predicate_type": "SCHEMA_VALID"},
        ],
        "completion_rule": "ALL",
    }
    evidence = [{"predicate_id": "p1", "artifact_present": True,
                 "source": "repo", "verifier": "ci"}]
    r = outcome.verify_outcome(contract, evidence)
    assert r["state"] == "PARTIALLY_VERIFIED"
    assert r["unresolved_predicates"]  # non-empty
    assert "p2" in r["unresolved_predicates"]


# ===========================================================================
# AC-0006-169/170 — disputes and defeaters.
# ===========================================================================

def test_ac169_dispute_findings():
    # AC-0006-169: an open dispute -> OUTCOME_DISPUTED.
    disputes = [{"dispute_id": "d1", "outcome_id": "o1", "open": True}]
    assert OUTCOME_DISPUTED in _k(outcome.dispute_findings(disputes))


def test_ac170_defeater_findings():
    # AC-0006-170: an open defeater against a verified outcome -> DEFEATER_OPEN.
    defeaters = [{"defeater_id": "df1", "outcome_id": "o1",
                  "outcome_state": "VERIFIED", "open": True}]
    assert OUTCOME_DEFEATER_OPEN in _k(outcome.defeater_findings(defeaters))


# ===========================================================================
# AC-0006-171/172 — reopen via linked successor; supersession cannot resume.
# ===========================================================================

def test_ac171_reopen_by_defeater_linked_successor():
    # AC-0006-171: reopen via LINKED successor; original stays immutable.
    wo = {"work_order_id": "W1", "work_version": 1}
    succ = outcome.reopen_by_defeater(wo, {"defeater_id": "df1"})
    assert succ["reopened_by_defeater"] == "df1"
    assert succ["original_completion_immutable"] is True
    assert succ["successor_of"] == "W1"
    assert succ["work_order_id"] != "W1"


def test_ac172_supersede_cannot_resume():
    # AC-0006-172: superseded work references its replacement and cannot resume.
    s = outcome.supersede({"work_order_id": "W1"}, "W2")
    assert s["superseded_by"] == "W2"
    assert s["can_resume"] is False
    assert s["status"] == "SUPERSEDED"


# ===========================================================================
# AC-0006-173/174 — self-report can never be the sole oracle.
# ===========================================================================

def test_ac173_174_self_report_as_sole_oracle_blocked():
    # AC-0006-173/174: a CRITICAL outcome whose only oracle is AGENT_SELF_REPORT
    # -> SELF_REPORT_AS_SOLE_OUTCOME_ORACLE.
    contract = {
        "contract_id": "OCc",
        "critical": True,
        "acceptance_predicates": [
            {"predicate_id": "p1", "predicate_type": "ARTIFACT_EXISTS"}],
        "oracles": ["AGENT_SELF_REPORT"],
        "completion_rule": "ALL",
    }
    r = outcome.verify_outcome(contract, [])
    assert SELF_REPORT_AS_SOLE_OUTCOME_ORACLE in _k(r["findings"])


# ===========================================================================
# AC-0006-175 — UNKNOWN outcome distinct from failure.
# ===========================================================================

def test_ac175_blind_retry_of_non_idempotent_effect_flagged():
    # AC-0006-175: blind retry of a non-idempotent effect with an unknown
    # outcome -> UNKNOWN_OUTCOME_RECONCILIATION_REQUIRED.
    unknowns = [{"outcome_id": "u1", "effect_idempotent": False,
                 "retry_requested": True}]
    findings = cancellation.unknown_outcome_findings(unknowns)
    assert UNKNOWN_OUTCOME_RECONCILIATION_REQUIRED in _k(findings)


# ===========================================================================
# AC-0006-176..183 — governed work state machine.
# ===========================================================================

def test_ac176_177_valid_and_invalid_transitions():
    # AC-0006-176/177: valid edges accepted; an invalid edge is INVALID.
    assert statemachine.valid_transition("DRAFT", "NORMALIZING") is True
    assert statemachine.valid_transition("DRAFT", "RUNNING") is False
    assert INVALID_STATE_TRANSITION in _k(
        statemachine.validate_transition("DRAFT", "RUNNING"))


def test_ac178_179_ambiguous_conflicted_cannot_run():
    # AC-0006-178/179: AMBIGUOUS/CONFLICTED can never enter RUNNING.
    assert statemachine.valid_transition("AMBIGUOUS", "RUNNING") is False
    assert statemachine.valid_transition("CONFLICTED", "RUNNING") is False
    assert INVALID_STATE_TRANSITION in _k(
        statemachine.validate_run(["AMBIGUOUS", "RUNNING"]))
    assert statemachine.can_run("AMBIGUOUS") is False
    assert statemachine.can_run("CONFLICTED") is False


def test_ac180_181_terminal_states_cannot_resume():
    # AC-0006-180/181: EXPIRED/CANCELLED/SUPERSEDED have no executable outgoing.
    for terminal in ("EXPIRED", "CANCELLED", "SUPERSEDED"):
        outgoing = statemachine.TRANSITIONS[terminal]
        assert not (outgoing & statemachine.EXECUTABLE_STATES)
        assert statemachine.can_run(terminal) is False


def test_ac182_183_outcome_produced_is_not_verified_complete():
    # AC-0006-182/183: OUTCOME_PRODUCED must pass through OUTCOME_VERIFYING.
    assert statemachine.valid_transition(
        "OUTCOME_PRODUCED", "VERIFIED_COMPLETE") is False
    assert statemachine.valid_transition(
        "OUTCOME_PRODUCED", "OUTCOME_VERIFYING") is True


# ===========================================================================
# AC-0006-184..190 — bounded model checking.
# ===========================================================================

def test_ac184_explore_result_shape():
    # AC-0006-184: explore returns the expected honest result keys.
    initial, tf, iv = modelcheck.work_state_model()
    r = modelcheck.explore(initial, tf, iv)
    for key in ("explored", "verdict", "truncated", "counterexample"):
        assert key in r


def test_ac185_186_safe_models_hold():
    # AC-0006-185/186: every safe model in the suite verdict HOLDS.
    summary = modelcheck.run_all_models()
    for name, res in summary.items():
        assert res["verdict"] == modelcheck.HOLDS, name


def test_ac187_violating_model_yields_counterexample():
    # AC-0006-187: an amplification variant is caught VIOLATED with a path.
    initial, tf, iv = modelcheck.authority_monotonicity_model(violating=True)
    r = modelcheck.explore(initial, tf, iv)
    assert r["verdict"] == modelcheck.VIOLATED
    assert r["invariant_holds"] is False
    assert r["counterexample"]  # shortest path present


def test_ac188_190_specific_safety_models_hold():
    # AC-0006-188..190: authority-monotonicity, budget-conservation,
    # no-self-approval, cancellation all HOLD.
    summary = modelcheck.run_all_models()
    for name in ("authority_monotonicity_model", "budget_conservation_model",
                 "no_self_approval_model", "cancellation_model"):
        assert summary[name]["verdict"] == modelcheck.HOLDS, name


def test_ac186_truncation_is_honest():
    # AC-0006-186: a truncated search is INCONCLUSIVE_TRUNCATED, never HOLDS.
    initial, tf, iv = modelcheck.work_state_model()
    r = modelcheck.explore(initial, tf, iv, max_states=2)
    assert r["truncated"] is True
    assert r["verdict"] == modelcheck.INCONCLUSIVE_TRUNCATED
    assert r["verdict"] != modelcheck.HOLDS
    assert r["invariant_holds"] is None


# ===========================================================================
# AC-0006-191..195 — proof envelopes are evidence, not authority.
# ===========================================================================

def _work():
    return {"work_instance_hash": "wih-1", "semantic_work_hash": "swh-1",
            "work_order_id": "W1"}


def test_ac191_192_envelope_deterministic_and_classified():
    # AC-0006-191/192: same input -> same envelope_hash; EVIDENCE_NOT_AUTHORITY.
    w = _work()
    e1 = envelope.work_proof_envelope(w, leases=[{"lease_id": "l1"}],
                                      approvals=[{"approval_id": "a1"}],
                                      outcome_evidence=[{"e": 1}])
    e2 = envelope.work_proof_envelope(w, leases=[{"lease_id": "l1"}],
                                      approvals=[{"approval_id": "a1"}],
                                      outcome_evidence=[{"e": 1}])
    assert e1["envelope_hash"] == e2["envelope_hash"]
    assert e1["classification"] == "EVIDENCE_NOT_AUTHORITY"
    assert envelope.validate_envelope(e1) == []


def test_ac193_lease_change_changes_hash():
    # AC-0006-193: a different lease set -> different envelope_hash.
    w = _work()
    base = envelope.work_proof_envelope(w, leases=[{"lease_id": "l1"}])
    changed = envelope.work_proof_envelope(w, leases=[{"lease_id": "l2"}])
    assert base["envelope_hash"] != changed["envelope_hash"]


def test_ac194_approval_and_outcome_change_hash():
    # AC-0006-194: approval change and outcome-evidence change each alter hash.
    w = _work()
    base = envelope.work_proof_envelope(w, approvals=[{"approval_id": "a1"}],
                                        outcome_evidence=[{"e": 1}])
    appr = envelope.work_proof_envelope(w, approvals=[{"approval_id": "a2"}],
                                        outcome_evidence=[{"e": 1}])
    outc = envelope.work_proof_envelope(w, approvals=[{"approval_id": "a1"}],
                                        outcome_evidence=[{"e": 2}])
    assert base["envelope_hash"] != appr["envelope_hash"]
    assert base["envelope_hash"] != outc["envelope_hash"]


def test_ac195_envelope_claiming_authority_is_mismatch():
    # AC-0006-195: an envelope claiming to grant authority is flagged.
    e = envelope.work_proof_envelope(_work())
    e_bad = dict(e, grants_authority=True)
    assert PROOF_ENVELOPE_MISMATCH in _k(envelope.validate_envelope(e_bad))


def test_outcome_states_alphabet_present():
    # sanity: OUTCOME_STATES alphabet is importable and non-trivial.
    assert "VERIFIED" in OUTCOME_STATES
    assert "PARTIALLY_VERIFIED" in OUTCOME_STATES

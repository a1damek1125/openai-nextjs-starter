"""SP0006 red-team regression locks (SWARM-M).

Each test pins shut a confirmed false-negative escape — a way an unsafe
governed-work condition was admitted as SAFE. They must FAIL if the corresponding
hardening is reverted. Two systemic root causes were fixed kernel-wide: truthy-
string coercion of boolean flags (fix: `is True`), and blacklist/"missing =
permissive" logic (fix: allowlist + fail-closed).
"""
from __future__ import annotations

from tools.governed_work import (delegation, lease, drift, outcome, purpose,
                                 approval, recurrence, envelope)
from tools.governed_work.validate import validate_all
from tools.governed_work.model import (SELF_REPORT_AS_SOLE_OUTCOME_ORACLE,
                                       HIDDEN_WORK_DETECTED, SELF_APPROVAL_DETECTED,
                                       APPROVAL_CLASS_INSUFFICIENT,
                                       RECURRENCE_REAUTHORIZATION_FAILED,
                                       PROOF_ENVELOPE_MISMATCH,
                                       DELEGATION_CYCLE_DETECTED, HARD_GOAL_DRIFT)


def _k(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


# E1 — coordination_only truthy-string must not launder an authority cycle
def test_e1_coordination_only_truthy_string_does_not_hide_cycle():
    edges = [{"parent_identity": "A", "child_identity": "B", "work_order_id": "W"},
             {"parent_identity": "B", "child_identity": "A", "work_order_id": "W",
              "coordination_only": "false"}]
    assert delegation.has_cycle(edges)
    # and it defeats the aggregate gate no more:
    ids = [{"execution_identity_id": "A", "work_order_id": "W", "role": "x"},
           {"execution_identity_id": "B", "work_order_id": "W", "role": "x",
            "parent_identity_id": "A", "delegation_depth": 1}]
    f = delegation.validate_delegation({"work_order_id": "W",
                                        "capability_ceiling": {}}, edges, ids, {})
    assert DELEGATION_CYCLE_DETECTED in _k(f)


def test_e1_real_coordination_only_true_still_excluded():
    edges = [{"parent_identity": "A", "child_identity": "B", "work_order_id": "W"},
             {"parent_identity": "B", "child_identity": "A", "work_order_id": "W",
              "coordination_only": True}]
    assert not delegation.has_cycle(edges)


# E4 — a child that omits a ceiling/use-count the parent bounds is not attenuated
def test_e4_omitted_numeric_ceiling_is_not_attenuation():
    assert not lease.is_attenuation({"cost_ceiling": 100}, {})[0]
    assert not lease.is_attenuation({"cost_ceiling": {"x": 5}}, {"cost_ceiling": {}})[0]


def test_e4_omitted_use_count_is_not_attenuation():
    assert not lease.is_attenuation({"maximum_uses": 10}, {})[0]
    assert not lease.is_attenuation({"maximum_uses": 10}, {"maximum_uses": None})[0]


def test_e4_proper_child_still_attenuates():
    assert lease.is_attenuation({"cost_ceiling": 100, "maximum_uses": 10},
                                {"cost_ceiling": 50, "maximum_uses": 4})[0]


# E5 — approved_replan truthy-string must not suppress outcome-redefinition drift
def test_e5_approved_replan_string_does_not_suppress_hard_drift():
    base = {"outcome_contract": {"a": 1}}
    cur = {"outcome_contract": {"a": 2}, "approved_replan": "false"}
    assert HARD_GOAL_DRIFT in _k(drift.hard_drift(base, cur))


def test_e5_real_approved_replan_suppresses():
    base = {"outcome_contract": {"a": 1}}
    cur = {"outcome_contract": {"a": 2}, "approved_replan": True}
    assert not any(f.details.get("trigger") == "outcome_redefinition"
                   for f in drift.hard_drift(base, cur))


# E3 — junk oracle cannot mask self-report as sufficient for a critical outcome
def _critical_contract(oracles):
    return {"critical": True, "expected_outcomes": ["x"],
            "acceptance_predicates": [{"predicate_id": "p",
                                       "predicate_type": "ARTIFACT_EXISTS"}],
            "verification_mode": "INDEPENDENT_QUALIFIED", "completion_rule": "ALL",
            "oracles": oracles}


def test_e3_junk_oracle_does_not_launder_self_report():
    c = _critical_contract(["AGENT_SELF_REPORT", "JUNK_ORACLE_9000"])
    ev = [{"predicate_id": "p", "oracle": "AGENT_SELF_REPORT", "artifact_ref": "x"}]
    assert SELF_REPORT_AS_SOLE_OUTCOME_ORACLE in _k(outcome.verify_outcome(c, ev)['findings'])


def test_e3_real_primary_oracle_ok():
    c = _critical_contract(["ENVIRONMENT_STATE"])
    ev = [{"predicate_id": "p", "oracle": "ENVIRONMENT_STATE", "artifact_ref": "x"}]
    assert SELF_REPORT_AS_SOLE_OUTCOME_ORACLE not in _k(outcome.verify_outcome(c, ev)['findings'])


# E8 — THRESHOLD:0 / negative never vacuously VERIFIED
def test_e8_threshold_zero_not_vacuously_verified():
    for rule in ("THRESHOLD:0", "THRESHOLD:-3"):
        c = {"expected_outcomes": ["x"], "acceptance_predicates": [],
             "verification_mode": "DETERMINISTIC", "completion_rule": rule}
        assert outcome.verify_outcome(c, [])["state"] != "VERIFIED"


# E6 — hidden work: a param-smuggled step is not deemed admitted
def test_e6_param_smuggled_step_is_hidden_work():
    admitted = [{"action": "transfer", "target": "acctA"}]
    executed = [{"action": "transfer", "target": "acctA", "amount": 9999999,
                 "recipient": "attacker"}]
    assert HIDDEN_WORK_DETECTED in _k(purpose.hidden_work(admitted, executed))


# E7 — purpose memory-source whitespace/case + access self-authorization
def test_e7_memory_source_whitespace_cannot_create_purpose():
    for src in ("memory ", "Memory", " MEMORY"):
        acc = {"purpose": "marketing", "source": src,
               "compatible_purposes": ["billing"]}
        assert not purpose.purpose_compatible(acc, {"privacy_purpose": "billing"})


def test_e7_access_cannot_self_authorize_new_purpose():
    acc = {"purpose": "marketing", "source": "tool",
           "compatible_purposes": ["billing"]}
    # work does not list marketing as compatible -> incompatible
    assert not purpose.purpose_compatible(acc, {"privacy_purpose": "billing"})


# E2 — an under-classed (downgraded) approval token is rejected via context floor
def test_e2_downgraded_approval_token_rejected():
    action = {"action_type": "pay", "effect_class": "PAYMENT",
              "target": {"target_id": "X"}, "parameters": {"amount": 1000}}
    tok = approval.issue_token(work_instance_hash="wih", action=action,
                               required_class="A0", approver_id="u",
                               approver_class="A0", issued_at="2026-03-05",
                               expires_at="2026-03-06")
    ok, f = approval.validate_token(tok, action=action, work_instance_hash="wih",
                                    now="2026-03-05T12:00:00Z")
    assert not ok and APPROVAL_CLASS_INSUFFICIENT in _k(f)


# E10 — self-approval via case/whitespace identity variants
def test_e10_self_approval_identity_variants():
    for approver in ("ALICE", "alice ", " Alice"):
        f = approval.no_self_approval(proposer="alice", planner=None,
                                      executor=None, approver=approver,
                                      verifier="v", independence_required=True)
        assert SELF_APPROVAL_DETECTED in _k(f)


# E9 — recurrence: a stale token bound under an alternate key cannot authorize
def test_e9_alternate_key_token_cannot_authorize_run():
    ok, f = recurrence.reauthorize(
        {"reauthorization_requirements": []},
        {"work_instance_hash": "IH_NEW"},
        {"approval_tokens": [{"prior_instance_hash": "IH_OLD"}]})
    assert not ok and RECURRENCE_REAUTHORIZATION_FAILED in _k(f)


# E11 — an envelope key that implies authority via a synonym is a mismatch
def test_e11_envelope_authority_synonym_rejected():
    for key in ("confers_capability", "grants_permission", "entitles",
                "authorization"):
        assert PROOF_ENVELOPE_MISMATCH in _k(envelope.validate_envelope(
            {"envelope_kind": "W", key: True}))

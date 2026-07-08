"""CORE-A4.1 — deterministic canonicalization and hashes for the Human
Approval Gate foundation (pure). Every hash is deterministic, excludes itself
and volatile fields, and changes when the covered content changes."""
import math

import pytest

from finalis.ai_employee import approvals as A


def _capsule():
    return A.build_policy_capsule(
        tenant_id="t1", run_id="r1", task_id="k1",
        approval_request_id="ar1", action_type="draft_customer_reply",
        subject_type="case", subject_id="c1", risk_level="MEDIUM",
        authority_decision="APPROVAL_REQUIRED", authority_hard_fail=False,
        consent_requirement=True, evidence_requirement=False,
        proof_requirement=False, allowed_next_transition="X",
        created_at="2026-07-08T00:00:00Z")


def _package(capsule, challenge=None):
    pre = A.build_preconditions(
        tenant_id="t1", run_id="r1", task_id="k1",
        approval_action_type="draft_customer_reply", subject_type="case",
        subject_id="c1", task_contract_hash="tc", task_envelope_hash="te",
        run_state_hash="rs", run_chain_hash="rc", run_event_merkle_root="rm",
        policy_decision_hash=A.policy_decision_hash(capsule),
        authority_decision="APPROVAL_REQUIRED", consent_required=True,
        evidence_required=False, proof_required=False, challenge_required=False)
    return A.build_package(
        approval_request_id="ar1", tenant_id="t1", run_id="r1", task_id="k1",
        task_contract_hash="tc", task_envelope_hash="te", run_chain_hash="rc",
        run_state_hash="rs", run_event_merkle_root="rm",
        assigned_ai_employee_id="e1", requester_user_id="u1", capsule=capsule,
        approval_action_type="draft_customer_reply", approval_scope={"a": 1},
        allowed_next_transition="X", risk_level="MEDIUM",
        authority_decision="APPROVAL_REQUIRED", authority_reason="r",
        requires_consent_check=True, requires_evidence_check=False,
        requires_tool_broker=False, evidence_refs=[], proof_report_refs=[],
        consent_refs=[], subject_refs=["c1"], data_scope_refs=[],
        preconditions=pre, challenge=challenge)


class TestCanonicalJson:
    def test_key_order_independent(self):
        assert A.canonical_json({"b": 1, "a": 2}) \
            == A.canonical_json({"a": 2, "b": 1})

    def test_compact_separators(self):
        assert A.canonical_json({"a": 1, "b": 2}) == '{"a":1,"b":2}'

    def test_nan_rejected(self):
        with pytest.raises(ValueError):
            A.canonical_json({"x": math.nan})

    def test_unicode_preserved(self):
        assert "ą" in A.canonical_json({"k": "ą"})


class TestPolicyHash:
    def test_deterministic(self):
        assert A.policy_decision_hash(_capsule()) \
            == A.policy_decision_hash(_capsule())

    def test_excludes_created_at(self):
        c1 = _capsule()
        c2 = dict(c1, created_at="2099-01-01T00:00:00Z")
        assert A.policy_decision_hash(c1) == A.policy_decision_hash(c2)

    def test_excludes_self(self):
        c = _capsule()
        c["policy_decision_hash"] = "deadbeef"
        h1 = A.policy_decision_hash(c)
        c["policy_decision_hash"] = "cafe"
        assert h1 == A.policy_decision_hash(c)

    def test_changes_on_role_change(self):
        c1 = _capsule()
        c2 = dict(c1, required_approver_role="owner")
        assert A.policy_decision_hash(c1) != A.policy_decision_hash(c2)

    def test_input_and_output_hashes_present_and_stable(self):
        c = _capsule()
        assert c["policy_input_hash"] == A._sha(c["policy_input"])
        assert len(c["policy_output_hash"]) == 64


class TestPackageHash:
    def test_deterministic(self):
        c = _capsule()
        assert A.package_hash(_package(c)) == A.package_hash(_package(c))

    def test_excludes_self(self):
        p = _package(_capsule())
        p["package_hash"] = "x"
        h = A.package_hash(p)
        p["package_hash"] = "y"
        assert h == A.package_hash(p)

    def test_changes_when_action_changes(self):
        c = _capsule()
        p = _package(c)
        p2 = dict(p, approval_action_type="execute_payment")
        assert A.package_hash(p) != A.package_hash(p2)

    def test_challenge_binding_changes_hash(self):
        c = _capsule()
        base = _package(c)
        with_ch = dict(base, approval_challenge={"x": 1})
        assert A.package_hash(base) != A.package_hash(with_ch)


class TestChallengeHash:
    def test_deterministic_and_excludes_volatile(self):
        ch1 = A.build_challenge(
            approval_request_id="ar1", tenant_id="t1",
            viewed_package_hash="vp", required_acknowledgements=["a"],
            risk_level="HIGH", subject_required=True,
            created_at="2026-07-08T00:00:00Z", expires_at=None, required=True)
        ch2 = dict(ch1, created_at="2099-01-01T00:00:00Z")
        assert A.challenge_hash(ch1) == A.challenge_hash(ch2)
        assert ch1["challenge_hash"] == A.challenge_hash(ch1)

    def test_changes_on_viewed_package_hash(self):
        kw = dict(approval_request_id="ar1", tenant_id="t1",
                  required_acknowledgements=["a"], risk_level="HIGH",
                  subject_required=False, created_at="t", expires_at=None,
                  required=True)
        a = A.build_challenge(viewed_package_hash="p1", **kw)
        b = A.build_challenge(viewed_package_hash="p2", **kw)
        assert a["challenge_hash"] != b["challenge_hash"]


class TestPreconditionHash:
    def test_deterministic(self):
        c = _capsule()
        p = _package(c)
        pre = p["preconditions"]
        assert A.precondition_hash(pre) == A.precondition_hash(pre)

    def test_changes_when_run_state_hash_changes(self):
        c = _capsule()
        pre = _package(c)["preconditions"]
        pre2 = dict(pre, run_state_hash_unchanged="different")
        assert A.precondition_hash(pre) != A.precondition_hash(pre2)


class TestRequestHash:
    def test_excludes_self_and_volatile(self):
        core = {"approval_request_id": "ar1", "approval_status": "PENDING",
                "approval_request_hash": "old", "created_at": "t",
                "updated_at": "t2", "honesty_labels": ["x"]}
        h = A.request_hash(core)
        core2 = dict(core, approval_request_hash="new",
                     created_at="later", updated_at="later2",
                     honesty_labels=["y"])
        assert h == A.request_hash(core2)

    def test_changes_on_status(self):
        core = {"approval_request_id": "ar1", "approval_status": "PENDING"}
        assert A.request_hash(core) \
            != A.request_hash(dict(core, approval_status="BLOCKED"))

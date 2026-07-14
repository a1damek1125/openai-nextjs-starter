"""CORE-A4.1 — risk-based approval policy matrix and the always-blocked
invariant: an approval can never convert a forbidden action into an allowed
action (pure)."""
import pytest

from finalis.ai_employee import approvals as A


class TestApproverMatrix:
    @pytest.mark.parametrize("risk,role,count,dual", [
        ("LOW", "manager", 1, False),
        ("MEDIUM", "manager", 1, False),
        ("HIGH", "owner", 1, False),
        ("CRITICAL", "owner", 2, True),
    ])
    def test_approver_role_by_risk(self, risk, role, count, dual):
        assert A._approver_role(risk) == (role, count, dual)

    def test_unknown_risk_defaults_to_owner(self):
        assert A._approver_role("WAT") == ("owner", 1, False)

    @pytest.mark.parametrize("risk,needed", [
        ("LOW", False), ("MEDIUM", False), ("HIGH", True), ("CRITICAL", True)])
    def test_challenge_required_by_risk(self, risk, needed):
        assert A.challenge_required(risk) is needed

    def test_matrix_covers_all_risks(self):
        assert set(A.APPROVAL_POLICY_MATRIX) == {
            "LOW", "MEDIUM", "HIGH", "CRITICAL"}

    def test_low_does_not_require_human_approval(self):
        assert A.APPROVAL_POLICY_MATRIX["LOW"][
            "human_approval_required"] is False

    def test_medium_requires_human_but_not_challenge(self):
        m = A.APPROVAL_POLICY_MATRIX["MEDIUM"]
        assert m["human_approval_required"] is True
        assert m["challenge_required"] is False

    def test_critical_requires_dual_control(self):
        c = A.APPROVAL_POLICY_MATRIX["CRITICAL"]
        assert c["dual_control"] is True
        assert c["required_approver_count"] == 2


class TestAlwaysBlocked:
    @pytest.mark.parametrize("action", sorted(A.ALWAYS_BLOCKED_ACTIONS))
    def test_action_blocked_even_with_approval(self, action):
        cap = A.build_policy_capsule(
            tenant_id="t", run_id="r", task_id="k", approval_request_id="ar",
            action_type=action, subject_type="case", subject_id="c",
            risk_level="MEDIUM", authority_decision="APPROVAL_REQUIRED",
            authority_hard_fail=False, consent_requirement=False,
            evidence_requirement=False, proof_requirement=False,
            allowed_next_transition="X", created_at="t")
        assert cap["always_blocked"] is True
        assert cap["blocked_reasons"]
        # challenge is suppressed when always blocked
        assert cap["challenge_required"] is False

    def test_self_approval_and_ai_approval_forbidden_flags(self):
        cap = A.build_policy_capsule(
            tenant_id="t", run_id="r", task_id="k", approval_request_id="ar",
            action_type="draft_case_summary", subject_type="case",
            subject_id="c", risk_level="LOW",
            authority_decision="ALLOWED_DRAFT_ONLY", authority_hard_fail=False,
            consent_requirement=False, evidence_requirement=False,
            proof_requirement=False, allowed_next_transition="X",
            created_at="t")
        assert cap["self_approval_forbidden"] is True
        assert cap["ai_approval_forbidden"] is True

    def test_key_forbidden_actions_present(self):
        for a in ("override_consent", "rewrite_evidence", "execute_payment",
                  "approve_own_work", "call_external_provider",
                  "execute_merge", "verify_memory"):
            assert a in A.ALWAYS_BLOCKED_ACTIONS


class TestForbiddenUnlocks:
    def test_consent_and_evidence_never_unlockable(self):
        for f in ("override_consent", "override_rbac", "rewrite_evidence",
                  "delete_evidence", "hide_proof_failure", "approve_own_work"):
            assert f in A.FORBIDDEN_UNLOCKS

    def test_reuse_across_scope_forbidden(self):
        for f in ("reuse_for_other_run", "reuse_for_other_task",
                  "reuse_for_other_action", "reuse_after_hash_state_change"):
            assert f in A.FORBIDDEN_UNLOCKS

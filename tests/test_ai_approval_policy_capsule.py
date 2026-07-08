"""CORE-A4.1 — policy decision capsule: deterministic, no LLM, authoritative
policy output derived purely from (action, risk, authority, requirements)."""
from finalis.ai_employee import approvals as A


def _cap(**over):
    kw = dict(
        tenant_id="t1", run_id="r1", task_id="k1", approval_request_id="ar1",
        action_type="draft_customer_reply", subject_type="case",
        subject_id="c1", risk_level="HIGH",
        authority_decision="APPROVAL_REQUIRED", authority_hard_fail=False,
        consent_requirement=True, evidence_requirement=True,
        proof_requirement=False, allowed_next_transition="X", created_at="t")
    kw.update(over)
    return A.build_policy_capsule(**kw)


class TestCapsuleShape:
    def test_engine_is_local_deterministic(self):
        assert _cap()["policy_engine"] == "LOCAL_DETERMINISTIC_CORE_A4"

    def test_version_stamped(self):
        assert _cap()["policy_decision_version"] == A.POLICY_CAPSULE_VERSION

    def test_high_risk_owner_and_challenge(self):
        c = _cap(risk_level="HIGH")
        assert c["required_approver_role"] == "owner"
        assert c["challenge_required"] is True

    def test_critical_dual_control(self):
        c = _cap(risk_level="CRITICAL")
        assert c["dual_control_required"] is True
        assert c["required_approver_count"] == 2

    def test_forbidden_unlocks_recorded(self):
        assert _cap()["forbidden_unlocks"] == A.FORBIDDEN_UNLOCKS


class TestRequiredAcknowledgements:
    def test_base_acks_always_present(self):
        acks = _cap(consent_requirement=False, evidence_requirement=False)[
            "required_acknowledgements"]
        for a in ("risk_acknowledged", "scope_acknowledged",
                  "future_execution_acknowledged", "no_override_acknowledged",
                  "limitations_acknowledged"):
            assert a in acks

    def test_consent_ack_added_when_required(self):
        assert "consent_acknowledged" in _cap(consent_requirement=True)[
            "required_acknowledgements"]

    def test_evidence_ack_added_when_required(self):
        assert "evidence_acknowledged" in _cap(evidence_requirement=True)[
            "required_acknowledgements"]

    def test_proof_ack_added_when_required(self):
        assert "proof_acknowledged" in _cap(proof_requirement=True)[
            "required_acknowledgements"]

    def test_acks_are_sorted(self):
        acks = _cap()["required_acknowledgements"]
        assert acks == sorted(acks)


class TestAuthorityDominance:
    def test_blocked_authority_forces_always_blocked(self):
        c = _cap(authority_decision="BLOCKED")
        assert c["always_blocked"] is True
        assert any("authority" in r for r in c["blocked_reasons"])

    def test_hard_fail_forces_always_blocked(self):
        c = _cap(authority_hard_fail=True)
        assert c["always_blocked"] is True

    def test_challenge_suppressed_when_blocked(self):
        c = _cap(risk_level="HIGH", authority_decision="BLOCKED")
        assert c["challenge_required"] is False


class TestPolicyInputOutputHashes:
    def test_input_hash_matches_input(self):
        c = _cap()
        assert c["policy_input_hash"] == A._sha(c["policy_input"])

    def test_input_hash_changes_with_risk(self):
        assert _cap(risk_level="HIGH")["policy_input_hash"] \
            != _cap(risk_level="CRITICAL")["policy_input_hash"]

    def test_capsule_hash_stable_across_created_at(self):
        assert A.policy_decision_hash(_cap(created_at="a")) \
            == A.policy_decision_hash(_cap(created_at="b"))

    def test_subject_access_required_tracks_subject(self):
        assert _cap(subject_id="c1")["subject_access_required"] is True
        assert _cap(subject_id=None)["subject_access_required"] is False

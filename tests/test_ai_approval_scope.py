"""CORE-A4.2 — approval grant non-transferability. A grant is bound to exactly
one (tenant, run, task, action, hash state). Presenting it against any other
scope or a drifted hash state fails validation — it cannot be transferred or
replayed."""
from finalis.ai_employee import approval_decisions as D

from conftest import OWNER2, MANAGER


def _grant(**over):
    kw = dict(
        approval_grant_id="g1", approval_request_id="ar1",
        approval_decision_id="d1", tenant_id="t1", run_id="r1", task_id="k1",
        approval_action_type="draft_customer_reply", approval_scope={},
        allowed_next_transition="X", task_contract_hash="tc",
        task_envelope_hash="te", run_state_hash="rs", run_chain_hash="rc",
        run_event_merkle_root="rm", policy_decision_hash="pd",
        approval_package_hash="pk", approval_challenge_hash="ch",
        approval_decision_hash="dh", approval_precondition_hash="pre",
        grant_nonce_hash="nh", grant_status="VALID",
        grant_usage_policy="SINGLE_USE_READY", single_use=True,
        expires_at="2099-01-01T00:00:00", created_at="t")
    kw.update(over)
    return D.build_grant(**kw)


def _cur(g, **over):
    cur = {"tenant_id": g["tenant_id"], "run_id": g["run_id"],
           "task_id": g["task_id"],
           "approval_action_type": g["approval_action_type"],
           "task_contract_hash": g["task_contract_hash"],
           "task_envelope_hash": g["task_envelope_hash"],
           "run_state_hash": g["run_state_hash"],
           "run_chain_hash": g["run_chain_hash"],
           "run_event_merkle_root": g["run_event_merkle_root"],
           "policy_decision_hash": g["policy_decision_hash"],
           "approval_package_hash": g["approval_package_hash"],
           "approval_challenge_hash": g["approval_challenge_hash"],
           "approval_decision_hash": g["approval_decision_hash"],
           "action_always_blocked": False, "tool_broker_required": False,
           "precondition_status": "OK"}
    cur.update(over)
    return cur


class TestNonTransferable:
    def test_valid_only_in_own_scope(self):
        g = _grant()
        assert D.validate_grant(g, current=_cur(g), expired=False)[
            "grant_validation_status"] == "VALID"

    def test_cannot_reuse_for_another_run(self):
        g = _grant()
        res = D.validate_grant(g, current=_cur(g, run_id="OTHER"),
                               expired=False)
        assert res["grant_validation_status"] == "HASH_STATE_CHANGED"
        assert res["drift_detected"] is True

    def test_cannot_reuse_for_another_task(self):
        g = _grant()
        assert D.validate_grant(g, current=_cur(g, task_id="OTHER"),
                                expired=False)[
            "grant_validation_status"] == "HASH_STATE_CHANGED"

    def test_cannot_reuse_for_another_action(self):
        g = _grant()
        assert D.validate_grant(g, current=_cur(g,
                                approval_action_type="execute_payment"),
                                expired=False)[
            "grant_validation_status"] == "HASH_STATE_CHANGED"

    def test_cannot_reuse_after_hash_state_change(self):
        g = _grant()
        assert D.validate_grant(g, current=_cur(g, run_state_hash="new"),
                                expired=False)[
            "grant_validation_status"] == "HASH_STATE_CHANGED"

    def test_cannot_reuse_after_policy_decision_change(self):
        g = _grant()
        assert D.validate_grant(g, current=_cur(g,
                                policy_decision_hash="new"), expired=False)[
            "grant_validation_status"] == "HASH_STATE_CHANGED"

    def test_cannot_reuse_after_task_contract_change(self):
        g = _grant()
        assert D.validate_grant(g, current=_cur(g, task_contract_hash="new"),
                                expired=False)[
            "grant_validation_status"] == "HASH_STATE_CHANGED"

    def test_cross_tenant_scope_fails(self):
        g = _grant()
        assert D.validate_grant(g, current=_cur(g, tenant_id="OTHER"),
                                expired=False)[
            "grant_validation_status"] == "HASH_STATE_CHANGED"


class TestScopeApi:
    def test_grant_scope_matches_request(self, gate):
        ap, rid = gate.make_request("customer_reply_draft")
        g = gate.approve(ap, challenge=False).json()["approval_grant"]
        assert g["approval_scope"]["run_id"] == rid
        assert g["approval_scope"]["action_type"] == ap["approval_action_type"]

"""CORE-A4.2 — non-transferable approval grant model, grant/nonce hashing,
lifecycle (expiry/revoke/supersede) and grant issuance (pure + API).

An approval grant is a LOCAL Finalis artifact, not an OAuth/GNAP/OAP token. It
authorizes only a future gated transition and must be revalidated before use.
"""
import json
import math

import pytest

from finalis.ai_employee import approval_decisions as D

from conftest import OWNER2, MANAGER


def _grant(**over):
    kw = dict(
        approval_grant_id="g1", approval_request_id="ar1",
        approval_decision_id="d1", tenant_id="t1", run_id="r1", task_id="k1",
        approval_action_type="draft_customer_reply", approval_scope={"a": 1},
        allowed_next_transition="X", task_contract_hash="tc",
        task_envelope_hash="te", run_state_hash="rs", run_chain_hash="rc",
        run_event_merkle_root="rm", policy_decision_hash="pd",
        approval_package_hash="pk", approval_challenge_hash="ch",
        approval_decision_hash="dh", approval_precondition_hash="pre",
        grant_nonce_hash="nh", grant_status="VALID",
        grant_usage_policy="SINGLE_USE_READY", single_use=True,
        expires_at="2099-01-01T00:00:00", created_at="2026-07-08T00:00:00Z")
    kw.update(over)
    return D.build_grant(**kw)


class TestGrantHashPure:
    def test_type_is_local_non_transferable(self):
        assert _grant()["grant_type"] == "LOCAL_NON_TRANSFERABLE_APPROVAL_GRANT"

    def test_hash_excludes_itself(self):
        g = _grant()
        assert D.grant_hash(g) == D.grant_hash(dict(g, approval_grant_hash="z"))

    def test_hash_stable_across_mutable_lifecycle(self):
        g = _grant()
        mutated = dict(g, grant_status="REVOKED", revoked_at="now",
                       consume_check_count=9, validated_at="later")
        assert D.grant_hash(g) == D.grant_hash(mutated)

    def test_changed_run_state_hash_changes_grant_hash(self):
        assert _grant(run_state_hash="a")["approval_grant_hash"] \
            != _grant(run_state_hash="b")["approval_grant_hash"]

    def test_changed_task_contract_hash_changes_grant_hash(self):
        assert _grant(task_contract_hash="a")["approval_grant_hash"] \
            != _grant(task_contract_hash="b")["approval_grant_hash"]

    def test_changed_task_envelope_hash_changes_grant_hash(self):
        assert _grant(task_envelope_hash="a")["approval_grant_hash"] \
            != _grant(task_envelope_hash="b")["approval_grant_hash"]

    def test_changed_policy_decision_hash_changes_grant_hash(self):
        assert _grant(policy_decision_hash="a")["approval_grant_hash"] \
            != _grant(policy_decision_hash="b")["approval_grant_hash"]

    def test_changed_scope_changes_grant_hash(self):
        assert _grant(approval_scope={"a": 1})["approval_grant_hash"] \
            != _grant(approval_scope={"a": 2})["approval_grant_hash"]

    def test_changed_nonce_changes_grant_hash(self):
        assert _grant(grant_nonce_hash="a")["approval_grant_hash"] \
            != _grant(grant_nonce_hash="b")["approval_grant_hash"]

    def test_key_order_irrelevant(self):
        g = _grant()
        assert D.grant_hash(g) == D.grant_hash(dict(reversed(list(g.items()))))

    def test_unknown_status_rejected(self):
        with pytest.raises(ValueError):
            _grant(grant_status="TOTALLY_FINE")

    def test_unknown_usage_policy_rejected(self):
        with pytest.raises(ValueError):
            _grant(grant_usage_policy="ALWAYS")


class TestNoncePure:
    def test_nonce_hash_deterministic(self):
        kw = dict(nonce="n", approval_request_id="ar",
                  approval_decision_id="d", run_state_hash="rs",
                  task_contract_hash="tc", policy_decision_hash="pd")
        assert D.grant_nonce_hash(**kw) == D.grant_nonce_hash(**kw)

    def test_nonce_binds_to_state(self):
        base = dict(nonce="n", approval_request_id="ar",
                    approval_decision_id="d", run_state_hash="rs",
                    task_contract_hash="tc", policy_decision_hash="pd")
        assert D.grant_nonce_hash(**base) \
            != D.grant_nonce_hash(**dict(base, run_state_hash="other"))

    def test_different_nonce_differs(self):
        base = dict(approval_request_id="ar", approval_decision_id="d",
                    run_state_hash="rs", task_contract_hash="tc",
                    policy_decision_hash="pd")
        assert D.grant_nonce_hash(nonce="a", **base) \
            != D.grant_nonce_hash(nonce="b", **base)


class TestGrantApi:
    def test_grant_issued_and_bound_to_scope(self, gate):
        ap, rid = gate.make_request("customer_reply_draft")
        g = gate.approve(ap, challenge=False).json()["approval_grant"]
        assert g["grant_type"] == "LOCAL_NON_TRANSFERABLE_APPROVAL_GRANT"
        assert g["run_id"] == rid
        assert g["task_id"] == ap["task_id"]
        assert g["approval_action_type"] == ap["approval_action_type"]
        assert g["run_state_hash"] == ap["run_state_hash"]
        assert g["approval_grant_hash"]
        assert g["grant_nonce_hash"]

    def test_grant_hash_verifies(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        gate.approve(ap, challenge=False)
        g = gate.grant(ap["approval_request_id"])
        assert D.grant_hash(g) == g["approval_grant_hash"]

    def test_grant_read_endpoint(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        gate.approve(ap, challenge=False)
        r = gate.c.get(f"/ai-approvals/{ap['approval_request_id']}/grant",
                       headers=gate.h(OWNER2))
        assert r.status_code == 200
        assert r.json()["grant_type"] \
            == "LOCAL_NON_TRANSFERABLE_APPROVAL_GRANT"

    def test_grant_missing_returns_404(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        r = gate.c.get(f"/ai-approvals/{ap['approval_request_id']}/grant",
                       headers=gate.h(OWNER2))
        assert r.status_code == 404

    def test_tool_broker_action_not_consumable(self, gate):
        ap, _ = gate.make_request("evidence_report_request")   # requires TB
        r = gate.approve(ap, challenge=True).json()
        assert r["approval_status"] == "APPROVED_BUT_NOT_CONSUMABLE"
        assert r["approval_grant"]["grant_status"] == "NOT_CONSUMABLE"
        assert r["approval_grant"]["grant_usage_policy"] \
            == "CONSUMPTION_NOT_IMPLEMENTED"

    def test_grant_expiry(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        gate.approve(ap, challenge=False)
        aid = ap["approval_request_id"]
        g = gate.grant(aid)
        gp = json.loads(gate.db.one(
            "SELECT payload_json FROM ai_approval_grants WHERE id=?",
            g["approval_grant_id"])["payload_json"])
        gp["expires_at"] = "2000-01-01T00:00:00"
        gate.db.conn.execute(
            "UPDATE ai_approval_grants SET payload_json=?, expires_at=? "
            "WHERE id=?", (json.dumps(gp), "2000-01-01T00:00:00",
                           g["approval_grant_id"]))
        gate.db.conn.commit()
        assert gate.consume_check(aid)["grant_validation_status"] == "EXPIRED"

    def test_grant_revocation_invalidates(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        gate.approve(ap, challenge=False)
        aid = ap["approval_request_id"]
        r = gate.c.post(f"/ai-approvals/{aid}/revoke",
                        json={"decision_reason": "nvm"}, headers=gate.h(OWNER2))
        assert r.json()["approval_status"] == "REVOKED"
        assert gate.consume_check(aid)["grant_validation_status"] == "REVOKED"

    def test_supersession_invalidates_old_grant(self, gate):
        # Two requests for the SAME run/task/action: approving the second
        # supersedes the first grant.
        hdr = gate.h(MANAGER)
        cid = gate.case_id(hdr)
        tk = gate.c.post("/ai-tasks", json={
            "task_type": "customer_reply_draft", "task_title": "t",
            "task_description": "please do the thing", "subject_type": "case",
            "subject_id": cid}, headers=hdr).json()
        run = gate.c.post("/ai-runs", json={"task_id": tk["task_id"]},
                          headers=hdr).json()
        a1 = gate.c.post("/ai-approvals", json={"run_id": run["run_id"]},
                         headers=hdr).json()
        a2 = gate.c.post("/ai-approvals", json={"run_id": run["run_id"]},
                         headers=hdr).json()
        gate.approve(a1, challenge=False)
        gate.approve(a2, challenge=False)
        cc = gate.consume_check(a1["approval_request_id"])
        assert cc["grant_validation_status"] == "SUPERSEDED"

"""CORE-A4.2 — consume-check: validation-only grant re-check. It answers
"would this grant be valid?" and NEVER executes, calls a Tool Broker, or
consumes the grant."""
import json

from finalis.ai_employee import approval_decisions as D

from conftest import OWNER2, MANAGER


class TestValidateGrantPure:
    def _g(self, **over):
        kw = dict(
            approval_grant_id="g1", approval_request_id="ar1",
            approval_decision_id="d1", tenant_id="t1", run_id="r1",
            task_id="k1", approval_action_type="draft_customer_reply",
            approval_scope={}, allowed_next_transition="X",
            task_contract_hash="tc", task_envelope_hash="te",
            run_state_hash="rs", run_chain_hash="rc", run_event_merkle_root="rm",
            policy_decision_hash="pd", approval_package_hash="pk",
            approval_challenge_hash="ch", approval_decision_hash="dh",
            approval_precondition_hash="pre", grant_nonce_hash="nh",
            grant_status="VALID", grant_usage_policy="SINGLE_USE_READY",
            single_use=True, expires_at="2099-01-01T00:00:00",
            created_at="t")
        kw.update(over)
        return D.build_grant(**kw)

    def _cur(self, g, **over):
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

    def test_valid(self):
        g = self._g()
        res = D.validate_grant(g, current=self._cur(g), expired=False)
        assert res["grant_validation_status"] == "VALID"
        assert res["can_execute_now"] is False

    def test_expired(self):
        g = self._g()
        res = D.validate_grant(g, current=self._cur(g), expired=True)
        assert res["grant_validation_status"] == "EXPIRED"

    def test_hash_state_drift(self):
        g = self._g()
        res = D.validate_grant(g, current=self._cur(g, run_state_hash="new"),
                               expired=False)
        assert res["grant_validation_status"] == "HASH_STATE_CHANGED"
        assert res["drift_detected"] is True

    def test_precondition_failed(self):
        g = self._g()
        res = D.validate_grant(g, current=self._cur(g,
                               precondition_status="FAILED"), expired=False)
        assert res["grant_validation_status"] == "PRECONDITION_FAILED"

    def test_always_blocked(self):
        g = self._g()
        res = D.validate_grant(g, current=self._cur(g,
                               action_always_blocked=True), expired=False)
        assert res["grant_validation_status"] == "BLOCKED"

    def test_tool_broker_required_not_consumable(self):
        g = self._g()
        res = D.validate_grant(g, current=self._cur(g,
                               tool_broker_required=True), expired=False,
                               tool_broker_available=False)
        assert res["grant_validation_status"] == "NOT_CONSUMABLE"

    def test_revoked_precedes_everything(self):
        g = self._g()
        g["revoked_at"] = "now"
        res = D.validate_grant(g, current=self._cur(g, run_state_hash="new"),
                               expired=True)
        assert res["grant_validation_status"] == "REVOKED"


class TestConsumeCheckApi:
    def test_valid_and_no_execution(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        gate.approve(ap, challenge=False)
        cc = gate.consume_check(ap["approval_request_id"])
        assert cc["grant_validation_status"] == "VALID"
        assert cc["can_execute_now"] is False
        assert cc["drift_detected"] is False
        labels = " ".join(cc["honesty_labels"])
        assert "Consume-check validates approval scope only" in labels

    def test_no_grant_is_invalid(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        cc = gate.consume_check(ap["approval_request_id"])
        assert cc["grant_validation_status"] == "INVALID"
        assert cc["approval_grant_id"] is None

    def test_tool_broker_required_not_consumable(self, gate):
        ap, _ = gate.make_request("evidence_report_request")
        gate.approve(ap, challenge=True)
        cc = gate.consume_check(ap["approval_request_id"])
        assert cc["grant_validation_status"] == "NOT_CONSUMABLE"
        assert cc["tool_broker_required"] is True
        assert cc["can_execute_now"] is False

    def test_drift_after_run_state_change(self, gate):
        ap, rid = gate.make_request("customer_reply_draft")
        gate.approve(ap, challenge=False)
        row = gate.db.one("SELECT payload_json FROM ai_runs WHERE id=?", rid)
        p = json.loads(row["payload_json"])
        p["run_state_hash"] = "deadbeef" * 8
        gate.db.conn.execute("UPDATE ai_runs SET payload_json=? WHERE id=?",
                             (json.dumps(p), rid))
        gate.db.conn.commit()
        cc = gate.consume_check(ap["approval_request_id"])
        assert cc["grant_validation_status"] == "HASH_STATE_CHANGED"
        assert cc["drift_detected"] is True

    def test_consume_check_does_not_consume(self, gate):
        # Repeated consume-checks never mark the grant consumed.
        ap, _ = gate.make_request("customer_reply_draft")
        gate.approve(ap, challenge=False)
        aid = ap["approval_request_id"]
        for _ in range(3):
            gate.consume_check(aid)
        g = gate.grant(aid)
        assert g["consumed_at"] is None
        assert g["grant_status"] != "CONSUMED"
        assert g["consume_check_count"] == 3

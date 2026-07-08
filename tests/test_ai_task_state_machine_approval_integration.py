"""CORE-A5 — approval grant integration. An approval grant validates the
lifecycle transition ONLY; it executes nothing. Invalid/expired/revoked/
superseded/drifted grants deny the APPROVED_READY transition."""
import json

from conftest import OWNER, OWNER2, MANAGER


def _to_pending(gate, tid):
    gate.walk(tid, ["APPROVAL_REQUIRED_RECORDED", "APPROVAL_REQUEST_LINKED"])


class TestApprovalIntegration:
    def test_cannot_reach_approved_ready_without_grant(self, gate):
        tid = gate.make_task("merge_proposal")
        _to_pending(gate, tid)
        r = gate.transition(tid, "APPROVAL_GRANT_VALIDATED").json()
        assert r["transition_status"] == "REQUIRES_APPROVAL"
        assert r["applied"] is False

    def test_valid_grant_allows_lifecycle_movement(self, gate):
        tid, _ = gate.approved_grant_task("merge_proposal")
        _to_pending(gate, tid)
        r = gate.transition(tid, "APPROVAL_GRANT_VALIDATED").json()
        assert r["transition_status"] == "ALLOWED"
        assert r["to_state"] == "APPROVED_READY"

    def test_grant_does_not_execute(self, gate):
        tid, _ = gate.approved_grant_task("merge_proposal")
        _to_pending(gate, tid)
        run = gate.db.one("SELECT id FROM ai_runs WHERE task_id=?", tid)
        before = gate.db.one(
            "SELECT COUNT(*) c FROM ai_run_events WHERE run_id=?",
            run["id"])["c"]
        r = gate.transition(tid, "APPROVAL_GRANT_VALIDATED").json()
        assert r["transition_status"] == "ALLOWED"
        after = gate.db.one(
            "SELECT COUNT(*) c FROM ai_run_events WHERE run_id=?",
            run["id"])["c"]
        # the lifecycle transition appended nothing to the run ledger
        assert after == before

    def test_revoked_grant_denies(self, gate):
        tid, aid = gate.approved_grant_task("merge_proposal")
        _to_pending(gate, tid)
        gate.c.post(f"/ai-approvals/{aid}/revoke", json={},
                    headers=gate.h(OWNER2))
        r = gate.transition(tid, "APPROVAL_GRANT_VALIDATED").json()
        assert r["transition_status"] == "REQUIRES_APPROVAL"
        assert "APPROVAL_GRANT_VALID_IF_REQUIRED" in r["failed_guards"]

    def test_superseded_grant_denies(self, gate):
        # A grant in SUPERSEDED state must not authorize the transition.
        tid, aid = gate.approved_grant_task("merge_proposal")
        _to_pending(gate, tid)
        g = gate.db.one("SELECT id, payload_json FROM ai_approval_grants WHERE "
                        "task_id=?", tid)
        gp = json.loads(g["payload_json"])
        gp["superseded_at"] = "2026-01-01T00:00:00"
        gp["grant_status"] = "SUPERSEDED"
        gate.db.conn.execute(
            "UPDATE ai_approval_grants SET payload_json=?, superseded_at=? "
            "WHERE id=?", (json.dumps(gp), "2026-01-01T00:00:00", g["id"]))
        gate.db.conn.commit()
        r = gate.transition(tid, "APPROVAL_GRANT_VALIDATED").json()
        assert r["transition_status"] == "REQUIRES_APPROVAL"
        assert "APPROVAL_GRANT_VALID_IF_REQUIRED" in r["failed_guards"]

    def test_expired_grant_denies(self, gate):
        tid, aid = gate.approved_grant_task("merge_proposal")
        _to_pending(gate, tid)
        g = gate.db.one("SELECT id, payload_json FROM ai_approval_grants WHERE "
                        "task_id=?", tid)
        gp = json.loads(g["payload_json"])
        gp["expires_at"] = "2000-01-01T00:00:00"
        gate.db.conn.execute(
            "UPDATE ai_approval_grants SET payload_json=?, expires_at=? "
            "WHERE id=?", (json.dumps(gp), "2000-01-01T00:00:00", g["id"]))
        gate.db.conn.commit()
        r = gate.transition(tid, "APPROVAL_GRANT_VALIDATED").json()
        assert r["transition_status"] == "REQUIRES_APPROVAL"
        assert "APPROVAL_GRANT_VALID_IF_REQUIRED" in r["failed_guards"]

    def test_hash_state_change_denies(self, gate):
        tid, aid = gate.approved_grant_task("merge_proposal")
        _to_pending(gate, tid)
        # Advance the linked run's state hash so the grant drifts.
        run = gate.db.one("SELECT id, payload_json FROM ai_runs WHERE "
                          "task_id=?", tid)
        rp = json.loads(run["payload_json"])
        rp["run_state_hash"] = "deadbeef" * 8
        gate.db.conn.execute("UPDATE ai_runs SET payload_json=? WHERE id=?",
                             (json.dumps(rp), run["id"]))
        gate.db.conn.commit()
        r = gate.transition(tid, "APPROVAL_GRANT_VALIDATED").json()
        assert r["transition_status"] == "REQUIRES_APPROVAL"
        assert "APPROVAL_GRANT_VALID_IF_REQUIRED" in r["failed_guards"]

    def test_consume_check_still_validates_only(self, gate):
        tid, aid = gate.approved_grant_task("merge_proposal")
        cc = gate.consume_check(aid)
        assert cc["can_execute_now"] is False

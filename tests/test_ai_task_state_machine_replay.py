"""CORE-A5 — replay & verify (pure + API). Replay reconstructs lifecycle state
from the transition ledger and never executes; verify detects tampering."""
import json

from finalis.ai_employee import lifecycle as L

from conftest import OWNER


def _t(frm, event, to, status="ALLOWED"):
    return {"from_state": frm, "transition_event": event, "to_state": to,
            "transition_status": status}


class TestReplayPure:
    def test_reconstructs_state(self):
        ts = [_t("ACCEPTED", "DRAFT_CREATED", "DRAFT_READY"),
              _t("DRAFT_READY", "TASK_MARKED_REVIEW_READY", "REVIEW_READY")]
        r = L.replay("ACCEPTED", ts)
        assert r["replayed_state"] == "REVIEW_READY"
        assert r["replay_errors"] == []
        assert r["applied_count"] == 2

    def test_denied_transitions_do_not_advance(self):
        ts = [_t("ACCEPTED", "TASK_COMPLETED_NO_SIDE_EFFECTS", "ACCEPTED",
                 status="DENIED")]
        assert L.replay("ACCEPTED", ts)["replayed_state"] == "ACCEPTED"

    def test_detects_invalid_ordering(self):
        ts = [_t("REVIEW_READY", "COMPLETION_CHECK_REQUESTED",
                 "COMPLETION_CHECK_REQUIRED")]   # from_state != initial
        r = L.replay("ACCEPTED", ts)
        assert r["replay_errors"]

    def test_detects_edge_not_in_graph(self):
        ts = [_t("ACCEPTED", "DRAFT_CREATED", "REVIEW_READY")]   # wrong target
        r = L.replay("ACCEPTED", ts)
        assert r["replay_errors"]

    def test_reconstructs_completion(self):
        ts = [_t("ACCEPTED", "DRAFT_CREATED", "DRAFT_READY"),
              _t("DRAFT_READY", "TASK_MARKED_REVIEW_READY", "REVIEW_READY"),
              _t("REVIEW_READY", "COMPLETION_CHECK_REQUESTED",
                 "COMPLETION_CHECK_REQUIRED"),
              _t("COMPLETION_CHECK_REQUIRED", "TASK_COMPLETED_NO_SIDE_EFFECTS",
                 "COMPLETED_NO_SIDE_EFFECTS")]
        r = L.replay("ACCEPTED", ts)
        assert r["replayed_state"] == "COMPLETED_NO_SIDE_EFFECTS"
        assert r["replay_completion_status"] == "READY"


class TestVerifyApi:
    def test_verify_detects_payload_tamper(self, gate):
        tid = gate.make_task("case_summary")
        gate.transition(tid, "DRAFT_CREATED")
        row = gate.db.one(
            "SELECT id, payload_json FROM ai_task_transitions WHERE task_id=?",
            tid)
        p = json.loads(row["payload_json"])
        p["to_state"] = "REVIEW_READY"       # stale transition_hash
        gate.db.conn.execute(
            "UPDATE ai_task_transitions SET payload_json=? WHERE id=?",
            (json.dumps(p), row["id"]))
        gate.db.conn.commit()
        v = gate.c.post(f"/ai-tasks/{tid}/transitions/verify",
                        headers=gate.h(OWNER)).json()
        assert v["verification_status"] == "MISMATCHED"
        assert v["tamper_detected"] is True

    def test_verify_detects_hash_tamper(self, gate):
        tid = gate.make_task("case_summary")
        gate.transition(tid, "DRAFT_CREATED")
        row = gate.db.one(
            "SELECT id, payload_json FROM ai_task_transitions WHERE task_id=?",
            tid)
        p = json.loads(row["payload_json"])
        p["transition_hash"] = "deadbeef" * 8
        gate.db.conn.execute(
            "UPDATE ai_task_transitions SET payload_json=? WHERE id=?",
            (json.dumps(p), row["id"]))
        gate.db.conn.commit()
        v = gate.c.post(f"/ai-tasks/{tid}/transitions/verify",
                        headers=gate.h(OWNER)).json()
        assert v["verification_status"] == "MISMATCHED"

    def test_replay_does_not_execute(self, gate):
        tid = gate.make_task("case_summary")
        gate.transition(tid, "DRAFT_CREATED")
        before = gate.lc_state(tid)["task_version"]
        r = gate.c.post(f"/ai-tasks/{tid}/transitions/replay",
                        headers=gate.h(OWNER)).json()
        assert r["executed_task"] is False
        assert gate.lc_state(tid)["task_version"] == before

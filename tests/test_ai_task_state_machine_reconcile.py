"""CORE-A5 — reconciliation. Compares stored vs replayed vs completion vs
linked hashes; reports MATCHED/MISMATCHED and never auto-heals silently."""
import json

from conftest import OWNER


class TestReconcile:
    def test_matched_clean(self, gate):
        tid = gate.make_task("case_summary")
        gate.walk(tid, ["DRAFT_CREATED", "TASK_MARKED_REVIEW_READY"])
        r = gate.c.post(f"/ai-tasks/{tid}/transitions/reconcile",
                        headers=gate.h(OWNER)).json()
        assert r["reconciliation_status"] == "MATCHED"
        assert all(r["factors"].values())
        assert r["lifecycle_reconciliation_hash"]

    def test_mismatch_on_ledger_tamper(self, gate):
        tid = gate.make_task("case_summary")
        gate.transition(tid, "DRAFT_CREATED")
        row = gate.db.one(
            "SELECT id, payload_json FROM ai_task_transitions WHERE task_id=?",
            tid)
        p = json.loads(row["payload_json"])
        p["to_state"] = "REVIEW_READY"
        gate.db.conn.execute(
            "UPDATE ai_task_transitions SET payload_json=? WHERE id=?",
            (json.dumps(p), row["id"]))
        gate.db.conn.commit()
        r = gate.c.post(f"/ai-tasks/{tid}/transitions/reconcile",
                        headers=gate.h(OWNER)).json()
        assert r["reconciliation_status"] == "MISMATCHED"

    def test_does_not_auto_heal(self, gate):
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
        r = gate.c.post(f"/ai-tasks/{tid}/transitions/reconcile",
                        headers=gate.h(OWNER)).json()
        assert r["auto_healed"] is False
        # stored state unchanged (no silent correction)
        assert gate.lc_state(tid)["lifecycle_state"] == "DRAFT_READY"

    def test_no_silent_heal_on_state_divergence(self, gate):
        # Tamper a stored to_state so replay diverges from stored state; the
        # stored state must NOT be silently rewritten to the replayed value.
        tid = gate.make_task("case_summary")
        gate.walk(tid, ["DRAFT_CREATED", "TASK_MARKED_REVIEW_READY"])
        stored_before = gate.lc_state(tid)["lifecycle_state"]
        # Tamper the FIRST transition so replay breaks mid-chain while the
        # derived stored state (latest to_state) stays REVIEW_READY.
        row = gate.db.one(
            "SELECT id, payload_json FROM ai_task_transitions WHERE task_id=? "
            "AND transition_index=0", tid)
        p = json.loads(row["payload_json"])
        p["to_state"] = "COMPLETION_CHECK_REQUIRED"   # diverges from graph
        gate.db.conn.execute(
            "UPDATE ai_task_transitions SET payload_json=? WHERE id=?",
            (json.dumps(p), row["id"]))
        gate.db.conn.commit()
        r = gate.c.post(f"/ai-tasks/{tid}/transitions/reconcile",
                        headers=gate.h(OWNER)).json()
        assert r["reconciliation_status"] == "MISMATCHED"
        assert r["auto_healed"] is False
        # stored state is unchanged (no silent correction)
        assert gate.lc_state(tid)["lifecycle_state"] == stored_before

    def test_reconcile_does_not_execute(self, gate):
        tid = gate.make_task("case_summary")
        gate.transition(tid, "DRAFT_CREATED")
        before = gate.lc_state(tid)["task_version"]
        gate.c.post(f"/ai-tasks/{tid}/transitions/reconcile",
                    headers=gate.h(OWNER))
        assert gate.lc_state(tid)["task_version"] == before

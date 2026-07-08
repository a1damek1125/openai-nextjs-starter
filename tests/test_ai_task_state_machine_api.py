"""CORE-A5 — Task State Machine API surface (endpoints exist; dry-run/apply/
verify/replay/reconcile behave; responses carry hashes + honesty labels)."""
from conftest import OWNER, MANAGER


class TestEndpointsExist:
    def test_state_machine_matrix(self, gate):
        m = gate.c.get("/ai-tasks/state-machine", headers=gate.h(OWNER)).json()
        assert m["states"] and m["events"] and m["edges"]

    def test_state_machine_verify(self, gate):
        v = gate.c.get("/ai-tasks/state-machine/verify",
                       headers=gate.h(OWNER)).json()
        assert v["graph_verification_status"] == "MATCHED"

    def test_state_endpoint(self, gate):
        tid = gate.make_task("case_summary")
        s = gate.lc_state(tid)
        assert s["lifecycle_state"] == "ACCEPTED"
        assert s["task_state_hash"]
        assert s["allowed_next_transitions"]
        assert "completion_status" in s
        assert "reconciliation_status" in s

    def test_transitions_list(self, gate):
        tid = gate.make_task("case_summary")
        gate.transition(tid, "DRAFT_CREATED")
        lst = gate.c.get(f"/ai-tasks/{tid}/transitions",
                         headers=gate.h(OWNER)).json()
        assert len(lst["transitions"]) == 1
        assert lst["transitions"][0]["from_state"] == "ACCEPTED"

    def test_dashboard(self, gate):
        gate.make_task("case_summary")
        d = gate.c.get("/ai-tasks/lifecycle-dashboard",
                       headers=gate.h(OWNER)).json()
        assert "tasks_by_state" in d and "top_blockers" in d


class TestDryRunApply:
    def test_dry_run_does_not_mutate(self, gate):
        tid = gate.make_task("case_summary")
        v0 = gate.lc_state(tid)["task_version"]
        r = gate.dry_run(tid, "DRAFT_CREATED").json()
        assert r["transition_status"] == "ALLOWED" and r["dry_run"] is True
        assert gate.lc_state(tid)["task_version"] == v0
        assert gate.lc_state(tid)["lifecycle_state"] == "ACCEPTED"

    def test_apply_mutates_state_and_version(self, gate):
        tid = gate.make_task("case_summary")
        v0 = gate.lc_state(tid)["task_version"]
        r = gate.transition(tid, "DRAFT_CREATED").json()
        assert r["applied"] is True and r["to_state"] == "DRAFT_READY"
        s = gate.lc_state(tid)
        assert s["lifecycle_state"] == "DRAFT_READY"
        assert s["task_version"] == v0 + 1
        assert isinstance(s["task_state_hash"], str) \
            and len(s["task_state_hash"]) == 64

    def test_task_state_hash_changes_after_apply(self, gate):
        tid = gate.make_task("case_summary")
        h0 = gate.lc_state(tid)["task_state_hash"]
        gate.transition(tid, "DRAFT_CREATED")
        assert gate.lc_state(tid)["task_state_hash"] != h0

    def test_invalid_transition_denied_records_reason(self, gate):
        tid = gate.make_task("case_summary")
        r = gate.transition(tid, "TASK_COMPLETED_NO_SIDE_EFFECTS").json()
        assert r["transition_status"] == "DENIED"
        assert r["blocked_reason"]
        lst = gate.c.get(f"/ai-tasks/{tid}/transitions",
                         headers=gate.h(OWNER)).json()["transitions"]
        assert lst[-1]["transition_status"] == "DENIED"

    def test_transition_records_actor_and_hashes(self, gate):
        tid = gate.make_task("case_summary")
        gate.transition(tid, "DRAFT_CREATED")
        t = gate.c.get(f"/ai-tasks/{tid}/transitions",
                       headers=gate.h(OWNER)).json()["transitions"][0]
        assert t["requested_by_actor_type"] == "human"
        assert t["requested_by_actor_id"]
        assert t["transition_hash"] and t["guard_vector_hash"]
        assert t["from_state"] == "ACCEPTED" and t["to_state"] == "DRAFT_READY"
        assert t["guard_results"]

    def test_all_responses_have_honesty_labels(self, gate):
        tid = gate.make_task("case_summary")
        for resp in [gate.lc_state(tid),
                     gate.dry_run(tid, "DRAFT_CREATED").json(),
                     gate.transition(tid, "DRAFT_CREATED").json()]:
            labels = " ".join(resp["honesty_labels"])
            assert "does not execute the action" in labels
            assert "Server-side task state is authoritative." in labels


class TestVerifyReplayReconcile:
    def test_verify_matched(self, gate):
        tid = gate.make_task("case_summary")
        gate.walk(tid, ["DRAFT_CREATED", "TASK_MARKED_REVIEW_READY"])
        v = gate.c.post(f"/ai-tasks/{tid}/transitions/verify",
                        headers=gate.h(OWNER)).json()
        assert v["verification_status"] == "MATCHED"
        assert v["tamper_detected"] is False

    def test_replay_reconstructs_state(self, gate):
        tid = gate.make_task("case_summary")
        gate.walk(tid, ["DRAFT_CREATED", "TASK_MARKED_REVIEW_READY"])
        r = gate.c.post(f"/ai-tasks/{tid}/transitions/replay",
                        headers=gate.h(OWNER)).json()
        assert r["replay_status"] == "MATCHED"
        assert r["replayed_state"] == "REVIEW_READY"
        assert r["executed_task"] is False

    def test_reconcile_matched(self, gate):
        tid = gate.make_task("case_summary")
        gate.transition(tid, "DRAFT_CREATED")
        r = gate.c.post(f"/ai-tasks/{tid}/transitions/reconcile",
                        headers=gate.h(OWNER)).json()
        assert r["reconciliation_status"] == "MATCHED"
        assert r["auto_healed"] is False

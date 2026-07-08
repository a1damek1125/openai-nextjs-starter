"""CORE-A5 — transition idempotency & optimistic-version race safety."""
from conftest import OWNER, MANAGER, OTHER_OWNER


class TestIdempotency:
    def test_same_key_same_input_replays(self, gate):
        tid = gate.make_task("case_summary")
        r1 = gate.transition(tid, "DRAFT_CREATED",
                             transition_idempotency_key="k1").json()
        r2 = gate.transition(tid, "DRAFT_CREATED",
                             transition_idempotency_key="k1").json()
        assert r2["idempotent_replay"] is True
        assert r1["to_state"] == r2["to_state"]
        # version advanced exactly once
        assert gate.lc_state(tid)["task_version"] == 2

    def test_same_key_different_input_conflict(self, gate):
        tid = gate.make_task("case_summary")
        gate.transition(tid, "DRAFT_CREATED", transition_idempotency_key="k1")
        r = gate.transition(tid, "TASK_MARKED_REVIEW_READY",
                            transition_idempotency_key="k1")
        assert r.status_code == 409

    def test_cross_tenant_keys_do_not_collide(self, gate):
        t1 = gate.make_task("case_summary")
        gate.transition(t1, "DRAFT_CREATED", transition_idempotency_key="dup")
        # other tenant owner creates its own (subject-less) task + same key
        hdr = gate.h(OTHER_OWNER)
        tk = gate.c.post("/ai-tasks", json={
            "task_type": "research_brief", "task_title": "t",
            "task_description": "please do the thing"}, headers=hdr).json()[
            "task_id"]
        r = gate.c.post(f"/ai-tasks/{tk}/transitions", json={
            "transition_event": "DRAFT_CREATED",
            "transition_idempotency_key": "dup"}, headers=hdr).json()
        assert r["applied"] is True   # no collision across tenants

    def test_stale_expected_version(self, gate):
        tid = gate.make_task("case_summary")
        r = gate.transition(tid, "DRAFT_CREATED",
                            expected_task_version=999).json()
        assert r["transition_status"] == "STALE_VERSION"

    def test_dry_run_does_not_increment_version(self, gate):
        tid = gate.make_task("case_summary")
        v0 = gate.lc_state(tid)["task_version"]
        gate.dry_run(tid, "DRAFT_CREATED", transition_idempotency_key="dr")
        assert gate.lc_state(tid)["task_version"] == v0

    def test_dry_run_does_not_consume_apply_key(self, gate):
        tid = gate.make_task("case_summary")
        gate.dry_run(tid, "DRAFT_CREATED", transition_idempotency_key="shared")
        # apply with the same key still applies (dry-run did not persist it)
        r = gate.transition(tid, "DRAFT_CREATED",
                            transition_idempotency_key="shared").json()
        assert r.get("idempotent_replay") is not True
        assert r["applied"] is True

    def test_apply_increments_version_once(self, gate):
        tid = gate.make_task("case_summary")
        v0 = gate.lc_state(tid)["task_version"]
        gate.transition(tid, "DRAFT_CREATED")
        assert gate.lc_state(tid)["task_version"] == v0 + 1

    def test_terminal_cannot_be_reopened_by_retry(self, gate):
        tid = gate.make_task("case_summary")
        gate.walk(tid, ["DRAFT_CREATED", "TASK_MARKED_REVIEW_READY",
                        "COMPLETION_CHECK_REQUESTED",
                        "TASK_COMPLETED_NO_SIDE_EFFECTS"])
        assert gate.lc_state(tid)["lifecycle_state"] \
            == "COMPLETED_NO_SIDE_EFFECTS"
        r = gate.transition(tid, "TASK_MARKED_RUN_READY").json()
        assert r["transition_status"] in ("DENIED", "BLOCKED")
        assert r["applied"] is False

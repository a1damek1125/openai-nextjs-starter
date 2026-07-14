"""CORE-A5 — RBAC / tenant isolation for the Task State Machine."""
from conftest import OWNER, MANAGER, VIEWER, OTHER_OWNER


class TestRbac:
    def test_viewer_cannot_transition(self, gate):
        tid = gate.make_task("case_summary")
        assert gate.transition(tid, "DRAFT_CREATED",
                               actor=VIEWER).status_code == 403

    def test_viewer_can_read_state(self, gate):
        tid = gate.make_task("case_summary")
        assert gate.c.get(f"/ai-tasks/{tid}/state",
                          headers=gate.h(VIEWER)).status_code == 200

    def test_ai_worker_cannot_transition(self, gate):
        gate.add_user("bot@demo.finalis", "ai_worker")
        tid = gate.make_task("case_summary")
        assert gate.transition(tid, "DRAFT_CREATED",
                               actor="bot@demo.finalis").status_code == 403

    def test_ai_worker_cannot_dry_run(self, gate):
        gate.add_user("bot@demo.finalis", "ai_worker")
        tid = gate.make_task("case_summary")
        assert gate.dry_run(tid, "DRAFT_CREATED",
                            actor="bot@demo.finalis").status_code == 403


class TestTenantIsolation:
    def test_cross_tenant_state_read_denied(self, gate):
        tid = gate.make_task("case_summary")
        assert gate.c.get(f"/ai-tasks/{tid}/state",
                          headers=gate.h(OTHER_OWNER)).status_code == 404

    def test_cross_tenant_transition_denied(self, gate):
        tid = gate.make_task("case_summary")
        assert gate.transition(tid, "DRAFT_CREATED",
                               actor=OTHER_OWNER).status_code == 404

    def test_cross_tenant_dry_run_denied(self, gate):
        tid = gate.make_task("case_summary")
        assert gate.dry_run(tid, "DRAFT_CREATED",
                            actor=OTHER_OWNER).status_code == 404

    def test_cross_tenant_completion_check_denied(self, gate):
        tid = gate.make_task("case_summary")
        assert gate.c.post(f"/ai-tasks/{tid}/completion/check",
                           headers=gate.h(OTHER_OWNER)).status_code == 404

    def test_cross_tenant_reconcile_denied(self, gate):
        tid = gate.make_task("case_summary")
        assert gate.c.post(f"/ai-tasks/{tid}/transitions/reconcile",
                           headers=gate.h(OTHER_OWNER)).status_code == 404

    def test_unknown_task_safe_not_found(self, gate):
        assert gate.c.get("/ai-tasks/nope/state",
                          headers=gate.h(OWNER)).status_code == 404
        assert gate.transition("nope", "DRAFT_CREATED").status_code == 404

    def test_admin_owner_can_transition(self, gate):
        tid = gate.make_task("case_summary")
        assert gate.transition(tid, "DRAFT_CREATED",
                               actor=OWNER).json()["applied"] is True

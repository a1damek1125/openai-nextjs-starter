"""TOOL-B2 RBAC and tenant isolation.

Running a quality check requires case.update; every quality read requires
case.read. The gate is deterministic so an ai_worker may run it, but it is
recorded as an ai_employee actor, never a human. All cross-tenant access 404s.
"""
from tests.conftest import OWNER, MANAGER, VIEWER, OTHER_OWNER

READ_ENDPOINTS = ["", "/history", "/safe", "/matrix", "/evidence",
                  "/assurance", "/ir", "/graph", "/confusion",
                  "/selection-boundary", "/non-regression"]


class TestCheckRequiresUpdate:
    def test_viewer_cannot_run_check(self, gate):
        tid = gate.register_quality_tool().json()["tool_id"]
        assert gate.q(tid, "/check", actor=VIEWER,
                      method="POST").status_code == 403

    def test_manager_can_run_check(self, gate):
        tid = gate.register_quality_tool(requester=MANAGER).json()["tool_id"]
        r = gate.quality_check(tid, actor=MANAGER)
        assert r.status_code == 200
        assert r.json()["quality_status"] == "QUALITY_PASS"

    def test_owner_can_run_check(self, gate):
        tid = gate.register_quality_tool().json()["tool_id"]
        assert gate.quality_check(tid, actor=OWNER).status_code == 200


class TestReadsRequireRead:
    def test_viewer_can_read_all_quality_views(self, gate):
        tid, _ = gate.checked_quality_tool()   # owner ran the check
        for path in READ_ENDPOINTS:
            assert gate.q(tid, path, actor=VIEWER).status_code == 200, path

    def test_safe_view_redacts_ir_for_viewer(self, gate):
        tid, _ = gate.checked_quality_tool()
        owner_view = gate.q(tid, "/safe", actor=OWNER).json()
        viewer_view = gate.q(tid, "/safe", actor=VIEWER).json()
        # Owner sees a structured IR summary; viewer sees a redaction marker.
        assert isinstance(owner_view["ir_summary"], dict)
        assert isinstance(viewer_view["ir_summary"], str)
        assert "REDACTED" in viewer_view["ir_summary"]

    def test_owner_can_read_registry_summary(self, gate):
        gate.checked_quality_tool()
        assert gate.c.get("/ai-tools/registry/quality",
                          headers=gate.h(OWNER)).status_code == 200
        assert gate.c.get("/ai-tools/registry/quality",
                          headers=gate.h(VIEWER)).status_code == 200


class TestActorTyping:
    def test_ai_worker_recorded_as_ai_employee_not_human(self, gate):
        gate.add_user("ai@demo.finalis", "ai_worker")
        tid = gate.register_quality_tool().json()["tool_id"]
        gate.quality_check(tid, actor="ai@demo.finalis")
        evs = gate.c.get(f"/ai-tools/{tid}/quality/binding-ledger",
                         headers=gate.h(OWNER)).json()["events"]
        actor_types = {e["actor_type"] for e in evs}
        assert actor_types == {"ai_employee"}
        assert "human" not in actor_types

    def test_owner_check_recorded_as_human(self, gate):
        tid, _ = gate.checked_quality_tool()
        evs = gate.c.get(f"/ai-tools/{tid}/quality/binding-ledger",
                         headers=gate.h(OWNER)).json()["events"]
        assert {e["actor_type"] for e in evs} == {"human"}


class TestCrossTenant:
    def test_cross_tenant_check_404(self, gate):
        tid = gate.register_quality_tool().json()["tool_id"]
        assert gate.q(tid, "/check", actor=OTHER_OWNER,
                      method="POST").status_code == 404

    def test_cross_tenant_read_404(self, gate):
        tid, _ = gate.checked_quality_tool()
        for path in ("", "/history", "/matrix", "/ir"):
            assert gate.q(tid, path, actor=OTHER_OWNER).status_code == 404, path

    def test_cross_tenant_verify_404(self, gate):
        tid, _ = gate.checked_quality_tool()
        assert gate.q(tid, "/verify", actor=OTHER_OWNER,
                      method="POST").status_code == 404

    def test_cross_tenant_binding_ledger_404(self, gate):
        tid, _ = gate.checked_quality_tool()
        assert gate.c.get(f"/ai-tools/{tid}/quality/binding-ledger",
                          headers=gate.h(OTHER_OWNER)).status_code == 404


class TestOwnerCanDoEverything:
    def test_owner_full_surface(self, gate):
        tid, _ = gate.checked_quality_tool()
        assert gate.q(tid, "/check", method="POST").status_code == 200
        for path in READ_ENDPOINTS:
            assert gate.q(tid, path, actor=OWNER).status_code == 200, path
        assert gate.q(tid, "/verify", method="POST").status_code == 200

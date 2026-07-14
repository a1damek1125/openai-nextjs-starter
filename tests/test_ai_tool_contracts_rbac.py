"""TOOL-B3 RBAC + tenant isolation + actor provenance.

Create and project require case.update (viewer denied, manager allowed); all
reads require case.read (viewer allowed, with redaction on /safe); cross-tenant
access is 404 everywhere; an ai_worker-authored contract is recorded as
actor_type "ai_employee", never "human".
"""
from conftest import OWNER, MANAGER, VIEWER, OTHER_OWNER

AI_WORKER = "ai@demo.finalis"


class TestCreateRbac:
    def test_viewer_cannot_create(self, gate):
        tid = gate.contract_tool()
        assert gate.create_contract(tid, actor=VIEWER).status_code == 403

    def test_manager_can_create(self, gate):
        # manager has case.update.
        tid = gate.contract_tool()
        assert gate.create_contract(tid, actor=MANAGER).status_code == 200

    def test_owner_can_create(self, gate):
        tid = gate.contract_tool()
        assert gate.create_contract(tid, actor=OWNER).status_code == 200

    def test_ai_worker_can_create(self, gate):
        # ai_worker also holds case.update.
        gate.add_user(AI_WORKER, "ai_worker")
        tid = gate.contract_tool()
        assert gate.create_contract(tid, actor=AI_WORKER).status_code == 200


class TestProjectRbac:
    def test_viewer_cannot_project(self, gate):
        tid, c = gate.contracted_tool()
        assert gate.project(tid, c["contract_id"],
                            actor=VIEWER).status_code == 403

    def test_manager_can_project(self, gate):
        tid, c = gate.contracted_tool()
        assert gate.project(tid, c["contract_id"],
                            actor=MANAGER).status_code == 200

    def test_owner_can_project(self, gate):
        tid, c = gate.contracted_tool()
        assert gate.project(tid, c["contract_id"],
                            actor=OWNER).status_code == 200


class TestReadRbac:
    def test_viewer_can_read_safe_view(self, gate):
        tid, c = gate.contracted_tool()
        assert gate.ct(tid, c["contract_id"], path="/safe",
                       actor=VIEWER).status_code == 200

    def test_viewer_safe_view_redacts_description(self, gate):
        tid, c = gate.contracted_tool()
        sv = gate.ct(tid, c["contract_id"], path="/safe", actor=VIEWER).json()
        assert sv["description_safe"] == "[REDACTED]"

    def test_owner_safe_view_not_redacted(self, gate):
        tid, c = gate.contracted_tool()
        sv = gate.ct(tid, c["contract_id"], path="/safe", actor=OWNER).json()
        assert sv["description_safe"] != "[REDACTED]"

    def test_viewer_can_read_detail_endpoints(self, gate):
        tid, c = gate.contracted_tool()
        for path in ("", "/normal-form", "/abi", "/proof-bundle"):
            r = gate.ct(tid, c["contract_id"], path=path, actor=VIEWER)
            assert r.status_code == 200, (path, r.status_code)


class TestTenantIsolation:
    def test_cross_tenant_create_404(self, gate):
        tid = gate.contract_tool()
        assert gate.create_contract(tid, actor=OTHER_OWNER).status_code == 404

    def test_cross_tenant_read_404(self, gate):
        tid, c = gate.contracted_tool()
        assert gate.ct(tid, c["contract_id"],
                       actor=OTHER_OWNER).status_code == 404

    def test_cross_tenant_project_404(self, gate):
        tid, c = gate.contracted_tool()
        assert gate.project(tid, c["contract_id"],
                            actor=OTHER_OWNER).status_code == 404

    def test_cross_tenant_verify_404(self, gate):
        tid, c = gate.contracted_tool()
        assert gate.ct(tid, c["contract_id"], path="/verify", method="POST",
                       actor=OTHER_OWNER).status_code == 404


class TestActorProvenance:
    def test_ai_worker_contract_recorded_as_ai_employee(self, gate):
        gate.add_user(AI_WORKER, "ai_worker")
        tid = gate.contract_tool()
        c = gate.create_contract(tid, actor=AI_WORKER).json()
        assert c["created_by_actor_type"] == "ai_employee"

    def test_ai_worker_ledger_events_never_human(self, gate):
        gate.add_user(AI_WORKER, "ai_worker")
        tid = gate.contract_tool()
        c = gate.create_contract(tid, actor=AI_WORKER).json()
        led = gate.ct(tid, c["contract_id"], path="/revocation-ledger",
                      actor=OWNER).json()
        actor_types = [e["actor_type"] for e in led["events"]]
        assert actor_types
        assert "human" not in actor_types
        assert all(a == "ai_employee" for a in actor_types)

    def test_human_owner_contract_recorded_as_human(self, gate):
        tid, c = gate.contracted_tool()
        assert c["created_by_actor_type"] == "human"

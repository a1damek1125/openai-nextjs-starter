"""CORE-A6 — RBAC / tenant isolation for the Artifact System."""
from conftest import OWNER, MANAGER, VIEWER, OTHER_OWNER


class TestRbac:
    def test_viewer_cannot_create(self, gate):
        assert gate.make_artifact("RESEARCH_NOTE", "x",
                                  requester=VIEWER).status_code == 403

    def test_viewer_can_read(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "x").json()
        assert gate.art(a["artifact_id"], actor=VIEWER).status_code == 200

    def test_ai_worker_creates_ai_draft_tier(self, gate):
        gate.add_user("bot@demo.finalis", "ai_worker")
        a = gate.make_artifact("CASE_SUMMARY_DRAFT", "draft",
                               requester="bot@demo.finalis").json()
        # AI-created artifacts are AI_DRAFT_UNVERIFIED, not human truth
        assert a["artifact_trust_tier"] == "AI_DRAFT_UNVERIFIED"
        assert a["created_by_actor_type"] == "ai_employee"

    def test_ai_worker_cannot_be_human_reviewed(self, gate):
        gate.add_user("bot@demo.finalis", "ai_worker")
        a = gate.make_artifact("CASE_SUMMARY_DRAFT", "draft",
                               requester="bot@demo.finalis").json()
        assert a["artifact_trust_tier"] != "HUMAN_REVIEWED"


class TestTenantIsolation:
    def test_cross_tenant_read_denied(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "x").json()
        assert gate.art(a["artifact_id"], actor=OTHER_OWNER).status_code == 404

    def test_cross_tenant_version_read_denied(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "x").json()
        assert gate.art(a["artifact_id"], "/versions",
                        actor=OTHER_OWNER).status_code == 404

    def test_cross_tenant_verify_denied(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "x").json()
        assert gate.art(a["artifact_id"], "/verify", actor=OTHER_OWNER,
                        method="POST").status_code == 404

    def test_cross_tenant_provenance_denied(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "x").json()
        assert gate.art(a["artifact_id"], "/provenance",
                        actor=OTHER_OWNER).status_code == 404

    def test_cross_tenant_claims_denied(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "x").json()
        assert gate.art(a["artifact_id"], "/claims",
                        actor=OTHER_OWNER).status_code == 404

    def test_cross_tenant_safe_view_denied(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "x").json()
        assert gate.art(a["artifact_id"], "/safe",
                        actor=OTHER_OWNER).status_code == 404

    def test_cross_tenant_materialization_denied(self, gate):
        a = gate.make_artifact("RESEARCH_NOTE", "x").json()
        assert gate.art(a["artifact_id"], "/materialization-check",
                        actor=OTHER_OWNER, method="POST").status_code == 404

    def test_unknown_artifact_safe_not_found(self, gate):
        assert gate.art("nope").status_code == 404
        assert gate.art("nope", "/verify", method="POST").status_code == 404

    def test_cross_tenant_task_link_denied(self, gate):
        # linking to a task in another tenant fails (task not found in tenant)
        tid = gate.make_task("case_summary")
        r = gate.c.post("/ai-artifacts", json={
            "artifact_type": "CASE_SUMMARY_DRAFT", "content_body": "x",
            "task_id": tid}, headers=gate.h(OTHER_OWNER))
        assert r.status_code == 404

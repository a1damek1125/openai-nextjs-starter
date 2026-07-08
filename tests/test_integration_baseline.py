"""CONSOLIDATE-1 integration safety tests — migrations, route registry,
RBAC catalog, and cross-module smoke over the merged baseline
(Portal Wiring + Quotes + Scheduling + Evidence V-A..V-E + CRM-A/B).

No feature tests here: this file exists to catch integration damage —
duplicate migration numbers, route collisions, permission conflicts,
startup regressions.
"""
import base64

import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.db import MIGRATIONS, Database
from finalis.portal.seed import seed

EXPECTED_DB_VERSION = 8


@pytest.fixture()
def client():
    app = create_app(":memory:")
    seed(app.state.db)
    return TestClient(app)


def login(client, email="owner@demo.finalis", password="demo1234"):
    r = client.post("/auth/login", json={"email": email,
                                         "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _tables(db):
    return {r["name"] for r in db.all(
        "SELECT name FROM sqlite_master WHERE type='table'")}


class TestMigrations:
    def test_1_2_3_order_version_and_no_duplicates(self, tmp_path):
        versions = [v for v, _ in MIGRATIONS]
        assert versions == sorted(versions)               # ordered
        assert len(versions) == len(set(versions))        # no duplicates
        assert versions == list(range(1, EXPECTED_DB_VERSION + 1))  # no gaps
        db = Database(str(tmp_path / "clean.db"))         # from empty DB
        assert db.migrate() == EXPECTED_DB_VERSION
        assert db.one("SELECT MAX(version) v FROM schema_version")["v"] \
            == EXPECTED_DB_VERSION

    def test_4_5_6_7_8_all_module_tables_exist(self, tmp_path):
        tables = _tables(Database(str(tmp_path / "t.db")))
        # Portal base.
        assert {"tenants", "users", "cases", "parties",
                "audit_events"} <= tables
        # Quote Builder (v3).
        assert {"quotes", "quote_line_items", "price_books",
                "pricing_rules", "quote_approvals", "change_orders",
                "payment_requirements", "quote_pdf_documents"} <= tables
        # Scheduling persistence (v4).
        assert {"scheduling_appointments",
                "scheduling_appointment_events"} <= tables
        # Evidence Trust Fabric (v5).
        assert {"evidence_objects", "evidence_chain_events",
                "evidence_access_events", "evidence_decision_contracts",
                "evidence_legal_holds"} <= tables
        # Evidence V-E hardening (v6).
        assert {"evidence_derivatives", "evidence_retention_policies",
                "evidence_merkle_roots",
                "evidence_policy_versions"} <= tables
        # CRM Relationship Core (v7, renumbered from the CRM branch's v6).
        assert {"crm_parties", "crm_contact_points", "crm_consent_records",
                "crm_relationship_edges", "crm_promises",
                "crm_memory_items", "crm_merge_decisions",
                "crm_external_references",
                "crm_external_sync_events"} <= tables
        # Canonical Evidence Report Package registry (v8).
        assert {"evidence_proof_reports"} <= tables

    def test_evidence_ve_columns_survived_renumber(self, tmp_path):
        db = Database(str(tmp_path / "c.db"))
        cols = {r["name"] for r in db.all(
            "PRAGMA table_info(evidence_decision_contracts)")}
        assert {"contract_hash", "policy_version",
                "causal_result"} <= cols


class TestRouteRegistry:
    def test_10_no_duplicate_method_path_pairs(self, client):
        seen = {}
        for route in client.app.routes:
            path = getattr(route, "path", None)
            methods = getattr(route, "methods", None) or set()
            for m in methods - {"HEAD", "OPTIONS"}:
                key = (m, path)
                assert key not in seen, f"duplicate route {key}"
                seen[key] = route
        assert len(seen) > 100                # merged surface is intact

    def test_11_no_public_raw_or_admin_leak_routes(self, client):
        for route in client.app.routes:
            path = (getattr(route, "path", "") or "").lower()
            if path.startswith("/evidence"):
                assert "raw" not in path and "download" not in path, path
        # Unauthenticated probes on merged sensitive surfaces.
        for probe in ("/evidence", "/crm/parties", "/quotes",
                      "/admin/users", "/evidence/contracts"):
            assert client.get(probe).status_code == 401, probe

    def test_crm_route_does_not_shadow_legacy_parties(self, client):
        # CRM lives under /crm/* — no route claims the bare /parties path.
        paths = {getattr(r, "path", "") for r in client.app.routes}
        assert "/crm/parties" in paths
        assert "/parties" not in paths


class TestRbacCatalog:
    def test_12_catalog_consistent(self):
        from finalis.admin.rbac import PERMISSIONS, ROLE_PERMISSIONS
        # Every role grants only cataloged permissions; no phantom names.
        for role, perms in ROLE_PERMISSIONS.items():
            unknown = perms - set(PERMISSIONS)
            assert not unknown, f"{role} grants unknown perms {unknown}"
        # The structural safety invariant survived every merge.
        assert "ai.approve_own_action" not in PERMISSIONS
        # ai_worker holds no human-judgment permissions.
        ai = ROLE_PERMISSIONS["ai_worker"]
        for forbidden in ("action.approve", "action.approve_high_risk",
                          "override.hard", "payment.mark_paid",
                          "tenant.manage_users", "document.delete",
                          "override.compliance_review", "offer.approve"):
            assert forbidden not in ai, forbidden
        # Viewer cannot mutate anything sensitive.
        viewer = ROLE_PERMISSIONS["viewer"]
        for forbidden in ("document.upload", "document.analyze",
                          "case.update", "offer.create", "offer.approve",
                          "tenant.manage_users", "audit.view",
                          "override.compliance_review"):
            assert forbidden not in viewer, forbidden


class TestCrossModuleSmoke:
    """One authenticated pass across every merged module."""

    def test_13_18_owner_smoke_all_modules(self, client):
        h = login(client)
        case_id = client.get("/cases", headers=h).json()[0]["id"]

        # Quote smoke (Q-B).
        q = client.post("/quotes", json={"case_id": case_id}, headers=h)
        assert q.status_code == 200

        # Scheduling smoke (SCHED-V4).
        s = client.post("/scheduling/appointments", json={
            "case_id": case_id, "appointment_type": "CALLBACK",
            "start_at": "2030-03-13T10:00:00"}, headers=h)
        assert s.status_code == 200
        assert client.get("/scheduling/appointments",
                          headers=h).status_code == 200

        # Evidence smoke (V-B + V-E).
        ev = client.post("/evidence/upload", json={
            "case_id": case_id, "filename": "smoke.txt",
            "mime": "text/plain",
            "content_b64": base64.b64encode(b"smoke 450 EUR").decode(),
            "evidence_type": "payment_proof",
            "text_preview": "smoke 450 EUR"}, headers=h).json()
        assert ev["state"] == "QUARANTINED"
        assert client.get(f"/evidence/{ev['id']}/chain",
                          headers=h).status_code == 200
        assert client.get("/evidence/policy-version",
                          headers=h).status_code == 200
        assert client.post("/evidence/merkle-roots/generate",
                           headers=h).status_code == 200

        # CRM smoke (CRM-B).
        p = client.post("/crm/parties", json={
            "kind": "person", "display_name": "Smoke Person",
            "contact_points": [{"kind": "EMAIL",
                                "value": "smoke@example.pl"}]},
            headers=h)
        assert p.status_code == 200
        assert client.post("/crm/relationships", json={
            "from_id": p.json()["id"], "to_id": case_id,
            "to_kind": "case"}, headers=h).status_code == 200
        check = client.post("/crm/consent/check", json={
            "party_id": p.json()["id"], "channel": "EMAIL",
            "purpose": "marketing"}, headers=h).json()
        assert check["requires_review"] is True   # marketing never implied

        # Admin/governance smoke (W1).
        assert client.get("/admin/me", headers=h).status_code == 200
        assert client.get("/governance/blocked",
                          headers=h).status_code == 200

        # Audit chain still verifies across all merged traffic.
        assert client.app.state.audit.verify_chain()

    def test_9_portal_page_serves_all_ui_sections(self, client):
        page = client.get("/portal").text
        for section in ('id="quotes-section"', 'id="sched-section"',
                        'id="evidence-section"', 'id="admin-section"',
                        'id="gov-section"'):
            assert section in page, section
        assert "No public raw download" in page

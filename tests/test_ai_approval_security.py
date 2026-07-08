"""CORE-A4.1 — Human Approval Gate RBAC and tenant isolation. An AI worker can
never create an approval request; approvals are strictly tenant-scoped; every
mutation is re-checked server-side regardless of UI."""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.auth import AuthService
from finalis.portal.seed import seed


@pytest.fixture()
def app():
    a = create_app(":memory:")
    seed(a.state.db)
    return a


def _auth(c, email):
    return {"Authorization": "Bearer " + c.post("/auth/login", json={
        "email": email, "password": "demo1234"}).json()["token"]}


def _make_run(c, h):
    cid = c.get("/cases", headers=h).json()[0]["id"]
    tk = c.post("/ai-tasks", json={
        "task_type": "customer_reply_draft", "task_title": "t",
        "task_description": "please do", "subject_type": "case",
        "subject_id": cid}, headers=h).json()
    return c.post("/ai-runs", json={"task_id": tk["task_id"]},
                  headers=h).json()["run_id"]


class TestRbac:
    def test_viewer_cannot_create(self, app):
        c = TestClient(app)
        ho = _auth(c, "owner@demo.finalis")
        rid = _make_run(c, ho)
        hv = _auth(c, "viewer@demo.finalis")
        r = c.post("/ai-approvals", json={"run_id": rid}, headers=hv)
        assert r.status_code == 403

    def test_viewer_can_read(self, app):
        c = TestClient(app)
        ho = _auth(c, "owner@demo.finalis")
        rid = _make_run(c, ho)
        c.post("/ai-approvals", json={"run_id": rid}, headers=ho)
        hv = _auth(c, "viewer@demo.finalis")
        assert c.get("/ai-approvals", headers=hv).status_code == 200

    def test_ai_worker_cannot_create(self, app):
        # ai_worker holds case.update, so the explicit human-oversight guard
        # (not RBAC alone) must block it.
        c = TestClient(app)
        ho = _auth(c, "owner@demo.finalis")
        rid = _make_run(c, ho)
        tid = app.state.db.one(
            "SELECT tenant_id FROM users WHERE email=?",
            "owner@demo.finalis")["tenant_id"]
        AuthService(app.state.db).create_user(
            tenant_id=tid, email="bot@demo.finalis", password="demo1234",
            role="ai_worker")
        hb = _auth(c, "bot@demo.finalis")
        r = c.post("/ai-approvals", json={"run_id": rid}, headers=hb)
        assert r.status_code == 403


class TestTenantIsolation:
    def test_cross_tenant_get_404(self, app):
        c = TestClient(app)
        ho = _auth(c, "owner@demo.finalis")
        rid = _make_run(c, ho)
        a = c.post("/ai-approvals", json={"run_id": rid}, headers=ho).json()
        hother = _auth(c, "owner@other.finalis")
        r = c.get(f"/ai-approvals/{a['approval_request_id']}", headers=hother)
        assert r.status_code == 404

    def test_cross_tenant_list_excludes(self, app):
        c = TestClient(app)
        ho = _auth(c, "owner@demo.finalis")
        rid = _make_run(c, ho)
        a = c.post("/ai-approvals", json={"run_id": rid}, headers=ho).json()
        hother = _auth(c, "owner@other.finalis")
        lst = c.get("/ai-approvals", headers=hother).json()
        assert all(x["approval_request_id"] != a["approval_request_id"]
                   for x in lst)

    def test_cross_tenant_verify_404(self, app):
        c = TestClient(app)
        ho = _auth(c, "owner@demo.finalis")
        rid = _make_run(c, ho)
        a = c.post("/ai-approvals", json={"run_id": rid}, headers=ho).json()
        hother = _auth(c, "owner@other.finalis")
        r = c.post(f"/ai-approvals/{a['approval_request_id']}/verify",
                   headers=hother)
        assert r.status_code == 404


class TestHonestyLabels:
    def test_no_overclaim_of_execution_or_approval(self, app):
        c = TestClient(app)
        ho = _auth(c, "owner@demo.finalis")
        rid = _make_run(c, ho)
        a = c.post("/ai-approvals", json={"run_id": rid}, headers=ho).json()
        labels = " ".join(a["honesty_labels"]).lower()
        assert "does not approve or execute" in labels
        assert "does not override consent" in labels
        assert "core-a4.2" in labels

    def test_labels_present_on_every_request(self, app):
        c = TestClient(app)
        ho = _auth(c, "owner@demo.finalis")
        rid = _make_run(c, ho)
        a = c.post("/ai-approvals", json={"run_id": rid}, headers=ho).json()
        assert len(a["honesty_labels"]) >= 8

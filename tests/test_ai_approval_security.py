"""CORE-A4.1 — Human Approval Gate RBAC and tenant isolation. An AI worker can
never create an approval request; approvals are strictly tenant-scoped; every
mutation is re-checked server-side regardless of UI. Extended in CORE-A4.2 with
decision/grant/consume-check RBAC and tenant isolation."""
import json

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


# --- CORE-A4.2: decision / grant / consume-check RBAC + tenant isolation ----
from conftest import OWNER, OWNER2, MANAGER, VIEWER, OTHER_OWNER  # noqa: E402


class TestDecisionRbac:
    def test_viewer_cannot_approve(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        aid = ap["approval_request_id"]
        r = gate.c.post(f"/ai-approvals/{aid}/approve",
                        json={"viewed_package_hash": ap["approval_package_hash"],
                              "acknowledgements": {}, "challenge_passed": False},
                        headers=gate.h(VIEWER))
        assert r.status_code == 403

    def test_ai_worker_cannot_approve(self, gate):
        gate.add_user("bot@demo.finalis", "ai_worker")
        ap, _ = gate.make_request("customer_reply_draft")
        aid = ap["approval_request_id"]
        r = gate.c.post(f"/ai-approvals/{aid}/approve",
                        json={"viewed_package_hash": ap["approval_package_hash"],
                              "acknowledgements": {}, "challenge_passed": False},
                        headers=gate.h("bot@demo.finalis"))
        assert r.status_code == 403

    def test_manager_cannot_approve_high_risk(self, gate):
        # HIGH requires owner; a manager approver is rejected on ROLE. The
        # requester is an owner (not the manager) so the self-approval guard
        # cannot fire — only the insufficient-role guard can produce the 403.
        ap, _ = gate.make_request("merge_proposal", requester=OWNER)
        r = gate.approve(ap, approver=MANAGER, challenge=True)
        assert r.status_code == 403

    def test_requester_cannot_self_approve_high_risk(self, gate):
        # owner creates and is the only owner-of-record; self-approval blocked.
        ap, _ = gate.make_request("merge_proposal", requester=OWNER)
        r = gate.approve(ap, approver=OWNER, challenge=True)
        assert r.status_code == 403

    def test_requester_cannot_self_approve_medium_risk(self, gate):
        # Separation of duties is enforced for ALL tiers, not just HIGH: the
        # manager who requested cannot approve their own MEDIUM request.
        ap, _ = gate.make_request("customer_reply_draft", requester=MANAGER)
        r = gate.approve(ap, approver=MANAGER, challenge=False)
        assert r.status_code == 403

    def test_second_owner_can_approve_high_risk(self, gate):
        ap, _ = gate.make_request("merge_proposal", requester=MANAGER)
        r = gate.approve(ap, approver=OWNER2, challenge=True)
        assert r.status_code == 200


class TestDualControl:
    """A count>=2 request needs two DISTINCT human approvers; one user cannot
    fill both slots and no grant is issued until quorum is met."""

    def _high_dual(self, gate):
        ap, _ = gate.make_request("merge_proposal", requester=MANAGER)
        aid = ap["approval_request_id"]
        gate.set_request_field(aid, required_approver_count=2)
        return ap, aid

    def test_first_approval_awaits_quorum_no_grant(self, gate):
        ap, aid = self._high_dual(gate)
        r = gate.raw_approve(aid, ap, OWNER2).json()
        assert r["approval_status"] == "APPROVED_PENDING_QUORUM"
        assert r["approval_grant"] is None
        assert r["approvals_recorded"] == 1 and r["approvals_required"] == 2
        assert gate.c.get(f"/ai-approvals/{aid}/grant",
                          headers=gate.h(OWNER2)).status_code == 404

    def test_same_user_cannot_count_twice(self, gate):
        ap, aid = self._high_dual(gate)
        gate.raw_approve(aid, ap, OWNER2)
        again = gate.raw_approve(aid, ap, OWNER2)
        assert again.status_code == 409

    def test_second_distinct_approver_completes_quorum(self, gate):
        gate.add_user("owner3@demo.finalis", "owner")
        ap, aid = self._high_dual(gate)
        gate.raw_approve(aid, ap, OWNER2)
        r = gate.raw_approve(aid, ap, "owner3@demo.finalis").json()
        assert r["approval_status"] == "APPROVED_CONSUME_READY"
        assert r["approval_grant"]["grant_status"] == "VALID"

    def test_quorum_fields_present_when_declared(self, gate):
        # Quorum-ready fields are honest even though full multi-approver
        # workflow (per-slot roles, quorum groups) is MISSING/NEXT.
        ap, _ = gate.make_request("merge_proposal", requester=MANAGER)
        assert "required_approver_count" in ap
        assert "dual_control_required" in ap


class TestDecisionTenantIsolation:
    def test_cross_tenant_approve_denied(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        aid = ap["approval_request_id"]
        r = gate.c.post(f"/ai-approvals/{aid}/approve",
                        json={"viewed_package_hash": ap["approval_package_hash"],
                              "acknowledgements": {}, "challenge_passed": False},
                        headers=gate.h(OTHER_OWNER))
        assert r.status_code == 404

    def test_cross_tenant_grant_read_denied(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        gate.approve(ap, challenge=False)
        aid = ap["approval_request_id"]
        r = gate.c.get(f"/ai-approvals/{aid}/grant",
                       headers=gate.h(OTHER_OWNER))
        assert r.status_code == 404

    def test_cross_tenant_consume_check_denied(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        gate.approve(ap, challenge=False)
        aid = ap["approval_request_id"]
        r = gate.c.post(f"/ai-approvals/{aid}/consume-check",
                        headers=gate.h(OTHER_OWNER))
        assert r.status_code == 404

    def test_unknown_approval_safe_not_found(self, gate):
        assert gate.c.post("/ai-approvals/nope/approve", json={},
                           headers=gate.h(OWNER2)).status_code == 404
        assert gate.c.post("/ai-approvals/nope/consume-check",
                           headers=gate.h(OWNER2)).status_code == 404
        assert gate.c.get("/ai-approvals/nope/grant",
                          headers=gate.h(OWNER2)).status_code == 404


class TestExtendedVerify:
    def test_verify_covers_decision_and_grant(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        gate.approve(ap, challenge=False)
        aid = ap["approval_request_id"]
        v = gate.c.post(f"/ai-approvals/{aid}/verify",
                        headers=gate.h(OWNER2)).json()
        assert v["verification_status"] == "MATCHED"
        assert v["approval_decision_hash_status"] == "MATCHED"
        assert v["approval_grant_hash_status"] == "MATCHED"

    def test_verify_detects_grant_tamper(self, gate):
        ap, _ = gate.make_request("customer_reply_draft")
        gate.approve(ap, challenge=False)
        aid = ap["approval_request_id"]
        g = gate.grant(aid)
        gp = json.loads(gate.db.one(
            "SELECT payload_json FROM ai_approval_grants WHERE id=?",
            g["approval_grant_id"])["payload_json"])
        gp["approval_action_type"] = "execute_payment"
        gate.db.conn.execute(
            "UPDATE ai_approval_grants SET payload_json=? WHERE id=?",
            (json.dumps(gp), g["approval_grant_id"]))
        gate.db.conn.commit()
        v = gate.c.post(f"/ai-approvals/{aid}/verify",
                        headers=gate.h(OWNER2)).json()
        assert v["approval_grant_hash_status"] == "MISMATCHED"
        assert v["verification_status"] == "MISMATCHED"

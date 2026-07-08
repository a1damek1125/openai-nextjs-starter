"""Shared fixtures for the Human Approval Gate PART 2 (CORE-A4.2) tests.

The `gate` fixture builds a seeded app with a SECOND owner in the demo tenant
so separation-of-duties can be exercised: a request created by the manager is
decided by an owner who is not the requester.
"""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.auth import AuthService
from finalis.portal.seed import seed

OWNER = "owner@demo.finalis"
OWNER2 = "owner2@demo.finalis"
MANAGER = "manager@demo.finalis"
VIEWER = "viewer@demo.finalis"
OTHER_OWNER = "owner@other.finalis"


class Gate:
    def __init__(self):
        self.app = create_app(":memory:")
        seed(self.app.state.db)
        self.c = TestClient(self.app)
        self.tid = self.db.one("SELECT tenant_id FROM users WHERE email=?",
                               OWNER)["tenant_id"]
        AuthService(self.db).create_user(
            tenant_id=self.tid, email=OWNER2, password="demo1234", role="owner")

    @property
    def db(self):
        return self.app.state.db

    def add_user(self, email, role):
        AuthService(self.db).create_user(
            tenant_id=self.tid, email=email, password="demo1234", role=role)

    def h(self, email=OWNER):
        tok = self.c.post("/auth/login", json={
            "email": email, "password": "demo1234"}).json()["token"]
        return {"Authorization": "Bearer " + tok}

    def case_id(self, hdr=None):
        return self.c.get("/cases", headers=hdr or self.h()).json()[0]["id"]

    def make_request(self, task_type="customer_reply_draft",
                     requester=MANAGER):
        hdr = self.h(requester)
        cid = self.case_id(hdr)
        tk = self.c.post("/ai-tasks", json={
            "task_type": task_type, "task_title": "t",
            "task_description": "please do the thing", "subject_type": "case",
            "subject_id": cid}, headers=hdr).json()
        run = self.c.post("/ai-runs", json={"task_id": tk["task_id"]},
                          headers=hdr).json()
        ap = self.c.post("/ai-approvals", json={"run_id": run["run_id"]},
                         headers=hdr).json()
        return ap, run["run_id"]

    def approve(self, ap, approver=OWNER2, challenge=True, acks=None,
                viewed=None, reason="ok"):
        aid = ap["approval_request_id"]
        required = ap["policy_decision_capsule"]["required_acknowledgements"]
        if acks is None:
            acks = {a: True for a in required}
        body = {"viewed_package_hash": (viewed if viewed is not None
                                        else ap["approval_package_hash"]),
                "acknowledgements": acks, "challenge_passed": challenge,
                "decision_reason": reason}
        return self.c.post(f"/ai-approvals/{aid}/approve", json=body,
                           headers=self.h(approver))

    def set_request_field(self, aid, **fields):
        """White-box helper: patch stored request payload fields (e.g. force a
        dual-control quorum) to exercise a code path directly."""
        import json
        row = self.db.one(
            "SELECT payload_json FROM ai_approval_requests WHERE id=?", aid)
        p = json.loads(row["payload_json"])
        p.update(fields)
        self.db.conn.execute(
            "UPDATE ai_approval_requests SET payload_json=? WHERE id=?",
            (json.dumps(p), aid))
        self.db.conn.commit()

    def raw_approve(self, aid, ap, approver, challenge=True):
        acks = {a: True for a in ap["policy_decision_capsule"][
            "required_acknowledgements"]}
        return self.c.post(f"/ai-approvals/{aid}/approve", json={
            "viewed_package_hash": ap["approval_package_hash"],
            "acknowledgements": acks, "challenge_passed": challenge},
            headers=self.h(approver))

    def grant(self, aid, approver=OWNER2):
        return self.c.get(f"/ai-approvals/{aid}/grant", headers=self.h(
            approver)).json()

    def consume_check(self, aid, approver=OWNER2):
        return self.c.post(f"/ai-approvals/{aid}/consume-check",
                           headers=self.h(approver)).json()


@pytest.fixture()
def gate():
    return Gate()

"""CORE-A4.1 — Human Approval Gate API (PART 1): create/list/get/safe/package/
challenge/verify. Creating an approval request approves and executes nothing;
it produces a scoped, hash-bound, policy-derived request only."""
import json

import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.seed import seed


@pytest.fixture()
def app():
    a = create_app(":memory:")
    seed(a.state.db)
    return a


def _auth(c, email="owner@demo.finalis"):
    return {"Authorization": "Bearer " + c.post("/auth/login", json={
        "email": email, "password": "demo1234"}).json()["token"]}


def _make_run(c, h, task_type="customer_reply_draft"):
    cid = c.get("/cases", headers=h).json()[0]["id"]
    tk = c.post("/ai-tasks", json={
        "task_type": task_type, "task_title": "t",
        "task_description": "please do the thing", "subject_type": "case",
        "subject_id": cid}, headers=h).json()
    run = c.post("/ai-runs", json={"task_id": tk["task_id"]},
                 headers=h).json()
    return run["run_id"]


class TestCreate:
    def test_medium_risk_pending_manager(self, app):
        c = TestClient(app); h = _auth(c)
        rid = _make_run(c, h, "customer_reply_draft")
        r = c.post("/ai-approvals", json={"run_id": rid}, headers=h).json()
        assert r["approval_status"] == "PENDING"
        assert r["approval_risk_level"] == "MEDIUM"
        assert r["required_approver_role"] == "manager"
        assert r["approval_challenge_required"] is False

    def test_high_risk_challenge_required_owner(self, app):
        c = TestClient(app); h = _auth(c)
        rid = _make_run(c, h, "merge_proposal")
        r = c.post("/ai-approvals", json={"run_id": rid}, headers=h).json()
        assert r["approval_status"] == "CHALLENGE_REQUIRED"
        assert r["required_approver_role"] == "owner"
        assert r["approval_challenge_required"] is True
        assert r["approval_challenge"]["challenge_status"] == "REQUIRED"

    def test_create_does_not_approve_or_execute(self, app):
        c = TestClient(app); h = _auth(c)
        rid = _make_run(c, h)
        r = c.post("/ai-approvals", json={"run_id": rid}, headers=h).json()
        assert r["approval_status"] in ("PENDING", "CHALLENGE_REQUIRED")
        assert "APPROVED" not in r["approval_status"]
        assert r["self_approval_forbidden"] is True
        assert r["ai_approval_forbidden"] is True

    def test_challenge_bound_to_package(self, app):
        c = TestClient(app); h = _auth(c)
        rid = _make_run(c, h, "merge_proposal")
        r = c.post("/ai-approvals", json={"run_id": rid}, headers=h).json()
        pkg = r["approval_package"]
        base = {**pkg, "approval_challenge": None}
        from finalis.ai_employee import approvals as A
        assert r["approval_challenge"]["viewed_package_hash"] \
            == A.package_hash(base)

    def test_missing_run_404(self, app):
        c = TestClient(app); h = _auth(c)
        r = c.post("/ai-approvals", json={"run_id": "nope"}, headers=h)
        assert r.status_code == 404

    def test_forbidden_unlocks_recorded_on_package(self, app):
        c = TestClient(app); h = _auth(c)
        rid = _make_run(c, h)
        r = c.post("/ai-approvals", json={"run_id": rid}, headers=h).json()
        assert "override_consent" in r["approval_package"]["forbidden_unlocks"]

    def test_blocked_when_authority_hard_fail(self, app):
        # Force a hard-fail authority on the stored run and confirm approval
        # is BLOCKED: an approval cannot convert a forbidden action to allowed.
        c = TestClient(app); h = _auth(c)
        rid = _make_run(c, h)
        row = app.state.db.one("SELECT payload_json FROM ai_runs WHERE id=?",
                               rid)
        p = json.loads(row["payload_json"])
        p["authority_hard_fail"] = True
        app.state.db.conn.execute(
            "UPDATE ai_runs SET payload_json=? WHERE id=?",
            (json.dumps(p), rid))
        app.state.db.conn.commit()
        r = c.post("/ai-approvals", json={"run_id": rid}, headers=h).json()
        assert r["approval_status"] == "BLOCKED"
        assert r["blocked_reason"]


class TestReadEndpoints:
    def _create(self, c, h):
        rid = _make_run(c, h, "merge_proposal")
        return c.post("/ai-approvals", json={"run_id": rid},
                      headers=h).json()

    def test_list_and_get(self, app):
        c = TestClient(app); h = _auth(c)
        a = self._create(c, h)
        lst = c.get("/ai-approvals", headers=h).json()
        assert any(x["approval_request_id"] == a["approval_request_id"]
                   for x in lst)
        got = c.get(f"/ai-approvals/{a['approval_request_id']}",
                    headers=h).json()
        assert got["approval_request_hash"] == a["approval_request_hash"]

    def test_safe_view_omits_sensitive_fields(self, app):
        c = TestClient(app); h = _auth(c)
        a = self._create(c, h)
        sv = c.get(f"/ai-approvals/{a['approval_request_id']}/safe",
                   headers=h).json()
        assert sv["redaction_profile"] == "SAFE_APPROVAL_VIEW"
        # policy_input is a sensitive field carried inside the capsule; the
        # recursive safe view must redact it wherever it appears.
        assert sv["policy_decision_capsule"]["policy_input"] \
            == "<omitted in safe view>"
        assert "policy_input" in sv["redaction_manifest"]["omitted_fields"]

    def test_package_endpoint(self, app):
        c = TestClient(app); h = _auth(c)
        a = self._create(c, h)
        pk = c.get(f"/ai-approvals/{a['approval_request_id']}/package",
                   headers=h).json()
        assert pk["approval_package_hash"] == a["approval_package_hash"]

    def test_challenge_endpoint(self, app):
        c = TestClient(app); h = _auth(c)
        a = self._create(c, h)
        ch = c.get(f"/ai-approvals/{a['approval_request_id']}/challenge",
                   headers=h).json()
        assert ch["approval_challenge_required"] is True
        assert ch["approval_challenge_hash"] == a["approval_challenge_hash"]

    def test_get_missing_404(self, app):
        c = TestClient(app); h = _auth(c)
        assert c.get("/ai-approvals/nope", headers=h).status_code == 404


class TestVerify:
    def test_verify_matched_untampered(self, app):
        c = TestClient(app); h = _auth(c)
        rid = _make_run(c, h, "merge_proposal")
        a = c.post("/ai-approvals", json={"run_id": rid}, headers=h).json()
        v = c.post(f"/ai-approvals/{a['approval_request_id']}/verify",
                   headers=h).json()
        assert v["verification_status"] == "MATCHED"
        assert v["challenge_bound_to_package"] == "VALID"
        assert v["approval_package_hash_status"] == "MATCHED"
        assert v["policy_decision_hash_status"] == "MATCHED"

    def test_verify_mismatch_on_package_tamper(self, app):
        c = TestClient(app); h = _auth(c)
        rid = _make_run(c, h)
        a = c.post("/ai-approvals", json={"run_id": rid}, headers=h).json()
        aid = a["approval_request_id"]
        row = app.state.db.one(
            "SELECT payload_json FROM ai_approval_requests WHERE id=?", aid)
        p = json.loads(row["payload_json"])
        p["approval_package"]["approval_action_type"] = "execute_payment"
        app.state.db.conn.execute(
            "UPDATE ai_approval_requests SET payload_json=? WHERE id=?",
            (json.dumps(p), aid))
        app.state.db.conn.commit()
        v = c.post(f"/ai-approvals/{aid}/verify", headers=h).json()
        assert v["verification_status"] == "MISMATCHED"
        assert v["approval_package_hash_status"] == "MISMATCHED"

    def test_verify_detects_challenge_reuse(self, app):
        # Re-point the challenge's viewed_package_hash: binding must break.
        c = TestClient(app); h = _auth(c)
        rid = _make_run(c, h, "merge_proposal")
        a = c.post("/ai-approvals", json={"run_id": rid}, headers=h).json()
        aid = a["approval_request_id"]
        row = app.state.db.one(
            "SELECT payload_json FROM ai_approval_requests WHERE id=?", aid)
        p = json.loads(row["payload_json"])
        p["approval_challenge"]["viewed_package_hash"] = "deadbeef" * 8
        # keep the challenge_hash consistent so only the binding check fails
        from finalis.ai_employee import approvals as A
        p["approval_challenge"]["challenge_hash"] = A.challenge_hash(
            p["approval_challenge"])
        app.state.db.conn.execute(
            "UPDATE ai_approval_requests SET payload_json=? WHERE id=?",
            (json.dumps(p), aid))
        app.state.db.conn.commit()
        v = c.post(f"/ai-approvals/{aid}/verify", headers=h).json()
        assert v["challenge_bound_to_package"] == "REUSE_DETECTED"
        assert v["verification_status"] == "MISMATCHED"


class TestPolicyEndpoint:
    def test_policy_matrix_exposed(self, app):
        c = TestClient(app); h = _auth(c)
        p = c.get("/ai-approvals/policy", headers=h).json()
        assert set(p["approval_policy_matrix"]) == {
            "LOW", "MEDIUM", "HIGH", "CRITICAL"}
        assert "override_consent" in p["forbidden_unlocks"]
        assert "execute_payment" in p["always_blocked_actions"]

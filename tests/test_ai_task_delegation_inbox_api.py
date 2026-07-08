"""CORE-A2 — Secure Work Intake Registry API. Endpoints, response shape,
authority-decision mapping, RBAC/tenant isolation, idempotency, source
channels, intake events. Task intake is NOT execution."""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.seed import seed


@pytest.fixture()
def client():
    app = create_app(":memory:")
    seed(app.state.db)
    return TestClient(app)


def _login(client, email="owner@demo.finalis"):
    t = client.post("/auth/login", json={"email": email,
                                         "password": "demo1234"}).json()
    return {"Authorization": f"Bearer {t['token']}"}


def _case(client, h):
    return client.get("/cases", headers=h).json()[0]["id"]


def _mk(client, h, **body):
    return client.post("/ai-tasks", json=body, headers=h)


def _summary_task(client, h):
    return _mk(client, h, task_type="case_summary", task_title="Summarize",
               task_description="please summarize", subject_type="case",
               subject_id=_case(client, h)).json()


class TestEndpointsAndShape:
    def test_1_to_8_endpoints_exist(self, client):
        h = _login(client)
        t = _summary_task(client, h)
        tid = t["task_id"]
        assert client.get("/ai-tasks", headers=h).status_code == 200
        assert client.get(f"/ai-tasks/{tid}", headers=h).status_code == 200
        assert client.get("/ai-tasks/types", headers=h).status_code == 200
        assert client.get(f"/ai-tasks/{tid}/envelope",
                          headers=h).status_code == 200
        assert client.get(f"/ai-tasks/{tid}/contract",
                          headers=h).status_code == 200
        assert client.get(f"/ai-tasks/{tid}/intake-events",
                          headers=h).status_code == 200
        assert client.post(f"/ai-tasks/{tid}/cancel",
                           headers=h).status_code == 200

    def test_16_to_53_task_fields_present(self, client):
        h = _login(client)
        t = _summary_task(client, h)
        for f in ("tenant_id", "requester_user_id", "assigned_ai_employee_id",
                  "assigned_ai_employee_capability_snapshot_hash",
                  "source_channel", "canonical_task_envelope_hash",
                  "canonical_task_envelope_version",
                  "canonical_task_contract_hash",
                  "canonical_task_contract_version", "task_type", "segment",
                  "segment_confidence", "task_status", "task_version",
                  "priority", "subject_type", "subject_id", "task_purpose",
                  "purpose_category", "allowed_data_scopes",
                  "forbidden_data_scopes", "sensitive_data_flags",
                  "authority_decision", "authority_reason",
                  "authority_hard_fail", "risk_level", "risk_reason",
                  "requires_human_approval", "requires_consent_check",
                  "requires_evidence_check", "requires_tool_broker",
                  "requires_run_ledger", "forbidden_side_effects",
                  "input_security_flags", "unsafe_requested_actions",
                  "honesty_labels"):
            assert f in t, f
        assert t["task_description_trust"] == "UNTRUSTED_USER_INPUT"
        assert t["canonical_task_envelope_version"] == "finalis-task-envelope-v1"
        assert t["canonical_task_contract_version"] == "finalis-task-contract-v1"


class TestAuthorityMapping:
    def test_54_blocked_not_accepted(self, client):
        # A task type that maps to a forbidden action can never be ACCEPTED.
        h = _login(client)
        # override is not a task_type; emulate via merge execution mapping:
        # merge_proposal is APPROVAL (safe). Use sop_change -> NOT_IMPLEMENTED
        # and construct a blocked path via cross-tenant subject.
        t = _mk(client, h, task_type="case_summary", task_title="x",
                subject_type="case", subject_id="c1",
                subject_tenant_id="other-tenant").json()
        assert t["task_status"] == "BLOCKED"
        assert t["authority_hard_fail"] is True

    def test_55_approval_required_no_execution(self, client):
        h = _login(client)
        t = _mk(client, h, task_type="merge_proposal", task_title="merge",
                subject_type="customer", subject_id="cu1").json()
        assert t["task_status"] == "ACCEPTED"
        assert t["requires_human_approval"] is True
        assert t["latest_result_summary"] is None    # nothing executed

    def test_56_draft_only_no_execution(self, client):
        h = _login(client)
        t = _summary_task(client, h)
        assert t["task_status"] == "ACCEPTED"
        assert t["authority_decision"] == "ALLOWED_DRAFT_ONLY"
        assert t["draft_artifact_placeholder"] is None

    def test_57_not_implemented_labeled(self, client):
        h = _login(client)
        t = _mk(client, h, task_type="sop_change_proposal", task_title="x",
                subject_type="op", subject_id="o1").json()
        assert t["task_status"] == "NOT_IMPLEMENTED"

    def test_58_unknown_task_type_safe_error(self, client):
        h = _login(client)
        assert _mk(client, h, task_type="does_not_exist",
                   task_title="x").status_code == 400

    def test_59_ambiguous_subject_needs_clarification(self, client):
        h = _login(client)
        t = _mk(client, h, task_type="case_summary",
                task_title="no subject").json()
        assert t["task_status"] == "NEEDS_CLARIFICATION"
        assert t["clarification_questions"]

    def test_60_expired_task_not_accepted(self, client):
        h = _login(client)
        t = _mk(client, h, task_type="case_summary", task_title="x",
                subject_type="case", subject_id=_case(client, h),
                expires_at="2000-01-01T00:00:00").json()
        assert t["task_status"] == "EXPIRED"


class TestRbacAndTenant:
    def test_10_viewer_cannot_create(self, client):
        vh = _login(client, "viewer@demo.finalis")
        assert _mk(client, vh, task_type="case_summary",
                   task_title="x").status_code == 403

    def test_viewer_can_list(self, client):
        vh = _login(client, "viewer@demo.finalis")
        assert client.get("/ai-tasks", headers=vh).status_code == 200

    def test_11_12_13_cross_tenant_isolation(self, client):
        h = _login(client)
        t = _summary_task(client, h)
        oh = _login(client, "owner@other.finalis")
        assert client.get(f"/ai-tasks/{t['task_id']}",
                          headers=oh).status_code == 404
        # other tenant sees none of demo's tasks
        assert client.get("/ai-tasks", headers=oh).json() == []


class TestIdempotency:
    def test_71_same_key_same_envelope_replays(self, client):
        h = _login(client)
        cid = _case(client, h)
        a = _mk(client, h, task_type="case_summary", task_title="Idem",
                subject_type="case", subject_id=cid,
                idempotency_key="K1").json()
        b = _mk(client, h, task_type="case_summary", task_title="Idem",
                subject_type="case", subject_id=cid, idempotency_key="K1")
        assert b.status_code == 200
        assert b.json().get("idempotent_replay") is True
        assert b.json()["task_id"] == a["task_id"]

    def test_72_same_key_diff_envelope_conflict(self, client):
        h = _login(client)
        cid = _case(client, h)
        _mk(client, h, task_type="case_summary", task_title="Idem2",
            subject_type="case", subject_id=cid, idempotency_key="K2")
        r = _mk(client, h, task_type="case_summary", task_title="DIFFERENT",
                subject_type="case", subject_id=cid, idempotency_key="K2")
        assert r.status_code == 409

    def test_73_different_key_new_task(self, client):
        h = _login(client)
        cid = _case(client, h)
        a = _mk(client, h, task_type="case_summary", task_title="A",
                subject_type="case", subject_id=cid, idempotency_key="KA")
        b = _mk(client, h, task_type="case_summary", task_title="A",
                subject_type="case", subject_id=cid, idempotency_key="KB")
        assert a.json()["task_id"] != b.json()["task_id"]

    def test_74_cross_tenant_keys_do_not_collide(self, client):
        h = _login(client)
        _mk(client, h, task_type="case_summary", task_title="X",
            subject_type="case", subject_id=_case(client, h),
            idempotency_key="SHARED")
        oh = _login(client, "owner@other.finalis")
        # other tenant reuses the same key — must NOT replay demo's task.
        r = client.post("/ai-tasks", json={
            "task_type": "case_summary", "task_title": "X",
            "idempotency_key": "SHARED"}, headers=oh)
        # other-tenant owner has case.update; no demo task is returned.
        assert r.status_code in (200, 400)
        if r.status_code == 200:
            assert r.json().get("idempotent_replay") is not True

    def test_75_channel_retry_no_duplicate(self, client):
        h = _login(client)
        cid = _case(client, h)
        body = dict(task_type="case_summary", task_title="Retry",
                    subject_type="case", subject_id=cid,
                    source_channel="API", idempotency_key="RETRY1")
        a = _mk(client, h, **body).json()
        b = _mk(client, h, **body).json()
        assert a["task_id"] == b["task_id"]      # retry is idempotent


class TestSourceChannelsAndEvents:
    def test_source_channel_status(self, client):
        h = _login(client)
        t = _mk(client, h, task_type="case_summary", task_title="x",
                subject_type="case", subject_id=_case(client, h),
                source_channel="SLACK_NOT_IMPLEMENTED").json()
        assert t["source_channel"] == "SLACK_NOT_IMPLEMENTED"
        assert t["source_channel_status"] == "NOT_IMPLEMENTED"

    def test_117_intake_events_append_only(self, client):
        h = _login(client)
        t = _summary_task(client, h)
        evs = client.get(f"/ai-tasks/{t['task_id']}/intake-events",
                         headers=h).json()
        types = [e["event_type"] for e in evs]
        assert "TASK_CREATED" in types and "AUTHORITY_CHECKED" in types
        assert "TASK_CONTRACT_CREATED" in types
        # cancelling appends, never rewrites
        client.post(f"/ai-tasks/{t['task_id']}/cancel", headers=h)
        evs2 = client.get(f"/ai-tasks/{t['task_id']}/intake-events",
                          headers=h).json()
        assert len(evs2) > len(evs)
        assert evs2[:len(evs)] == evs            # earlier events unchanged


def vh_client(c):
    return c


def test_types_endpoint_lists_mappings(client):
    h = _login(client)
    d = client.get("/ai-tasks/types", headers=h).json()
    assert "case_summary" in d["task_types"]
    assert d["task_types"]["case_summary"]["segment"] == "casework"
    assert "SLACK_NOT_IMPLEMENTED" in d["source_channels"]

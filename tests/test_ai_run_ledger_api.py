"""CORE-A3 — Run Ledger API: endpoints, response shape, task integration,
lifecycle, RBAC/tenant isolation, event-types listing, trace, safe view."""
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


def _task(client, h, task_type="case_summary", **extra):
    body = {"task_type": task_type, "task_title": "t",
            "task_description": "please", "subject_type": "case",
            "subject_id": _case(client, h)}
    body.update(extra)
    return client.post("/ai-tasks", json=body, headers=h).json()


def _run(client, h, **extra):
    t = _task(client, h, **extra)
    return client.post("/ai-runs", json={"task_id": t["task_id"]},
                       headers=h).json()


class TestEndpointsAndShape:
    def test_1_to_9_endpoints_exist(self, client):
        h = _login(client)
        run = _run(client, h)
        rid = run["run_id"]
        assert client.get("/ai-runs", headers=h).status_code == 200
        assert client.get(f"/ai-runs/{rid}", headers=h).status_code == 200
        assert client.get(f"/ai-runs/{rid}/events",
                          headers=h).status_code == 200
        assert client.get("/ai-runs/event-types",
                          headers=h).status_code == 200
        assert client.get(f"/ai-runs/{rid}/trace",
                          headers=h).status_code == 200
        assert client.post(f"/ai-runs/{rid}/verify",
                           headers=h).status_code == 200
        assert client.post(f"/ai-runs/{rid}/replay",
                           headers=h).status_code == 200
        assert client.get(f"/ai-runs/{rid}/safe",
                          headers=h).status_code == 200
        assert client.post(f"/ai-runs/{rid}/cancel",
                           headers=h).status_code == 200

    def test_run_stores_all_snapshot_fields(self, client):
        h = _login(client)
        r = _run(client, h)
        for f in ("tenant_id", "task_id", "task_envelope_hash",
                  "task_contract_hash", "assigned_ai_employee_id",
                  "requester_user_id", "trace_id", "authority_decision",
                  "ai_employee_capability_snapshot_hash",
                  "allowed_data_scopes_snapshot", "risk_level", "event_count",
                  "run_state_hash", "run_chain_hash", "run_event_merkle_root",
                  "latest_event_hash", "honesty_labels"):
            assert f in r, f
        assert r["requires_run_ledger"] is True

    def test_run_creates_snapshot_event_sequence(self, client):
        h = _login(client)
        r = _run(client, h)
        types = [e["event_type"] for e in r["events"]]
        for required in ("RUN_CREATED", "TASK_CONTRACT_SNAPSHOT_RECORDED",
                         "TASK_ENVELOPE_SNAPSHOT_RECORDED",
                         "AUTHORITY_SNAPSHOT_RECORDED",
                         "CAPABILITY_SNAPSHOT_RECORDED",
                         "DATA_SCOPE_SNAPSHOT_RECORDED"):
            assert required in types, required
        # events are indexed, hashed, chained
        e0 = r["events"][0]
        assert e0["event_index"] == 1 and e0["event_hash"]
        assert e0["previous_event_hash"] == "GENESIS"
        assert e0["event_schema_version"] == "run-event-v1"
        assert e0["event_payload_hash"]

    def test_run_status_consistency_matched(self, client):
        h = _login(client)
        r = _run(client, h)
        assert r["run_status"] == r["replayed_run_status"]
        assert r["run_status_consistency"] == "MATCHED"


class TestTaskIntegration:
    def test_blocked_task_cannot_create_run(self, client):
        h = _login(client)
        blocked = _task(client, h, subject_tenant_id="other-tenant")
        assert blocked["task_status"] == "BLOCKED"
        assert client.post("/ai-runs", json={"task_id": blocked["task_id"]},
                           headers=h).status_code == 409

    def test_not_implemented_task_cannot_create_run(self, client):
        h = _login(client)
        t = _task(client, h, task_type="sop_change_proposal")
        assert t["task_status"] == "NOT_IMPLEMENTED"
        assert client.post("/ai-runs", json={"task_id": t["task_id"]},
                           headers=h).status_code == 409

    def test_approval_task_run_pauses(self, client):
        h = _login(client)
        r = _run(client, h, task_type="merge_proposal",
                 subject_type="customer", subject_id="cu1")
        assert r["run_status"] == "PAUSED"
        assert r["requires_human_approval"] is True

    def test_clarification_task_waits_for_context(self, client):
        h = _login(client)
        # a case_summary with no subject -> NEEDS_CLARIFICATION
        t = client.post("/ai-tasks", json={
            "task_type": "case_summary", "task_title": "x"},
            headers=h).json()
        assert t["task_status"] == "NEEDS_CLARIFICATION"
        r = client.post("/ai-runs", json={"task_id": t["task_id"]},
                        headers=h).json()
        assert r["run_status"] == "WAITING_FOR_CONTEXT"

    def test_unknown_task_404(self, client):
        h = _login(client)
        assert client.post("/ai-runs", json={"task_id": "nope"},
                           headers=h).status_code == 404


class TestRbacAndTenant:
    def test_viewer_can_list_not_create(self, client):
        vh = _login(client, "viewer@demo.finalis")
        assert client.get("/ai-runs", headers=vh).status_code == 200
        assert client.post("/ai-runs", json={"task_id": "x"},
                           headers=vh).status_code == 403

    def test_cross_tenant_denied(self, client):
        h = _login(client)
        rid = _run(client, h)["run_id"]
        oh = _login(client, "owner@other.finalis")
        assert client.get(f"/ai-runs/{rid}", headers=oh).status_code == 404
        assert client.get(f"/ai-runs/{rid}/events",
                          headers=oh).status_code == 404
        assert client.post(f"/ai-runs/{rid}/verify",
                           headers=oh).status_code == 404
        assert client.post(f"/ai-runs/{rid}/replay",
                           headers=oh).status_code == 404
        assert client.get("/ai-runs", headers=oh).json() == []

    def test_unknown_run_404(self, client):
        h = _login(client)
        assert client.get("/ai-runs/nope", headers=h).status_code == 404
        assert client.post("/ai-runs/nope/verify",
                           headers=h).status_code == 404


class TestLifecycle:
    def test_cancel_then_terminal(self, client):
        h = _login(client)
        rid = _run(client, h)["run_id"]
        assert client.post(f"/ai-runs/{rid}/cancel",
                           headers=h).json()["run_status"] == "CANCELLED"
        # cancelling a terminal run is refused
        assert client.post(f"/ai-runs/{rid}/cancel",
                           headers=h).status_code == 409
        # verify still MATCHED after the appended cancel event
        assert client.post(f"/ai-runs/{rid}/verify",
                           headers=h).json()["verification_status"] \
            == "MATCHED"

    def test_event_types_and_trace(self, client):
        h = _login(client)
        et = client.get("/ai-runs/event-types", headers=h).json()
        assert "RUN_CREATED" in et["event_types"]
        assert et["event_types"]["TOOL_CALL_PROPOSED"]["future_placeholder"]
        rid = _run(client, h)["run_id"]
        tr = client.get(f"/ai-runs/{rid}/trace", headers=h).json()
        assert tr["trace_id"] and len(tr["spans"]) >= 6


class TestSafeView:
    def test_safe_view_redacts_untrusted_payload(self, client):
        h = _login(client)
        rid = _run(client, h)["run_id"]
        sv = client.get(f"/ai-runs/{rid}/safe", headers=h).json()
        assert sv["redaction_profile"] == "SAFE_RUN_VIEW"
        # the envelope-snapshot event's payload (holding task_description) is
        # omitted in the safe view
        env_ev = next(e for e in sv["events"]
                      if e["event_type"] == "TASK_ENVELOPE_SNAPSHOT_RECORDED")
        assert env_ev["event_payload"] == "<omitted in safe view>"
        assert "Safe run view is not a separate ledger." in \
            sv["redaction_manifest"]["note"]

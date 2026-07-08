"""Portal API tests — auth, RBAC, tenant isolation, persistence, and the
full browser-equivalent E2E flow through real HTTP endpoints."""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.db import Database, DbAuditLog
from finalis.portal.seed import seed

SEGMENTS = [
    {"speaker": "SPEAKER_00", "text": "Hi, I'd like a quote for a heat "
     "pump installation.", "start_ms": 0, "end_ms": 3000,
     "asr_confidence": 0.95, "diar_confidence": 0.95, "language": "en"},
    {"speaker": "SPEAKER_00", "text": "I'll send you the photos tomorrow.",
     "start_ms": 3200, "end_ms": 5600,
     "asr_confidence": 0.93, "diar_confidence": 0.95, "language": "en"},
]


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


class TestAuth:
    def test_login_ok_and_me(self, client):
        h = login(client)
        me = client.get("/auth/me", headers=h).json()
        assert me["role"] == "owner" and me["tenant_id"] == "demo-hvac"

    def test_bad_password_rejected(self, client):
        r = client.post("/auth/login", json={"email": "owner@demo.finalis",
                                             "password": "wrong"})
        assert r.status_code == 401

    def test_unauthenticated_blocked(self, client):
        assert client.get("/cases").status_code == 401
        assert client.get("/dashboard/summary").status_code == 401

    def test_garbage_token_blocked(self, client):
        r = client.get("/cases", headers={"Authorization": "Bearer x.y"})
        assert r.status_code == 401


class TestTenantIsolation:
    def test_other_tenant_sees_no_demo_cases(self, client):
        h_other = login(client, "owner@other.finalis")
        assert client.get("/cases", headers=h_other).json() == []

    def test_cross_tenant_case_access_404(self, client):
        h = login(client)
        case_id = client.get("/cases", headers=h).json()[0]["id"]
        h_other = login(client, "owner@other.finalis")
        assert client.get(f"/cases/{case_id}",
                          headers=h_other).status_code == 404
        assert client.post(f"/cases/{case_id}/transition",
                           json={"to_state": "WON"},
                           headers=h_other).status_code == 404


class TestRBAC:
    def test_viewer_cannot_create_or_transition(self, client):
        h = login(client, "viewer@demo.finalis")
        assert client.post("/cases", json={"title": "x"},
                           headers=h).status_code == 403
        case_id = client.get("/cases", headers=h).json()[0]["id"]
        assert client.post(f"/cases/{case_id}/transition",
                           json={"to_state": "WON"},
                           headers=h).status_code == 403

    def test_operator_cannot_approve(self, client):
        h = login(client, "operator@demo.finalis")
        r = client.post("/actions/nonexistent/approve", json={}, headers=h)
        assert r.status_code == 403          # role gate before lookup


class TestDashboardApi:
    def test_summary_from_persisted_data(self, client):
        h = login(client)
        s = client.get("/dashboard/summary", headers=h).json()
        assert s["active_cases_count"] == 3   # seeded: offer/waiting/intake
        assert s["won_value_period"] == 9000
        assert s["stuck_cases_count"] >= 1
        assert s["overdue_promises_count"] >= 1

    def test_all_sections_respond(self, client):
        h = login(client)
        for section in ["action-queue", "approval-queue", "stuck-cases",
                        "missing-info", "promises", "offers-follow-up",
                        "pipeline", "risk-alerts", "activity"]:
            r = client.get(f"/dashboard/{section}", headers=h)
            assert r.status_code == 200, section


class TestPersistence:
    def test_case_survives_reload(self, tmp_path):
        db_file = str(tmp_path / "t.db")
        app1 = create_app(db_file)
        seed(app1.state.db)
        c1 = TestClient(app1)
        h = login(c1)
        case_id = c1.post("/cases", json={"title": "Persist me",
                                          "client_name": "K",
                                          "value_estimate": 500},
                          headers=h).json()["case_id"]
        # New process (new app instance over the same file).
        app2 = create_app(db_file)
        c2 = TestClient(app2)
        h2 = login(c2)
        titles = [c["title"] for c in c2.get("/cases", headers=h2).json()]
        assert "Persist me" in titles
        # Audit chain reloads from SQL and still verifies.
        assert DbAuditLog(app2.state.db).verify_chain()
        assert c2.get(f"/audit/verify/{case_id}",
                      headers=h2).json()["chain_valid"] is True

    def test_migration_idempotent(self, tmp_path):
        db = Database(str(tmp_path / "m.db"))
        assert db.migrate() == 12              # re-running is a no-op
        assert db.one("SELECT MAX(version) v FROM schema_version")["v"] == 12


class TestFullPortalFlowE2E:
    """The browser-equivalent flow through real HTTP + persistence."""

    def test_hvac_flow_end_to_end(self, client):
        h = login(client)
        # 1. Create case.
        case_id = client.post("/cases", json={
            "title": "New heat pump quote", "client_name": "E2E Client",
            "phone": "+48600999888", "value_estimate": 11000,
            "lead_score": 75}, headers=h).json()["case_id"]
        # 2. Transition into intake + submit transcript.
        assert client.post(f"/cases/{case_id}/transition",
                           json={"to_state": "INTAKE_IN_PROGRESS"},
                           headers=h).status_code == 200
        client.post(f"/cases/{case_id}/transcripts",
                    json={"segments": SEGMENTS}, headers=h)
        # 3. Analyze conversation → intent + missing items + promise.
        analysis = client.post(f"/cases/{case_id}/analyze-conversation",
                               headers=h).json()
        assert analysis["intent"] == "request_quote"
        assert any(m["type"] == "installation_photo"
                   for m in analysis["missing_items"])
        assert analysis["promises"][0]["what"] == "send photos"
        # 4. Move to WAITING_FOR_DOCUMENTS; run the loop.
        client.post(f"/cases/{case_id}/transition",
                    json={"to_state": "WAITING_FOR_DOCUMENTS"}, headers=h)
        tick = client.post(f"/completion-loop/run-case/{case_id}",
                           headers=h).json()
        assert tick["selected_action"] == "send_photo_request"
        # 5. Request photos → upload link + mock WhatsApp send.
        # (urgent=True keeps the test deterministic across business hours —
        # the non-urgent path defers via the consent gate, which is itself
        # tested in the ACE suite.)
        action = client.post("/actions/request", json={
            "case_id": case_id, "action_type": "send_photo_request",
            "reason": "photos missing", "payload": {"urgent": True}},
            headers=h).json()
        assert action["status"] == "executed"
        assert action["upload_url"]
        token = action["upload_url"].rsplit("/", 1)[1]
        # 6. Client opens + uploads via the public link (no auth).
        assert client.get(f"/upload-links/{token}").status_code == 200
        up = client.post(f"/upload-links/{token}/upload",
                         json={"filename": "nameplate.jpg",
                               "mime": "image/jpeg", "size_mb": 2.0})
        assert up.status_code == 200
        # 7. Missing photo resolved; document attached.
        detail = client.get(f"/cases/{case_id}", headers=h).json()
        photo_items = [m for m in detail["missing_items"]
                       if m["field_key"] == "installation_photo"]
        assert photo_items[0]["status"] == "received"
        assert detail["documents"][0]["filename"] == "nameplate.jpg"
        # 8. Resolve remaining blockers → quote → offer.
        client.post(f"/cases/{case_id}/transition",
                    json={"to_state": "DOCUMENT_ANALYSIS"}, headers=h)
        client.post(f"/cases/{case_id}/transition",
                    json={"to_state": "QUOTE_PREPARATION"}, headers=h)
        offer_id = client.post(f"/cases/{case_id}/offers",
                               json={"price": 10800, "scope": "12kW pump"},
                               headers=h).json()["offer_id"]
        assert client.post(f"/offers/{offer_id}/send",
                           headers=h).json()["status"] == "sent"
        client.post(f"/cases/{case_id}/transition",
                    json={"to_state": "OFFER_SENT", "offer_sent": True},
                    headers=h)
        # 9. Client accepts → WON.
        resp = client.post(f"/offers/{offer_id}/simulate-client-response",
                           json={"response": "accepted"}, headers=h).json()
        assert resp["client_response"] == "accepted"
        won = client.post(f"/cases/{case_id}/transition",
                          json={"to_state": "WON",
                                "reason": "client accepted"},
                          headers=h).json()
        assert won["state"] == "WON"
        # 10. Illegal transition still blocked at the API.
        bad = client.post(f"/cases/{case_id}/transition",
                          json={"to_state": "NEW_CONTACT"}, headers=h)
        assert bad.status_code == 409
        # 11. Timeline + audit verification.
        timeline = client.get(f"/cases/{case_id}/timeline",
                              headers=h).json()
        types = {e["event_type"] for e in timeline}
        for expected in ["CASE_CREATED", "case.state_changed",
                         "MISSING_INFO_RESOLVED", "OFFER_CREATED",
                         "OFFER_SENT_EVENT", "CLIENT_REPLIED"]:
            assert expected in types, expected
        verify = client.get(f"/audit/verify/{case_id}", headers=h).json()
        assert verify["chain_valid"] is True
        assert verify["events_case"] >= 10
        # 12. Dashboard reflects the win.
        s = client.get("/dashboard/summary", headers=h).json()
        assert s["won_value_period"] == 9000 + 11000

    def test_high_risk_action_requires_approval_then_owner_approves(
            self, client):
        h = login(client)
        case_id = client.get("/cases", headers=h).json()[0]["id"]
        action = client.post("/actions/request", json={
            "case_id": case_id, "action_type": "send_price_negotiation",
            "risk_level": "high", "reason": "negotiation"},
            headers=h).json()
        assert action["status"] == "pending_approval"
        draft_id = action["draft_id"]
        # Viewer may not approve.
        hv = login(client, "viewer@demo.finalis")
        assert client.post(f"/actions/{draft_id}/approve", json={},
                           headers=hv).status_code == 403
        # Owner approves with an edit.
        done = client.post(f"/actions/{draft_id}/approve",
                           json={"edited_message":
                                 "Dzień dobry, wracam do oferty."},
                           headers=h).json()
        assert done["approval_status"] == "APPROVED"
        assert done["executed"] is True


class TestUiPages:
    def test_login_portal_and_upload_pages_served(self, client):
        assert "Sign in" in client.get("/").text
        assert "Case Command Center" in client.get("/portal").text
        # Upload page renders for any token; validity checked via API.
        assert "Send your photos" in client.get("/u/some-token").text

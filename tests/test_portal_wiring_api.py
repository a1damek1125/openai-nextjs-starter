"""Portal Wiring API tests (W1B) — the HTTP layer over the admin/RBAC,
scheduling, governance, and confirmation endpoints added in the portal
wiring sprint. Engines themselves are covered in test_admin_rbac.py,
test_scheduling.py, and test_governance.py; here we test the wiring:
auth, roles, tenant isolation, status codes, and that nothing secret
leaks through a response."""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from finalis.governance.runtime import GovernedRuntime
from finalis.portal.app import create_app
from finalis.portal.seed import seed

# Fixed future weekday inside business hours keeps bookings deterministic
# regardless of when the suite runs.
AT10 = "2030-03-13T10:00:00"
AT14 = "2030-03-13T14:00:00"
PAST10 = "2020-01-02T10:00:00"     # valid hour, long past → expired token


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


def first_case_id(client, h):
    return client.get("/cases", headers=h).json()[0]["id"]


def user_id_of(client, email):
    row = client.app.state.db.one("SELECT id FROM users WHERE email=?",
                                  email)
    return row["id"]


class TestAdminApi:
    def test_owner_me_lists_role_and_permissions(self, client):
        h = login(client)
        me = client.get("/admin/me", headers=h).json()
        assert me["role"] == "owner"
        assert "tenant.manage_users" in me["permissions"]
        assert "ai.approve_own_action" not in me["permissions"]  # ungrantable

    def test_admin_endpoints_require_auth(self, client):
        assert client.get("/admin/me").status_code == 401
        assert client.get("/admin/users").status_code == 401
        assert client.get("/admin/access-logs").status_code == 401

    def test_owner_lists_users_without_password_hashes(self, client):
        h = login(client)
        users = client.get("/admin/users", headers=h).json()
        emails = {u["email"] for u in users}
        assert "owner@demo.finalis" in emails
        assert "owner@other.finalis" not in emails      # tenant-scoped
        for u in users:
            assert set(u) == {"id", "email", "role"}    # no hash, no extras

    def test_viewer_cannot_list_users(self, client):
        h = login(client, "viewer@demo.finalis")
        assert client.get("/admin/users", headers=h).status_code == 403

    def test_owner_invites_viewer_gets_no_token_back(self, client):
        h = login(client)
        r = client.post("/admin/users/invite",
                        json={"email": "new@demo.finalis", "role": "viewer"},
                        headers=h)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "pending"
        assert set(body) == {"invitation_id", "status"}  # no token leaks

    def test_viewer_cannot_invite(self, client):
        h = login(client, "viewer@demo.finalis")
        r = client.post("/admin/users/invite",
                        json={"email": "x@demo.finalis", "role": "viewer"},
                        headers=h)
        assert r.status_code == 403

    def test_invite_with_unknown_role_rejected(self, client):
        h = login(client)
        r = client.post("/admin/users/invite",
                        json={"email": "x@demo.finalis",
                              "role": "superadmin"}, headers=h)
        assert r.status_code == 400

    def test_owner_promotes_viewer_to_manager(self, client):
        h = login(client)
        target = user_id_of(client, "viewer@demo.finalis")
        r = client.patch(f"/admin/memberships/{target}/role",
                         json={"role": "manager"}, headers=h)
        assert r.status_code == 200, r.text
        # Role is persisted: a fresh login carries the new role.
        h2 = login(client, "viewer@demo.finalis")
        assert client.get("/auth/me", headers=h2).json()["role"] == "manager"

    def test_viewer_cannot_change_roles(self, client):
        """A viewer demoting a manager to viewer passes the pure escalation
        check (viewer ⊆ viewer) — the endpoint must still deny it because
        the viewer lacks tenant.manage_users."""
        h = login(client, "viewer@demo.finalis")
        target = user_id_of(client, "manager@demo.finalis")
        r = client.patch(f"/admin/memberships/{target}/role",
                         json={"role": "viewer"}, headers=h)
        assert r.status_code == 403

    def test_unknown_role_change_rejected_not_500(self, client):
        h = login(client)
        target = user_id_of(client, "viewer@demo.finalis")
        assert client.patch(f"/admin/memberships/{target}/role",
                            json={"role": "superadmin"},
                            headers=h).status_code == 400
        assert client.patch(f"/admin/memberships/{target}/role",
                            json={}, headers=h).status_code == 400

    def test_last_owner_cannot_be_demoted(self, client):
        h = login(client)
        target = user_id_of(client, "owner@demo.finalis")
        r = client.patch(f"/admin/memberships/{target}/role",
                         json={"role": "manager"}, headers=h)
        assert r.status_code == 403

    def test_cross_tenant_role_change_is_404(self, client):
        h_other = login(client, "owner@other.finalis")
        target = user_id_of(client, "viewer@demo.finalis")
        r = client.patch(f"/admin/memberships/{target}/role",
                         json={"role": "viewer"}, headers=h_other)
        assert r.status_code == 404

    def test_access_logs_gated_and_tenant_scoped(self, client):
        # Generate one DENY (viewer probing) and one ALLOW (other tenant).
        hv = login(client, "viewer@demo.finalis")
        client.get("/admin/users", headers=hv)
        h_other = login(client, "owner@other.finalis")
        client.get("/admin/users", headers=h_other)
        # Viewer may not read access logs.
        assert client.get("/admin/access-logs",
                          headers=hv).status_code == 403
        # Owner sees the denial, but nothing from the other tenant.
        h = login(client)
        logs = client.get("/admin/access-logs", headers=h).json()
        assert any(e["payload"]["decision"] == "DENY" for e in logs)
        assert all(e["payload"].get("tenant_id") == "demo-hvac"
                   for e in logs)


class TestSchedulingApi:
    def test_availability_requires_auth(self, client):
        assert client.get("/scheduling/availability").status_code == 401

    def test_availability_returns_business_hour_slots(self, client):
        h = login(client)
        slots = client.get(
            "/scheduling/availability",
            params={"appointment_type": "VIDEO_CALL", "day": AT10},
            headers=h).json()
        assert slots
        for s in slots:
            assert 8 <= datetime.fromisoformat(s["start_at"]).hour < 18
            assert 0.0 <= s["score"] <= 1.0

    def test_availability_unknown_type_is_400(self, client):
        h = login(client)
        r = client.get("/scheduling/availability",
                       params={"appointment_type": "TELEPORT"}, headers=h)
        assert r.status_code == 400

    def test_book_video_call_returns_mock_link_and_confirm_url(self, client):
        h = login(client)
        case_id = first_case_id(client, h)
        r = client.post("/scheduling/appointments",
                        json={"case_id": case_id,
                              "appointment_type": "VIDEO_CALL",
                              "start_at": AT10, "user_id": "u1"}, headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "PENDING_CLIENT_CONFIRMATION"
        assert body["video_meeting_url"].startswith(
            "https://meet.finalis.example/")
        assert body["confirmation_url"].startswith("/confirm/")
        assert body["provider_is_mock"] is True
        assert "token_hash" not in r.text

    def test_viewer_cannot_book(self, client):
        h = login(client, "viewer@demo.finalis")
        case_id = first_case_id(client, h)
        r = client.post("/scheduling/appointments",
                        json={"case_id": case_id,
                              "appointment_type": "CALLBACK",
                              "start_at": AT10}, headers=h)
        assert r.status_code == 403

    def test_book_cross_tenant_case_is_404(self, client):
        h = login(client)
        case_id = first_case_id(client, h)
        h_other = login(client, "owner@other.finalis")
        r = client.post("/scheduling/appointments",
                        json={"case_id": case_id,
                              "appointment_type": "CALLBACK",
                              "start_at": AT10}, headers=h_other)
        assert r.status_code == 404

    def test_book_missing_fields_is_400_not_500(self, client):
        h = login(client)
        case_id = first_case_id(client, h)
        assert client.post("/scheduling/appointments",
                           json={"appointment_type": "CALLBACK"},
                           headers=h).status_code == 400
        assert client.post("/scheduling/appointments",
                           json={"case_id": case_id,
                                 "appointment_type": "CALLBACK",
                                 "start_at": "not-a-date"},
                           headers=h).status_code == 400
        assert client.post("/scheduling/appointments",
                           json={"case_id": case_id,
                                 "appointment_type": "TELEPORT",
                                 "start_at": AT10},
                           headers=h).status_code == 400

    def test_double_booking_same_resource_is_409(self, client):
        h = login(client)
        case_id = first_case_id(client, h)
        ok = client.post("/scheduling/appointments",
                         json={"case_id": case_id,
                               "appointment_type": "TECHNICIAN_VISIT",
                               "start_at": AT10, "resource_id": "tech-1"},
                         headers=h)
        assert ok.status_code == 200
        dup = client.post("/scheduling/appointments",
                          json={"case_id": case_id,
                                "appointment_type": "TECHNICIAN_VISIT",
                                "start_at": AT10, "resource_id": "tech-1"},
                          headers=h)
        assert dup.status_code == 409
        assert "double booking" in dup.json()["detail"]

    def test_resources_are_tenant_isolated(self, client):
        """demo-hvac's tech-1 and other-tenant's tech-1 are different
        calendars — one tenant must not be able to block (or probe)
        another tenant's resource."""
        h = login(client)
        case_id = first_case_id(client, h)
        client.post("/scheduling/appointments",
                    json={"case_id": case_id,
                          "appointment_type": "TECHNICIAN_VISIT",
                          "start_at": AT10, "resource_id": "tech-1"},
                    headers=h)
        h_other = login(client, "owner@other.finalis")
        other_case = client.post("/cases", json={"title": "Other job",
                                                 "client_name": "O"},
                                 headers=h_other).json()["case_id"]
        r = client.post("/scheduling/appointments",
                        json={"case_id": other_case,
                              "appointment_type": "TECHNICIAN_VISIT",
                              "start_at": AT10, "resource_id": "tech-1"},
                        headers=h_other)
        assert r.status_code == 200, r.text

    def test_appointment_list_is_tenant_scoped(self, client):
        h = login(client)
        case_id = first_case_id(client, h)
        client.post("/scheduling/appointments",
                    json={"case_id": case_id,
                          "appointment_type": "CALLBACK",
                          "start_at": AT10}, headers=h)
        assert client.get("/scheduling/appointments", headers=h).json()
        h_other = login(client, "owner@other.finalis")
        assert client.get("/scheduling/appointments",
                          headers=h_other).json() == []

    def test_confirm_page_and_token_flow(self, client):
        h = login(client)
        case_id = first_case_id(client, h)
        url = client.post("/scheduling/appointments",
                          json={"case_id": case_id,
                                "appointment_type": "VIDEO_CALL",
                                "start_at": AT10, "user_id": "u1"},
                          headers=h).json()["confirmation_url"]
        page = client.get(url)                     # public, no auth
        assert page.status_code == 200
        assert "Confirm" in page.text
        token = url.rsplit("/", 1)[1]
        r = client.post(f"/scheduling/confirm/{token}")
        assert r.status_code == 200
        assert r.json()["status"] == "CONFIRMED"

    def test_invalid_and_expired_tokens_rejected(self, client):
        assert client.post(
            "/scheduling/confirm/bogus-token").status_code == 404
        # A booking whose start already passed → token expired.
        h = login(client)
        case_id = first_case_id(client, h)
        url = client.post("/scheduling/appointments",
                          json={"case_id": case_id,
                                "appointment_type": "VIDEO_CALL",
                                "start_at": PAST10, "user_id": "u2"},
                          headers=h).json()["confirmation_url"]
        token = url.rsplit("/", 1)[1]
        assert client.post(f"/scheduling/confirm/{token}").status_code == 404

    def test_reschedule_cancel_and_bad_cancel(self, client):
        h = login(client)
        case_id = first_case_id(client, h)
        appt_id = client.post("/scheduling/appointments",
                              json={"case_id": case_id,
                                    "appointment_type": "CALLBACK",
                                    "start_at": AT10},
                              headers=h).json()["appointment_id"]
        r = client.post(f"/scheduling/appointments/{appt_id}/reschedule",
                        json={"new_start": AT14}, headers=h)
        assert r.json()["status"] == "RESCHEDULED"
        # Cancel without reason refused; with reason lands in a clear state.
        assert client.post(
            f"/scheduling/appointments/{appt_id}/cancel",
            json={"reason": "  ", "by": "client"},
            headers=h).status_code == 409
        r = client.post(f"/scheduling/appointments/{appt_id}/cancel",
                        json={"reason": "client unavailable",
                              "by": "client"}, headers=h)
        assert r.json()["status"] == "CANCELLED_BY_CLIENT"

    def test_completed_technician_visit_reaches_won_completed(self, client):
        """The mandated demo: mock invoice+payment, book the technician,
        complete the visit → derived lifecycle view is WON_COMPLETED."""
        h = login(client)
        case_id = first_case_id(client, h)
        for step in ("accept-offer", "invoice", "payment"):
            assert client.post(f"/cases/{case_id}/lifecycle/{step}",
                               headers=h).status_code == 200
        appt_id = client.post("/scheduling/appointments",
                              json={"case_id": case_id,
                                    "appointment_type": "TECHNICIAN_VISIT",
                                    "start_at": AT10,
                                    "resource_id": "tech-9"},
                              headers=h).json()["appointment_id"]
        r = client.post(f"/scheduling/appointments/{appt_id}/complete",
                        json={}, headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "COMPLETED"
        assert r.json()["lifecycle_view"] == "WON_COMPLETED"
        view = client.get(f"/cases/{case_id}/lifecycle", headers=h).json()
        assert view["view"] == "WON_COMPLETED"     # persisted, not in-memory

    def test_no_show_recorded_and_unknown_op_404(self, client):
        h = login(client)
        case_id = first_case_id(client, h)
        appt_id = client.post("/scheduling/appointments",
                              json={"case_id": case_id,
                                    "appointment_type": "CALLBACK",
                                    "start_at": AT14},
                              headers=h).json()["appointment_id"]
        r = client.post(f"/scheduling/appointments/{appt_id}/no-show",
                        json={}, headers=h)
        assert r.json()["status"] == "NO_SHOW"
        assert client.post(f"/scheduling/appointments/{appt_id}/explode",
                           json={}, headers=h).status_code == 404

    def test_ops_on_other_tenants_appointment_404(self, client):
        h = login(client)
        case_id = first_case_id(client, h)
        appt_id = client.post("/scheduling/appointments",
                              json={"case_id": case_id,
                                    "appointment_type": "CALLBACK",
                                    "start_at": AT10},
                              headers=h).json()["appointment_id"]
        h_other = login(client, "owner@other.finalis")
        r = client.post(f"/scheduling/appointments/{appt_id}/cancel",
                        json={"reason": "hijack", "by": "company"},
                        headers=h_other)
        assert r.status_code == 404


class TestGovernanceApi:
    def _trace(self, client, tenant="demo-hvac", **kw):
        """Simulate an agent action writing through the portal's audit DB —
        exactly what a wired GovernedRuntime will do."""
        rt = GovernedRuntime(client.app.state.audit)
        return rt.execute(tenant_id=tenant, agent_name="followup-agent",
                          action="send_reminder", tool_name="messaging",
                          fn=lambda: "ok", **kw)

    def test_traces_gated_by_audit_view(self, client):
        self._trace(client)
        hv = login(client, "viewer@demo.finalis")
        assert client.get("/governance/traces",
                          headers=hv).status_code == 403
        h = login(client)
        traces = client.get("/governance/traces", headers=h).json()
        assert traces
        assert traces[-1]["payload"]["action"] == "send_reminder"

    def test_traces_are_tenant_scoped(self, client):
        self._trace(client, tenant="demo-hvac")
        self._trace(client, tenant="other-tenant")
        h = login(client)
        traces = client.get("/governance/traces", headers=h).json()
        assert traces
        assert all(t["payload"].get("tenant_id") == "demo-hvac"
                   for t in traces)

    def test_no_secrets_in_governance_output(self, client):
        self._trace(client,
                    input_summary="calling api_key=sk-abc123def456ghi789xyz")
        h = login(client)
        text = client.get("/governance/traces", headers=h).text
        text += client.get("/governance/blocked", headers=h).text
        assert "sk-abc123" not in text

    def test_blocked_actions_have_business_language_explanations(self,
                                                                 client):
        h = login(client)
        case_id = first_case_id(client, h)
        self._trace(client, hard_blockers=["client_opted_out"],
                    case_id=case_id)
        # Simulate the ACE rate-limiter event shape (real producer tested
        # in the ACE suite; here we test the endpoint's rendering of it).
        client.app.state.audit.append(
            event_type="FOLLOW_UP_RATE_LIMITED", actor="ace",
            case_id=case_id, payload={"cooldown_hours": 48})
        blocked = client.get("/governance/blocked", headers=h).json()
        events = {b["event"] for b in blocked}
        assert "AGENT_TRACE" in events and "FOLLOW_UP_RATE_LIMITED" in events
        for b in blocked:
            assert b["explanation"]                       # never empty
            assert "policy_denied" not in b["explanation"]  # human words
        rate = next(b for b in blocked
                    if b["event"] == "FOLLOW_UP_RATE_LIMITED")
        assert "contact limit or cooldown" in rate["explanation"]

    def test_blocked_list_tenant_scoped_and_gated(self, client):
        self._trace(client, tenant="other-tenant",
                    hard_blockers=["client_opted_out"])
        hv = login(client, "viewer@demo.finalis")
        assert client.get("/governance/blocked",
                          headers=hv).status_code == 403
        h = login(client)
        assert client.get("/governance/blocked", headers=h).json() == []

    def test_audit_chain_still_verifies_after_wiring_traffic(self, client):
        h = login(client)
        client.get("/admin/users", headers=h)
        self._trace(client)
        case_id = first_case_id(client, h)
        client.post("/scheduling/appointments",
                    json={"case_id": case_id,
                          "appointment_type": "CALLBACK",
                          "start_at": AT10}, headers=h)
        assert client.app.state.audit.verify_chain()

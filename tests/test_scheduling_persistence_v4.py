"""SCHED-V4 tests — appointments and hashed confirmation tokens survive
app restarts; tokens are never stored raw; tenant isolation and the
scheduling business rules hold across the persistence boundary.

'Restart' here = a fresh create_app() over the same SQLite file, which
rebuilds every engine from scratch and hydrates from the DB.
"""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.db import Database
from finalis.portal.seed import seed

AT10 = "2030-03-13T10:00:00"
AT14 = "2030-03-13T14:00:00"
PAST10 = "2020-01-02T10:00:00"


@pytest.fixture()
def db_file(tmp_path):
    return str(tmp_path / "sched.db")


@pytest.fixture()
def client(db_file):
    app = create_app(db_file)
    seed(app.state.db)
    return TestClient(app)


def restart(db_file):
    """Fresh app instance over the same file — nothing in memory survives
    except what migration-v4 persistence brings back."""
    return TestClient(create_app(db_file))


def login(client, email="owner@demo.finalis", password="demo1234"):
    r = client.post("/auth/login", json={"email": email,
                                         "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def first_case_id(client, h):
    return client.get("/cases", headers=h).json()[0]["id"]


def book(client, h, *, appt_type="CALLBACK", start=AT10, resource=None,
         user_id=None, case_id=None):
    body = {"case_id": case_id or first_case_id(client, h),
            "appointment_type": appt_type, "start_at": start}
    if resource:
        body["resource_id"] = resource
    if user_id:
        body["user_id"] = user_id
    r = client.post("/scheduling/appointments", json=body, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


class TestMigrationAndPersistence:
    def test_1_migration_v4_creates_tables(self, tmp_path):
        db = Database(str(tmp_path / "m.db"))
        assert db.migrate() == 4
        for table in ("scheduling_appointments",
                      "scheduling_appointment_events"):
            assert db.one("SELECT name FROM sqlite_master WHERE name=?",
                          table), table

    def test_2_3_appointment_persists_and_survives_restart(self, client,
                                                           db_file):
        h = login(client)
        appt = book(client, h)
        row = client.app.state.db.one(
            "SELECT * FROM scheduling_appointments WHERE id=?",
            appt["appointment_id"])
        assert row["status"] == "CONFIRMED"      # CALLBACK: no confirm step
        c2 = restart(db_file)
        h2 = login(c2)
        listed = c2.get("/scheduling/appointments", headers=h2).json()
        assert any(a["id"] == appt["appointment_id"] for a in listed)

    def test_4_5_6_token_survives_restart_hashed_never_raw(self, client,
                                                           db_file):
        h = login(client)
        appt = book(client, h, appt_type="VIDEO_CALL", user_id="u1")
        token = appt["confirmation_url"].rsplit("/", 1)[1]
        # 5: raw token appears nowhere in the database.
        db = client.app.state.db
        for table in ("scheduling_appointments",
                      "scheduling_appointment_events", "audit_events"):
            for r in db.all(f"SELECT * FROM {table}"):
                assert token not in str(dict(r)), table
        row = db.one("SELECT confirmation_token_hash FROM "
                     "scheduling_appointments WHERE id=?",
                     appt["appointment_id"])
        assert row["confirmation_token_hash"]
        assert row["confirmation_token_hash"] != token
        # 4+6: after a restart the token still confirms (via its hash).
        c2 = restart(db_file)
        r = c2.post(f"/scheduling/confirm/{token}")
        assert r.status_code == 200
        assert r.json()["status"] == "CONFIRMED"
        # And the confirmation itself persisted: restart again and check.
        c3 = restart(db_file)
        h3 = login(c3)
        listed = c3.get("/scheduling/appointments", headers=h3).json()
        target = next(a for a in listed
                      if a["id"] == appt["appointment_id"])
        assert target["status"] == "CONFIRMED"

    def test_7_8_invalid_and_expired_tokens_404_after_restart(self, client,
                                                              db_file):
        h = login(client)
        appt = book(client, h, appt_type="VIDEO_CALL", start=PAST10,
                    user_id="u2")
        token = appt["confirmation_url"].rsplit("/", 1)[1]
        c2 = restart(db_file)
        assert c2.post("/scheduling/confirm/bogus").status_code == 404
        assert c2.post(f"/scheduling/confirm/{token}").status_code == 404
        # The EXPIRED flip was persisted, not just in-memory.
        c3 = restart(db_file)
        h3 = login(c3)
        target = next(a for a in c3.get("/scheduling/appointments",
                                        headers=h3).json()
                      if a["id"] == appt["appointment_id"])
        assert target["status"] == "EXPIRED"

    def test_13_16_ops_persist_across_restart(self, client, db_file):
        h = login(client)
        a1 = book(client, h, start=AT10)
        a2 = book(client, h, start=AT14)
        a3 = book(client, h, start="2030-03-13T16:00:00")
        a4 = book(client, h, appt_type="TECHNICIAN_VISIT",
                  start="2030-03-14T09:00:00", resource="tech-1")
        client.post(f"/scheduling/appointments/{a1['appointment_id']}"
                    "/reschedule", json={"new_start": "2030-03-13T11:00:00"},
                    headers=h)
        client.post(f"/scheduling/appointments/{a2['appointment_id']}"
                    "/cancel", json={"reason": "client away",
                                     "by": "client"}, headers=h)
        client.post(f"/scheduling/appointments/{a3['appointment_id']}"
                    "/no-show", json={}, headers=h)
        client.post(f"/scheduling/appointments/{a4['appointment_id']}"
                    "/complete", json={}, headers=h)
        c2 = restart(db_file)
        h2 = login(c2)
        by_id = {a["id"]: a for a in c2.get("/scheduling/appointments",
                                            headers=h2).json()}
        assert by_id[a1["appointment_id"]]["status"] == "RESCHEDULED"
        assert by_id[a1["appointment_id"]]["start_at"] \
            .startswith("2030-03-13 11:00")
        assert by_id[a2["appointment_id"]]["status"] == "CANCELLED_BY_CLIENT"
        assert by_id[a3["appointment_id"]]["status"] == "NO_SHOW"
        assert by_id[a4["appointment_id"]]["status"] == "COMPLETED"
        # Cancel reason persisted in the row.
        row = c2.app.state.db.one(
            "SELECT cancellation_reason FROM scheduling_appointments "
            "WHERE id=?", a2["appointment_id"])
        assert row["cancellation_reason"] == "client away"

    def test_12_double_booking_survives_restart(self, client, db_file):
        h = login(client)
        book(client, h, appt_type="TECHNICIAN_VISIT", start=AT10,
             resource="tech-1")
        # After restart the hydrated engine still sees the conflict.
        c2 = restart(db_file)
        h2 = login(c2)
        r = c2.post("/scheduling/appointments", json={
            "case_id": first_case_id(c2, h2),
            "appointment_type": "TECHNICIAN_VISIT",
            "start_at": AT10, "resource_id": "tech-1"}, headers=h2)
        assert r.status_code == 409
        assert "double booking" in r.json()["detail"]


class TestTenantIsolation:
    def _other_case(self, client):
        h_other = login(client, "owner@other.finalis")
        case = client.post("/cases", json={"title": "Other job",
                                           "client_name": "O"},
                           headers=h_other).json()["case_id"]
        return h_other, case

    def test_9_10_cross_tenant_read_and_mutate_denied(self, client,
                                                      db_file):
        h = login(client)
        appt = book(client, h)
        c2 = restart(db_file)
        h_other = login(c2, "owner@other.finalis")
        assert c2.get("/scheduling/appointments",
                      headers=h_other).json() == []
        for op, body in [("cancel", {"reason": "hijack", "by": "company"}),
                         ("complete", {}), ("no-show", {}),
                         ("reschedule", {"new_start": AT14})]:
            r = c2.post(f"/scheduling/appointments/"
                        f"{appt['appointment_id']}/{op}",
                        json=body, headers=h_other)
            assert r.status_code == 404, op

    def test_11_same_resource_across_tenants_no_collision(self, client,
                                                          db_file):
        h = login(client)
        book(client, h, appt_type="TECHNICIAN_VISIT", start=AT10,
             resource="tech-1")
        c2 = restart(db_file)             # isolation holds post-hydration
        h_other, other_case = self._other_case(c2)
        r = c2.post("/scheduling/appointments", json={
            "case_id": other_case,
            "appointment_type": "TECHNICIAN_VISIT",
            "start_at": AT10, "resource_id": "tech-1"}, headers=h_other)
        assert r.status_code == 200, r.text

    def test_isolation_invariant_rows(self, client):
        """Property: every persisted appointment row belongs to the tenant
        that created it — no NULL/foreign tenant rows exist."""
        h = login(client)
        book(client, h, start=AT10)
        book(client, h, appt_type="VIDEO_CALL", start=AT14, user_id="u1")
        h_other, other_case = self._other_case(client)
        client.post("/scheduling/appointments", json={
            "case_id": other_case, "appointment_type": "CALLBACK",
            "start_at": AT10}, headers=h_other)
        rows = client.app.state.db.all(
            "SELECT tenant_id, case_id FROM scheduling_appointments")
        assert all(r["tenant_id"] in ("demo-hvac", "other-tenant")
                   for r in rows)
        demo_cases = {r["id"] for r in client.app.state.db.all(
            "SELECT id FROM cases WHERE tenant_id='demo-hvac'")}
        for r in rows:
            if r["tenant_id"] == "demo-hvac":
                assert r["case_id"] in demo_cases


class TestSideEffectsStillWork:
    def test_17_appointment_events_written(self, client):
        h = login(client)
        appt = book(client, h, start=AT10)
        client.post(f"/scheduling/appointments/{appt['appointment_id']}"
                    "/complete", json={}, headers=h)
        events = client.app.state.db.all(
            "SELECT event_type FROM scheduling_appointment_events WHERE "
            "appointment_id=?", appt["appointment_id"])
        types = {e["event_type"] for e in events}
        assert {"BOOKED", "COMPLETE"} <= types

    def test_18_19_20_lifecycle_semantics_survive_restart(self, client,
                                                          db_file):
        h = login(client)
        case_id = first_case_id(client, h)
        for step in ("accept-offer", "invoice", "payment"):
            client.post(f"/cases/{case_id}/lifecycle/{step}", headers=h)
        video = book(client, h, appt_type="VIDEO_CALL", start=AT10,
                     user_id="u1", case_id=case_id)
        tech = book(client, h, appt_type="TECHNICIAN_VISIT", start=AT14,
                    resource="tech-9", case_id=case_id)
        c2 = restart(db_file)
        h2 = login(c2)
        # 19: completing the video call does NOT complete fulfillment.
        r = c2.post(f"/scheduling/appointments/{video['appointment_id']}"
                    "/complete", json={}, headers=h2)
        assert r.json()["lifecycle_view"] == "WON_PAID_NOT_DELIVERED"
        # 20: completing the technician visit does (Completion Loop ran).
        r = c2.post(f"/scheduling/appointments/{tech['appointment_id']}"
                    "/complete", json={}, headers=h2)
        assert r.json()["lifecycle_view"] == "WON_COMPLETED"
        view = c2.get(f"/cases/{case_id}/lifecycle", headers=h2).json()
        assert view["view"] == "WON_COMPLETED"

    def test_23_ui_no_longer_claims_in_memory(self, client):
        page = client.get("/portal").text
        assert "do not survive" not in page
        assert "persisted locally" in page
        assert "in-memory only" not in page
        # Mock provider honesty labels stay.
        assert "mocks" in page and "BLOCKED_BY_CREDENTIALS" in page

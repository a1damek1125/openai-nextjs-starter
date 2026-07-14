"""The founder demo flow through real APIs + mock providers + local DB:
inbound call → case → analysis → follow-up → upload → offer accepted →
WON_NOT_FULFILLED → mock invoice → mock payment → mock fulfillment →
WON_COMPLETED → audit verified. Plus telephony endpoints + tenant checks."""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.seed import seed

SEGMENTS = [
    {"speaker": "SPEAKER_00", "text": "Hi, I'd like a quote for a heat pump "
     "installation.", "start_ms": 0, "end_ms": 3000,
     "asr_confidence": 0.95, "diar_confidence": 0.95, "language": "en"},
    {"speaker": "SPEAKER_00", "text": "I'll send you the photos tomorrow.",
     "start_ms": 3200, "end_ms": 5400, "asr_confidence": 0.93,
     "diar_confidence": 0.95, "language": "en"},
]


@pytest.fixture()
def client():
    app = create_app(":memory:")
    seed(app.state.db)
    return TestClient(app)


def login(client, email="owner@demo.finalis"):
    r = client.post("/auth/login", json={"email": email,
                                         "password": "demo1234"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


class TestTelephonyEndpoints:
    def test_inbound_simulation_creates_case_and_call(self, client):
        h = login(client)
        r = client.post("/telephony/inbound/simulate",
                        json={"caller_number": "+48601111222",
                              "segments": SEGMENTS}, headers=h).json()
        assert r["disposition"] == "ANSWERED_COMPLETED"
        assert r["provider_is_mock"] is True
        assert r["case_id"]
        calls = client.get("/telephony/calls", headers=h).json()
        assert calls[0]["direction"] == "inbound"

    def test_outbound_blocked_by_optout(self, client):
        h = login(client)
        case_id = client.get("/cases", headers=h).json()[0]["id"]
        r = client.post("/telephony/outbound/request",
                        json={"case_id": case_id,
                              "destination": "+48601111333",
                              "reason": "follow up",
                              "contact_state": {"opted_out": True}},
                        headers=h).json()
        assert r["permission"] == "BLOCK"
        assert r["disposition"] == "FAILED_PERMISSION_BLOCK"

    def test_outbound_no_answer_gets_retry_plan(self, client):
        h = login(client)
        case_id = client.get("/cases", headers=h).json()[0]["id"]
        # urgent=True keeps the test deterministic across business hours
        # (the SCHEDULE_LATER path is covered in tests/test_telephony.py).
        r = client.post("/telephony/outbound/request",
                        json={"case_id": case_id,
                              "destination": "+48601111444",
                              "reason": "follow up",
                              "scenario": "no_answer", "urgent": True,
                              "contact_state":
                                  {"last_attempt_hours_ago": 48}},
                        headers=h).json()
        assert r["disposition"] == "NO_ANSWER"
        assert r["retry"] in ("RETRY_NOW", "RETRY_LATER",
                              "USE_OTHER_CHANNEL")

    def test_viewer_cannot_request_outbound(self, client):
        hv = login(client, "viewer@demo.finalis")
        r = client.post("/telephony/outbound/request",
                        json={"destination": "+48601111555"}, headers=hv)
        assert r.status_code == 403


class TestFullLifecycleDemoFlow:
    def test_won_not_fulfilled_to_won_completed(self, client):
        h = login(client)
        # Case via inbound call.
        call = client.post("/telephony/inbound/simulate",
                           json={"caller_number": "+48602222333",
                                 "segments": SEGMENTS}, headers=h).json()
        case_id = call["case_id"]

        # Accept offer → commercially won but NOT complete.
        r = client.post(f"/cases/{case_id}/lifecycle/accept-offer",
                        headers=h).json()
        assert r["view"] == "WON_NOT_FULFILLED"
        assert "not complete yet" in r["message"]
        lc = client.get(f"/cases/{case_id}/lifecycle", headers=h).json()
        assert lc["can_complete"] is False
        assert any("invoice" in b or "payment" in b
                   for b in lc["blocked_reasons"])

        # Mock invoice → still not complete (payment pending).
        client.post(f"/cases/{case_id}/lifecycle/invoice", headers=h)
        # Mock payment → paid but fulfillment open.
        r2 = client.post(f"/cases/{case_id}/lifecycle/payment",
                         headers=h).json()
        assert r2["view"] == "WON_PAID_NOT_DELIVERED"

        # Mock fulfillment schedule + complete → WON_COMPLETED.
        client.post(f"/cases/{case_id}/lifecycle/fulfillment-schedule",
                    headers=h)
        r3 = client.post(f"/cases/{case_id}/lifecycle/fulfillment-complete",
                         headers=h).json()
        assert r3["view"] == "WON_COMPLETED"
        lc2 = client.get(f"/cases/{case_id}/lifecycle", headers=h).json()
        assert lc2["can_complete"] is True

        # Audit trail carries the mock provider events + chain verifies.
        timeline = client.get(f"/cases/{case_id}/timeline",
                              headers=h).json()
        types = {e["event_type"] for e in timeline}
        for expected in ["CASE_WON_NOT_FULFILLED", "INVOICE_ISSUED",
                         "PAYMENT_RECEIVED", "FULFILLMENT_SCHEDULED",
                         "FULFILLMENT_COMPLETED"]:
            assert expected in types, expected
        invoice_ev = next(e for e in timeline
                          if e["event_type"] == "INVOICE_ISSUED")
        assert invoice_ev["payload"]["is_mock"] is True   # honestly marked
        verify = client.get(f"/audit/verify/{case_id}", headers=h).json()
        assert verify["chain_valid"] is True

    def test_cannot_complete_without_payment(self, client):
        h = login(client)
        call = client.post("/telephony/inbound/simulate",
                           json={"caller_number": "+48603333444",
                                 "segments": SEGMENTS}, headers=h).json()
        case_id = call["case_id"]
        client.post(f"/cases/{case_id}/lifecycle/accept-offer", headers=h)
        client.post(f"/cases/{case_id}/lifecycle/invoice", headers=h)
        # Fulfillment done but NOT paid → still not completable.
        client.post(f"/cases/{case_id}/lifecycle/fulfillment-schedule",
                    headers=h)
        client.post(f"/cases/{case_id}/lifecycle/fulfillment-complete",
                    headers=h)
        lc = client.get(f"/cases/{case_id}/lifecycle", headers=h).json()
        assert lc["can_complete"] is False
        assert any("payment" in b for b in lc["blocked_reasons"])
        assert lc["view"] == "WON_NOT_FULFILLED"

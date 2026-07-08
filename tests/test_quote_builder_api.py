"""Quote Builder API tests (Q-B) — persistence, RBAC, tenant isolation,
state transitions over HTTP, following the W1B TestClient pattern.

Engine math is proven in test_quote_builder_core.py; here we prove the
wiring: migration-v3 round-trips, permissions, status codes, and that
immutability + 'accepted ≠ completed' survive the API + database."""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.seed import seed


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


def make_quote(client, h, *, cost="100", price="200", case_id=None,
               **line_extra):
    case_id = case_id or first_case_id(client, h)
    q = client.post("/quotes", json={"case_id": case_id}, headers=h).json()
    r = client.post(f"/quotes/{q['id']}/lines",
                    json={"description": "heat pump", "material_cost": cost,
                          "price_book_price": price, **line_extra},
                    headers=h)
    assert r.status_code == 200, r.text
    return q["id"]


def make_sendable(client, h, **kw):
    qid = make_quote(client, h, **kw)
    client.patch(f"/quotes/{qid}",
                 json={"assumptions": ["one-day install"],
                       "exclusions": ["electrical rework"],
                       "terms_template_id": "hvac-standard-v1",
                       "terms_template_approved": True}, headers=h)
    r = client.post(f"/quotes/{qid}/calculate", json={}, headers=h)
    assert r.status_code == 200, r.text
    return qid, r.json()


class TestDraftPersistenceRbac:
    def test_1_2_owner_creates_draft_and_it_persists(self, tmp_path):
        db_file = str(tmp_path / "q.db")
        app1 = create_app(db_file)
        seed(app1.state.db)
        c1 = TestClient(app1)
        h = login(c1)
        qid = make_quote(c1, h)
        # A new process over the same file sees the same quote + line.
        c2 = TestClient(create_app(db_file))
        h2 = login(c2)
        q = c2.get(f"/quotes/{qid}", headers=h2).json()
        assert q["state"] == "DRAFT"
        assert q["line_items"][0]["description"] == "heat pump"

    def test_3_4_list_tenant_scoped_and_cross_tenant_404(self, client):
        h = login(client)
        qid = make_quote(client, h)
        assert any(q["id"] == qid
                   for q in client.get("/quotes", headers=h).json())
        h_other = login(client, "owner@other.finalis")
        assert client.get("/quotes", headers=h_other).json() == []
        assert client.get(f"/quotes/{qid}",
                          headers=h_other).status_code == 404
        assert client.patch(f"/quotes/{qid}", json={},
                            headers=h_other).status_code == 404
        assert client.post(f"/quotes/{qid}/send", json={},
                           headers=h_other).status_code == 404

    def test_5_viewer_cannot_mutate(self, client):
        h = login(client)
        qid = make_quote(client, h)
        hv = login(client, "viewer@demo.finalis")
        assert client.get(f"/quotes/{qid}",
                          headers=hv).status_code == 200   # read ok
        for call in [
                lambda: client.post("/quotes",
                                    json={"case_id": "x"}, headers=hv),
                lambda: client.post(f"/quotes/{qid}/lines",
                                    json={"description": "x"}, headers=hv),
                lambda: client.post(f"/quotes/{qid}/calculate", json={},
                                    headers=hv),
                lambda: client.post(f"/quotes/{qid}/send", json={},
                                    headers=hv),
                lambda: client.patch(f"/quotes/{qid}", json={},
                                     headers=hv)]:
            assert call().status_code == 403

    def test_6_operator_cannot_approve(self, client):
        h = login(client)
        qid, _ = make_sendable(client, h)
        ho = login(client, "operator@demo.finalis")
        assert client.post(f"/quotes/{qid}/approve",
                           headers=ho).status_code == 403

    def test_7_nobody_approves_own_quote(self, client):
        """The engine ban surfaces as 403 at the API: the quote creator
        (human or AI) cannot approve their own quote."""
        h = login(client)
        qid, _ = make_sendable(client, h)
        r = client.post(f"/quotes/{qid}/approve", headers=h)
        assert r.status_code == 403
        assert "own quote" in r.json()["detail"]

    def test_27_invalid_payloads_400(self, client):
        h = login(client)
        assert client.post("/quotes", json={}, headers=h).status_code == 400
        qid = make_quote(client, h)
        assert client.post(f"/quotes/{qid}/lines", json={},
                           headers=h).status_code == 400
        assert client.post(f"/quotes/{qid}/lines",
                           json={"description": "x",
                                 "material_cost": "not-a-number"},
                           headers=h).status_code == 400
        assert client.post(f"/quotes/{qid}/decline", json={"reason": "  "},
                           headers=h).status_code == 400


class TestCalculationAndGates:
    def test_8_9_line_added_and_calculate_returns_totals_and_gates(
            self, client):
        h = login(client)
        qid, calc = make_sendable(client, h)
        assert calc["subtotal"] == "200.00"
        assert calc["tax_total"] == "46.00"        # mock 23% VAT
        assert calc["total"] == "246.00"
        assert calc["tax_engine_is_mock"] is True
        assert calc["gates"]["readiness"]["decision"] == "READY"
        assert calc["gates"]["margin"]["decision"] == "SAFE"
        assert calc["gates"]["discount"]["decision"] == "SAFE"
        assert 0 <= calc["scores"]["price_confidence"] <= 1

    def test_10_negative_margin_blocks_send(self, client):
        h = login(client)
        qid, calc = make_sendable(client, h, cost="500",
                                  manual_price="400")
        assert calc["gates"]["margin"]["decision"] == "BLOCKED"
        r = client.post(f"/quotes/{qid}/send", json={}, headers=h)
        assert r.status_code == 409
        assert "below cost" in r.json()["detail"]

    def test_11_12_discount_above_threshold_then_approved_send(self,
                                                               client):
        # Manager drafts with a big discount; owner approves; send works.
        hm = login(client, "manager@demo.finalis")
        qid, calc = make_sendable(client, hm, price="2000",
                                  requested_discount="500",
                                  discount_reason="negotiation")
        assert calc["gates"]["discount"]["decision"] == "REQUIRE_APPROVAL"
        blocked = client.post(f"/quotes/{qid}/send", json={}, headers=hm)
        assert blocked.status_code == 409
        h = login(client)
        assert client.post(f"/quotes/{qid}/approve",
                           headers=h).status_code == 200
        sent = client.post(f"/quotes/{qid}/send", json={}, headers=hm)
        assert sent.status_code == 200, sent.text
        assert sent.json()["state"] == "SENT"

    def test_28_invalid_state_transition_409(self, client):
        h = login(client)
        qid = make_quote(client, h)
        # DRAFT cannot expire, cannot decline, cannot accept.
        assert client.post(f"/quotes/{qid}/expire",
                           headers=h).status_code == 409
        assert client.post(f"/quotes/{qid}/decline", json={"reason": "no"},
                           headers=h).status_code == 409
        assert client.post(f"/quotes/{qid}/accept", json={},
                           headers=h).status_code == 409


class TestImmutabilityOverHttp:
    def _sent(self, client, h, **kw):
        qid, _ = make_sendable(client, h, **kw)
        r = client.post(f"/quotes/{qid}/send", json={}, headers=h)
        assert r.status_code == 200, r.text
        return qid

    def test_13_sent_quote_cannot_be_patched(self, client, tmp_path):
        h = login(client)
        qid = self._sent(client, h)
        assert client.patch(f"/quotes/{qid}",
                            json={"assumptions": ["changed"]},
                            headers=h).status_code == 409
        assert client.post(f"/quotes/{qid}/lines",
                           json={"description": "sneaky extra"},
                           headers=h).status_code == 409
        assert client.post(f"/quotes/{qid}/payment-schedule",
                           json={"milestones": [
                               {"label": "all", "fraction": "1"}]},
                           headers=h).status_code == 409

    def test_14_accepted_quote_cannot_be_patched_or_revised(self, client):
        h = login(client)
        qid = self._sent(client, h)
        assert client.post(f"/quotes/{qid}/accept", json={},
                           headers=h).status_code == 200
        assert client.patch(f"/quotes/{qid}", json={},
                            headers=h).status_code == 409
        r = client.post(f"/quotes/{qid}/revise", headers=h)
        assert r.status_code == 409
        assert "ChangeOrder" in r.json()["detail"]

    def test_15_revision_creates_new_version(self, client):
        h = login(client)
        qid = self._sent(client, h)
        r = client.post(f"/quotes/{qid}/revise", headers=h)
        assert r.status_code == 200
        new = r.json()
        assert new["version"] == 2 and new["state"] == "DRAFT"
        assert new["revised_from_id"] == qid
        # Old version persisted as REVISED; sending v2 supersedes it.
        assert client.get(f"/quotes/{qid}",
                          headers=h).json()["state"] == "REVISED"
        # Revisions recalculate before sending (fresh DRAFT).
        assert client.post(f"/quotes/{new['id']}/calculate", json={},
                           headers=h).status_code == 200
        sent = client.post(f"/quotes/{new['id']}/send", json={}, headers=h)
        assert sent.status_code == 200
        assert client.get(f"/quotes/{qid}",
                          headers=h).json()["state"] == "SUPERSEDED"

    def test_16_expired_quote_cannot_be_accepted(self, client):
        h = login(client)
        qid = self._sent(client, h)
        assert client.post(f"/quotes/{qid}/expire",
                           headers=h).status_code == 200
        r = client.post(f"/quotes/{qid}/accept", json={}, headers=h)
        assert r.status_code == 409

    def test_17_decline_requires_reason(self, client):
        h = login(client)
        qid = self._sent(client, h)
        assert client.post(f"/quotes/{qid}/decline", json={},
                           headers=h).status_code == 400
        r = client.post(f"/quotes/{qid}/decline",
                        json={"reason": "price too high"}, headers=h)
        assert r.json()["state"] == "DECLINED"


class TestAcceptanceFlow:
    def _sent_with_schedule(self, client, h):
        qid, _ = make_sendable(client, h, price="2000", cost="1000")
        r = client.post(f"/quotes/{qid}/payment-schedule", json={
            "milestones": [
                {"label": "deposit", "fraction": "0.3", "is_deposit": True,
                 "blocks_fulfillment_until_paid": True},
                {"label": "final", "fraction": "0.7",
                 "trigger": "on_completion"}]}, headers=h)
        assert r.status_code == 200, r.text
        # Schedule change re-runs calculate (schedule set while editable).
        client.post(f"/quotes/{qid}/calculate", json={}, headers=h)
        assert client.post(f"/quotes/{qid}/send", json={},
                           headers=h).status_code == 200
        return qid

    def test_18_payment_schedule_persists(self, client):
        h = login(client)
        qid = self._sent_with_schedule(client, h)
        ps = client.get(f"/quotes/{qid}/payment-schedule",
                        headers=h).json()
        assert [m["label"] for m in ps["milestones"]] == ["deposit",
                                                          "final"]
        bad = client.post(f"/quotes/{qid}/payment-schedule", json={
            "milestones": [{"label": "half", "fraction": "0.5"}]},
            headers=h)
        assert bad.status_code == 409           # sent quote is immutable

    def test_19_20_accept_creates_requirements_not_completion(self,
                                                              client):
        h = login(client)
        qid = self._sent_with_schedule(client, h)
        r = client.post(f"/quotes/{qid}/accept", json={}, headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["case_completed"] is False
        assert body["lifecycle_view"] == "WON_NOT_FULFILLED"
        reqs = body["payment_requirements"]
        assert len(reqs) == 2
        assert reqs[0]["blocks_fulfillment_until_paid"] is True
        total = sum(float(x["amount"]) for x in reqs)
        assert abs(total - float(body["total"])) < 0.001
        assert body["invoice_handoff"]["is_mock"] is True
        # Requirements persisted; case lifecycle NOT completed.
        ps = client.get(f"/quotes/{qid}/payment-schedule",
                        headers=h).json()
        assert len(ps["payment_requirements"]) == 2
        case_id = body["case_id"]
        view = client.get(f"/cases/{case_id}/lifecycle", headers=h).json()
        assert view["view"] == "WON_NOT_FULFILLED"
        assert view["view"] != "WON_COMPLETED"

    def test_manual_acceptance_requires_evidence(self, client):
        h = login(client)
        qid, _ = make_sendable(client, h)
        client.post(f"/quotes/{qid}/send", json={}, headers=h)
        assert client.post(f"/quotes/{qid}/accept",
                           json={"channel": "verbal_call"},
                           headers=h).status_code == 400
        r = client.post(f"/quotes/{qid}/accept", json={
            "channel": "verbal_call",
            "evidence": {"kind": "verbal_call",
                         "reference_id": "segment-42"}}, headers=h)
        assert r.status_code == 200
        assert r.json()["state"] == "ACCEPTED"

    def test_21_22_change_order_after_acceptance_with_margin(self, client):
        h = login(client)
        qid, _ = make_sendable(client, h)
        # Before acceptance a change order is refused (409, wrong state).
        assert client.post(f"/quotes/{qid}/change-orders",
                           json={"description": "x", "price_delta": "100"},
                           headers=h).status_code == 409
        client.post(f"/quotes/{qid}/send", json={}, headers=h)
        client.post(f"/quotes/{qid}/accept", json={}, headers=h)
        r = client.post(f"/quotes/{qid}/change-orders",
                        json={"description": "extra duct run",
                              "price_delta": "450", "cost_delta": "300"},
                        headers=h)
        assert r.status_code == 200
        co = r.json()
        assert co["status"] == "PENDING_APPROVAL"
        assert co["requires_approval"] is True
        assert co["margin_percent"] == "0.3333"    # recalculated on delta
        listed = client.get(f"/quotes/{qid}/change-orders",
                            headers=h).json()
        assert listed and listed[0]["description"] == "extra duct run"


class TestDocumentsEventsAudit:
    def test_23_generate_pdf_creates_mock_document(self, client):
        h = login(client)
        qid, _ = make_sendable(client, h)
        r = client.post(f"/quotes/{qid}/generate-pdf", headers=h)
        assert r.status_code == 200
        body = r.json()
        assert body["is_mock"] is True and body["provider"] == "mock-pdf"
        assert "MOCK DOCUMENT" in body["html"]
        assert "heat pump" in body["html"]
        row = client.app.state.db.one(
            "SELECT * FROM quote_pdf_documents WHERE id=?",
            body["document_id"])
        assert row and row["is_mock"] == 1

    def test_24_25_quote_events_and_audit_written(self, client):
        h = login(client)
        qid, _ = make_sendable(client, h)
        client.post(f"/quotes/{qid}/send", json={}, headers=h)
        client.post(f"/quotes/{qid}/accept", json={}, headers=h)
        events = client.get(f"/quotes/{qid}/events", headers=h).json()
        types = {e["event_type"] for e in events}
        assert {"QUOTE_DRAFT_CREATED", "QUOTE_LINE_ADDED",
                "QUOTE_PRICE_CALCULATED", "QUOTE_SENT",
                "QUOTE_ACCEPTED"} <= types
        accepted = next(e for e in events
                        if e["event_type"] == "QUOTE_ACCEPTED")
        assert accepted["payload"]["case_completed"] is False
        # Events endpoint is permission-gated (audit.view).
        hv = login(client, "viewer@demo.finalis")
        assert client.get(f"/quotes/{qid}/events",
                          headers=hv).status_code == 403
        # And the persisted audit chain still verifies.
        assert client.app.state.audit.verify_chain()

    def test_evidence_endpoint(self, client):
        h = login(client)
        qid = make_quote(client, h)
        ev = client.get(f"/quotes/{qid}/evidence", headers=h).json()
        assert "evidence_coverage_score" in ev
        assert 0 <= ev["evidence_coverage_score"] <= 1


class TestPricingConfig:
    def test_26_price_books_and_rules_endpoints(self, client):
        h = login(client)
        book = client.post("/price-books", json={"name": "hvac-2026"},
                           headers=h).json()
        r = client.post(f"/price-books/{book['id']}/items",
                        json={"sku": "HP-12KW", "name": "12kW pump",
                              "list_price": "9500"}, headers=h)
        assert r.status_code == 200
        items = client.get(f"/price-books/{book['id']}/items",
                           headers=h).json()
        assert items[0]["sku"] == "HP-12KW"
        rule = client.post("/pricing-rules",
                           json={"name": "bulk", "applies_to_sku": "HP-12KW",
                                 "min_quantity": "2",
                                 "discount_percent": "5"}, headers=h).json()
        assert client.patch(f"/pricing-rules/{rule['id']}",
                            json={"priority": 5},
                            headers=h).status_code == 200
        # Price book feeds calculation: SKU line picks up the book price.
        qid = make_quote(client, h)
        client.post(f"/quotes/{qid}/lines",
                    json={"description": "pump by sku", "sku": "HP-12KW",
                          "material_cost": "4000"}, headers=h)
        calc = client.post(f"/quotes/{qid}/calculate", json={},
                           headers=h).json()
        by_sku = next(l for l in calc["line_items"]
                      if l["sku"] == "HP-12KW")
        assert by_sku["price_before_discount"] == "9500.00"
        # Cross-tenant: other tenant sees neither book nor rules.
        h_other = login(client, "owner@other.finalis")
        assert client.get("/price-books", headers=h_other).json() == []
        assert client.get(f"/price-books/{book['id']}/items",
                          headers=h_other).status_code == 404
        assert client.get("/pricing-rules", headers=h_other).json() == []

    def test_stateless_pricing_calculate_and_validate(self, client):
        h = login(client)
        r = client.post("/pricing/calculate", json={"lines": [
            {"description": "what-if pump", "material_cost": "650",
             "price_book_price": "700"}]}, headers=h)
        assert r.status_code == 200
        body = r.json()
        assert body["persisted"] is False
        # Margin floor beats the weak book price: 650/(1-0.35) = 1000.
        assert body["line_items"][0]["price_before_discount"] == "1000.00"
        v = client.post("/pricing/validate", json={"lines": [
            {"description": "loss", "material_cost": "500",
             "manual_price": "400"}]}, headers=h).json()
        assert v["gates"]["margin"]["decision"] == "BLOCKED"
        assert client.post("/pricing/calculate", json={"lines": []},
                           headers=h).status_code == 400

    def test_29_tenant_isolation_invariant(self, client):
        """Property-style sweep: everything quote-scoped answers 404/empty
        for the other tenant, for every verb."""
        h = login(client)
        qid, _ = make_sendable(client, h)
        h_other = login(client, "owner@other.finalis")
        for method, path, body in [
                ("get", f"/quotes/{qid}", None),
                ("patch", f"/quotes/{qid}", {}),
                ("post", f"/quotes/{qid}/lines", {"description": "x"}),
                ("post", f"/quotes/{qid}/calculate", {}),
                ("post", f"/quotes/{qid}/send", {}),
                ("post", f"/quotes/{qid}/accept", {}),
                ("post", f"/quotes/{qid}/decline", {"reason": "x"}),
                ("post", f"/quotes/{qid}/revise", None),
                ("post", f"/quotes/{qid}/generate-pdf", None),
                ("get", f"/quotes/{qid}/events", None),
                ("get", f"/quotes/{qid}/payment-schedule", None),
                ("get", f"/quotes/{qid}/change-orders", None)]:
            fn = getattr(client, method)
            r = fn(path, headers=h_other) if body is None else \
                fn(path, json=body, headers=h_other)
            assert r.status_code == 404, (method, path, r.status_code)

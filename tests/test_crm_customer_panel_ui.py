"""CRM-C static UI checks — the Customer Panel is served, calls the
tested CRM-B APIs, and carries the mandated honesty/consent/memory/merge
labels. Browser behaviour is CRM-D."""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.seed import seed


@pytest.fixture()
def page():
    app = create_app(":memory:")
    seed(app.state.db)
    return TestClient(app).get("/portal").text


class TestCustomerPanelStatic:
    def test_1_sections_and_panels_exist(self, page):
        for marker in ['id="crm-section"', 'id="crm-dashboard"',
                       'id="crm-create"', 'id="crm-list"',
                       'id="crm-detail"', 'id="crm-caseparties"',
                       "Customer Panel", "Consent Center",
                       "Customer memory", "Duplicates / merge",
                       "External CRM (dry-run only)",
                       "Case relationships",
                       "Customer Readiness Index", "crmFor"]:
            assert marker in page, marker

    def test_2_11_ui_calls_tested_apis(self, page):
        for endpoint in ["/crm/parties", "/crm/parties/", "/contacts",
                         "/consents", "/crm/consent/check", "/promises",
                         "/memory", "/crm/relationships", "/crm/cases/",
                         "/dedupe-candidates", "/crm/merge",
                         "/external-references", "/crm/sync/dry-run",
                         "/crm/sync/decision"]:
            assert endpoint in page, endpoint
        # verify/dispute/mark-stale run through memAct(memId, action).
        assert "/crm/memory/${memId}/${action}" in page
        for action in ["'verify'", "'dispute'", "'mark-stale'"]:
            assert action in page, action

    def test_12_19_honesty_labels(self, page):
        norm = " ".join(page.split())     # collapse HTML line wrapping
        for label in ["Marketing consent is never implied",
                      "Only a human can verify memory",
                      "Disputed facts block automation",
                      "Merge is human-only",
                      "External CRM cannot overwrite verified "
                      "Finalis data",
                      "Case outcome fields are owned by Finalis",
                      "no external provider is called",
                      "Production readiness is false",
                      "AI-suggested memory is not a verified fact",
                      "Cross-tenant duplicates can never merge",
                      "tombstoned, not deleted",
                      "NON-AUTHORITATIVE UI SUMMARY",
                      "SCAFFOLDED_ONLY",
                      "OAuth is not implemented",
                      "webhook ingestion is not implemented",
                      # CRM-C1 mandated exact sentences.
                      "Finalis is the source of operational truth for "
                      "case outcomes.",
                      "AI can suggest. Human verification decides.",
                      "AI may suggest candidates but cannot approve merge.",
                      "Revoked or denied consent cannot be overridden "
                      "by AI",
                      "Unknown marketing consent requires human review",
                      "server-side policy remains the source of truth"]:
            assert label in norm, label

    def test_20_no_hardcoded_fake_crm_rows(self, page):
        assert "Loading customers…" in page
        assert "Jan Kowalski" not in page       # no baked-in customers
        assert "hubspot.com" not in page
        assert "owner@demo.finalis" not in page

    def test_untrusted_strings_escaped(self, page):
        # Content-bearing CRM fields render through esc() only.
        for escaped in ["esc(p.display_name)", "esc(d.display_name)",
                        "esc(c.value)", "esc(p.what)",
                        "esc(JSON.stringify(m.content))",
                        "c.signals.map(esc)",
                        "data.reasons.map(esc)"]:
            assert escaped in page, escaped

    def test_c1_no_production_claim_and_dry_run_only(self, page):
        norm = " ".join(page.split())
        # No text asserts production-readiness or a live connection.
        for banned in ("production ready", "connected to hubspot",
                       "live sync", "provider connected"):
            assert banned.lower() not in norm.lower(), banned
        # Sync is explicitly dry-run/decision, never a real write.
        assert "external write happened" in page
        assert "Dry-run only" in page or "dry-run/decision only" in page

    def test_c1_overdue_promise_logic_present(self, page):
        # Overdue highlighting is computed from due_at (regression guard
        # for the promises API change that now exposes due_at).
        assert "OVERDUE" in page
        assert "new Date(p.due_at)" in page


class TestPromisesDueAtApi:
    """Regression for the smallest CRM-B addition CRM-C1 required:
    the promises API now exposes and accepts due_at (already persisted)."""

    def test_promise_roundtrips_due_at(self):
        from finalis.portal.app import create_app
        from finalis.portal.seed import seed
        app = create_app(":memory:")
        seed(app.state.db)
        c = TestClient(app)
        tok = c.post("/auth/login", json={"email": "owner@demo.finalis",
                                          "password": "demo1234"}
                     ).json()["token"]
        h = {"Authorization": f"Bearer {tok}"}
        p = c.post("/crm/parties", json={"kind": "person",
                                         "display_name": "Due Person"},
                   headers=h).json()
        r = c.post(f"/crm/parties/{p['id']}/promises", json={
            "promisor": "finalis", "what": "call back",
            "due_at": "2020-01-01T09:00:00"}, headers=h)
        assert r.status_code == 200
        assert r.json()["due_at"] == "2020-01-01T09:00:00"
        listed = c.get(f"/crm/parties/{p['id']}/promises",
                       headers=h).json()
        assert listed[0]["due_at"] == "2020-01-01T09:00:00"
        # Invalid due_at is a clean 400.
        assert c.post(f"/crm/parties/{p['id']}/promises", json={
            "promisor": "finalis", "what": "x",
            "due_at": "not-a-date"}, headers=h).status_code == 400

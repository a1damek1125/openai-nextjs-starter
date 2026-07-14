"""Q-C static UI checks — the quote sections are served, call the tested
Q-B APIs, and carry the mandated honesty labels. Browser behaviour is Q-D."""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.seed import seed


@pytest.fixture()
def page():
    app = create_app(":memory:")
    seed(app.state.db)
    return TestClient(app).get("/portal").text


class TestQuoteUiStatic:
    def test_sections_and_controls_present(self, page):
        for marker in ['id="quotes-section"', 'id="quote-create"',
                       'id="quote-list"', 'id="quote-detail"',
                       'id="pricing-admin"', 'id="quote-line-form"',
                       "Create quote draft", "Calculate",
                       "Create change order", "Generate mock PDF",
                       "quotesFor"]:
            assert marker in page, marker

    def test_ui_calls_tested_apis(self, page):
        for endpoint in ["/quotes", "/quotes/", "/lines", "/calculate",
                         "/reject", "/decline", "/generate-pdf",
                         "/payment-schedule", "/change-orders", "/events",
                         "/price-books", "/pricing-rules"]:
            assert endpoint in page, endpoint
        # approve/send/accept/expire/revise run through qAct(id, action).
        for action in ["'approve')", "'send')", "'accept')", "'expire')",
                       "'revise')"]:
            assert action in page, action

    def test_honesty_labels(self, page):
        for label in ["MOCKED_AND_TESTED", "SCAFFOLDED_ONLY",
                      "MOCK_PDF_PROVIDER", "mock tax engine",
                      "Change-order approval API is MISSING",
                      "not a real PDF",
                      "placeholder domain event only",
                      "no real Stripe / invoicing / payment provider"]:
            assert label in page, label

    def test_state_language_and_not_completed_wording(self, page):
        for text in ["DRAFT — editable",
                     "already sent and cannot be edited. Create a revision",
                     "accepted and immutable. Use a change order",
                     "Superseded by a newer version",
                     "accepted quote does not mean the\ncase is completed",
                     "NOT completed"]:
            assert text in page, text

    def test_no_hardcoded_quote_data(self, page):
        # Tables render only from fetch() responses; no seeded fake rows.
        assert "Loading quotes…" in page
        assert "9500" not in page            # no baked-in prices
        assert "owner@demo.finalis" not in page

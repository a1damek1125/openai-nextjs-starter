"""CORE-A1 static UI checks — the portal shows the AI Employee is not a human
user, cannot bypass policy, and that production autonomy is disabled."""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.seed import seed


@pytest.fixture()
def page():
    app = create_app(":memory:")
    seed(app.state.db)
    return TestClient(app).get("/portal").text


@pytest.fixture()
def norm(page):
    return " ".join(page.split())


def test_section_exists(page):
    assert 'id="aiemp-section"' in page
    assert 'id="aiemp-profile"' in page
    assert "Finalis AI Employee" in page
    assert "/ai-employees" in page          # loads from the real API


def test_mandated_labels_present(norm):
    for label in (
            "Finalis AI Employee is not a human user.",
            "AI Employee cannot override server-side policy.",
            "AI Employee cannot verify memory as human truth.",
            "AI Employee cannot override consent.",
            "AI Employee cannot rewrite evidence.",
            "AI Employee cannot approve its own work.",
            "Human approval is required for sensitive actions.",
            "Production autonomy is disabled.",
            "Server-side policy remains authoritative."):
        assert label in norm, label


def test_no_hardcoded_fake_employee_rows(page):
    # Profile is rendered from the API response, not baked in.
    assert "loadAIEmployeeSection" in page
    assert "esc(e.display_name)" in page
    for fake in ("ai-emp-0001", "fake_ai_employee", "superuser"):
        assert fake not in page, fake

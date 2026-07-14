"""CORE-A3 static UI checks — the Run Ledger section carries the mandated
records-not-permission / replay-not-rerun / no-execution honesty labels."""
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
    assert 'id="runs-section"' in page
    assert "Run Ledger" in page
    assert "/ai-runs" in page               # API-driven


def test_mandated_labels(norm):
    for label in (
            "Run Ledger records what happened; it does not grant permission "
            "to act.",
            "Replay verifies ledger consistency; it does not re-run the "
            "task.",
            "Run event Merkle root is an internal checkpoint; it is not "
            "external notarization.",
            "No LLM execution is implemented in this mission.",
            "No Tool Broker execution is implemented in this mission.",
            "Human Approval Gate is not implemented in this mission.",
            "Trace-ready fields are internal; external telemetry export is "
            "not implemented.",
            "Safe run view is not a separate ledger.",
            "Retention fields are advisory in this build; production "
            "retention enforcement is not implemented.",
            "Server-side policy remains authoritative."):
        assert label in norm, label


def test_no_hardcoded_fake_run_rows(page):
    assert "loadRunsSection" in page and "openRun" in page
    assert "esc(r.run_status)" in page
    for fake in ("run-0001", "fake_run_id", "demo-run"):
        assert fake not in page, fake

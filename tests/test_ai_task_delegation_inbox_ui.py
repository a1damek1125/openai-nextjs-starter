"""CORE-A2 static UI checks — the Task Delegation Inbox carries the mandated
untrusted-input / authority / not-implemented labels and is API-driven."""
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
    assert 'id="tasks-section"' in page
    assert "Task Delegation Inbox" in page
    assert "/ai-tasks" in page              # API-driven, real endpoints


def test_mandated_labels(norm):
    for label in (
            "Task creation does not execute side effects.",
            "AI Employee can draft or prepare work only within its authority "
            "boundary.",
            "Sensitive actions require human approval.",
            "Task text is treated as untrusted input.",
            "Task contract defines the accepted purpose, scope and "
            "boundaries.",
            "Input security flags are advisory; server-side authority "
            "decision remains authoritative.",
            "Server-side policy remains authoritative.",
            "Slack and Microsoft Teams intake are not implemented in this "
            "mission.",
            "Run Ledger is not implemented in this mission.",
            "Tool Broker is not implemented in this mission."):
        assert label in norm, label


def test_no_hardcoded_fake_task_rows(page):
    assert "loadTasksSection" in page and "createTask" in page
    assert "esc(t.task_type)" in page
    for fake in ("task-0001", "fake_task_id", "demo-task"):
        assert fake not in page, fake

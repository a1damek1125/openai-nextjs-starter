"""TOOL-B2 UI surface tests — the Tool Descriptor Quality Gate section renders
in the portal with its honesty labels and action hooks. Static HTML/JS only; no
tool executes anywhere (there is no execute endpoint)."""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.seed import seed


@pytest.fixture()
def client():
    app = create_app(":memory:")
    seed(app.state.db)
    return TestClient(app)


def _page(client):
    return client.get("/portal").text


class TestQualityUi:
    def test_section_present(self, client):
        page = _page(client)
        assert 'id="tool-quality-section"' in page
        assert "Tool Descriptor Quality Gate" in page

    def test_containers(self, client):
        page = _page(client)
        assert 'id="tool-quality-list"' in page
        assert 'id="tool-quality-detail"' in page

    def test_honesty_labels_present(self, client):
        page = _page(client)
        for label in (
                "Tool Description Quality Gate does not execute tools.",
                "Quality pass does not mean executable.",
                "Future Tool Broker is still required.",
                "Quality scoring is deterministic and local; it does not use "
                "LLM.",
                "Formal descriptor IR is deterministic and limited; it is not "
                "full semantic understanding.",
                "Assurance graph is local evidence, not production "
                "certification.",
                "Quality pass cannot override TOOL-B1 security blockers.",
                "Server-side registry truth is authoritative."):
            assert label in page, label

    def test_loader_and_actions_wired(self, client):
        page = _page(client)
        for hook in ("loadQualitySection", "loadQuality", "openQuality",
                     "runQualityCheck", "verifyQuality"):
            assert hook in page, hook

    def test_loader_registered(self, client):
        page = _page(client)
        assert "if (window.loadQualitySection) jobs.push(" \
            "loadQualitySection(me));" in page

    def test_no_execute_affordance(self, client):
        page = _page(client).lower()
        for bad in ("executequality", "runtool(", "invoketool",
                    "/quality/execute", "/quality/run-tool"):
            assert bad not in page, bad

    def test_actions_target_quality_endpoints(self, client):
        page = _page(client)
        assert "'/ai-tools/' + id + '/quality/check'" in page
        assert "'/ai-tools/' + id + '/quality/verify'" in page

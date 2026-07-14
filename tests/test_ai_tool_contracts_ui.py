"""TOOL-B3 UI surface tests — the Protocol Contract Proof Kernel section renders
in the portal with its honesty labels and action hooks. Static HTML/JS only; no
tool executes and no protocol runtime exists (there is no execute endpoint)."""
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


class TestContractsUi:
    def test_section_present(self, client):
        page = _page(client)
        assert 'id="tool-contracts-section"' in page
        assert "Protocol Contract Proof Kernel" in page

    def test_containers(self, client):
        page = _page(client)
        assert 'id="tool-contracts-list"' in page
        assert 'id="tool-contract-detail"' in page

    def test_honesty_labels_present(self, client):
        page = _page(client)
        for label in (
                "This is an internal contract only.",
                "This is not an MCP server or client.",
                "This contract does not execute tools.",
                "Projection does not mean runtime compliance.",
                "Broker-readiness certificate does not execute or approve "
                "tools.",
                "Future Tool Broker is still required before any tool call.",
                "No token is issued.",
                "Sampling, elicitation, resources and prompts are not "
                "implemented in this mission.",
                "Runtime capabilities are denied in TOOL-B3.",
                "Server-side registry truth is authoritative."):
            assert label in page, label

    def test_loader_and_actions_wired(self, client):
        page = _page(client)
        for hook in ("loadContractsSection", "loadContracts", "openContract",
                     "verifyContract", "projectContract"):
            assert hook in page, hook

    def test_loader_registered(self, client):
        page = _page(client)
        assert "if (window.loadContractsSection) jobs.push(" \
            "loadContractsSection(me));" in page

    def test_no_runtime_affordance(self, client):
        page = _page(client).lower()
        for bad in ("executetool", "mcpserver(", "startmcp", "servesampling",
                    "serveresource", "/contracts/execute", "issuetoken"):
            assert bad not in page, bad

    def test_actions_target_contract_endpoints(self, client):
        page = _page(client)
        assert "'/contracts/' + cid + '/verify'" in page
        assert "'/contracts/' + cid + '/project'" in page

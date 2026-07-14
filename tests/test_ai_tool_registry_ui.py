"""TOOL-B1 UI surface tests — the Zero-Trust Tool Capability Registry section
is served in the portal page with its honesty labels, and the client-side
loader + action hooks are wired. These assert the rendered HTML/JS only; no
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


class TestToolRegistryUiSection:
    def test_section_present(self, client):
        page = _page(client)
        assert 'id="tools-section"' in page
        assert "Zero-Trust Tool Capability Registry" in page

    def test_section_lists_and_detail_containers(self, client):
        page = _page(client)
        assert 'id="tools-list"' in page
        assert 'id="tool-detail"' in page

    def test_honesty_labels_rendered(self, client):
        page = _page(client)
        for label in (
                "This is a tool capability registry, not a Tool Broker.",
                "Registering a tool descriptor does not execute the tool.",
                "There is no execute endpoint and no dry-run execution in "
                "this mission.",
                "The registry sends no customer message, moves no payment "
                "and writes no CRM.",
                "The registry rewrites no evidence and exports no document.",
                "Admission means a FUTURE broker may consider the tool; "
                "nothing runs it here.",
                "Admission is fail-closed: any hard-fail signal blocks "
                "admission.",
                "Consent requirements declared as non-overridable can never "
                "be downgraded.",
                "This is not production autonomous tool execution."):
            assert label in page, label

    def test_no_execute_or_dry_run_affordance_in_ui(self, client):
        page = _page(client).lower()
        # The UI must never offer an execute / run / invoke / dry-run action.
        for affordance in ("executetool", "dryruntool", "runtool",
                           "invoketool", "calltool", "/ai-tools/execute",
                           "/ai-tools/' + id + '/execute",
                           "/ai-tools/' + id + '/run",
                           "/ai-tools/' + id + '/invoke"):
            assert affordance not in page, affordance

    def test_loader_and_actions_wired(self, client):
        page = _page(client)
        assert "loadToolsSection" in page
        assert "loadTools" in page
        assert "openTool" in page
        assert "admitTool" in page
        assert "verifyTool" in page
        assert "driftTool" in page

    def test_loader_registered_in_loadsections(self, client):
        page = _page(client)
        assert "if (window.loadToolsSection) jobs.push(loadToolsSection(me));" \
            in page

    def test_actions_target_governance_endpoints(self, client):
        page = _page(client)
        assert "'/ai-tools/' + id + '/admit'" in page
        assert "'/ai-tools/' + id + '/verify'" in page
        assert "'/ai-tools/' + id + '/drift-check'" in page

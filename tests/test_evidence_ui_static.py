"""V-C static UI checks — the Evidence Command Center is served, calls
the tested V-B APIs, and carries the mandated honesty/safety labels.
Browser behaviour is V-D."""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.seed import seed


@pytest.fixture()
def page():
    app = create_app(":memory:")
    seed(app.state.db)
    return TestClient(app).get("/portal").text


class TestEvidenceUiStatic:
    def test_1_2_sections_and_panels_exist(self, page):
        for marker in ['id="evidence-section"', 'id="ev-dashboard"',
                       'id="ev-upload-panel"', 'id="ev-list"',
                       'id="ev-detail"', 'id="ev-matrix"',
                       'id="ev-contract"', "evidenceFor",
                       "Decision Completeness Matrix",
                       "Causal Action Guard",
                       "Chain of custody", "Dual-View",
                       "Hard Blocker Proof",
                       "Evidence Readiness Index",
                       "Decision replay"]:
            assert marker in page, marker

    def test_3_9_ui_calls_tested_apis(self, page):
        for endpoint in ["/evidence/upload", "/evidence/upload-sessions",
                         "'/evidence'", "/evidence/", "/chain",
                         "/human-view", "/agent-view",
                         "/ai-access-decision", "/verify-integrity",
                         "/review", "/legal-hold", "/delete-decision",
                         "/human-verify-symbol",
                         "/evidence/requirement-check",
                         "/evidence/decision-contract/validate"]:
            assert endpoint in page, endpoint

    def test_10_14_honesty_and_safety_labels(self, page):
        for label in ["Documents provide facts, never commands",
                      "No public raw download",
                      "Agent view is intentionally different from",
                      "hard blockers override scores",
                      "NON-AUTHORITATIVE",
                      "no native\nWORM/Object Lock",
                      "not\nproduction antivirus",
                      "NOT RUN",             # OCR
                      "not connected",       # Docling/.../S3
                      "SCAFFOLDED_ONLY",
                      "NOT production-ready",
                      "Quarantine-first",
                      "original filename is metadata only",
                      "Content-Type is not trusted",
                      "never an operational command"]:
            assert label in page, label

    def test_21_no_hardcoded_fake_evidence(self, page):
        assert "Loading evidence…" in page
        # No baked-in sha256 or evidence rows.
        import re
        assert not re.search(r'\b[0-9a-f]{64}\b', page)
        assert "owner@demo.finalis" not in page

    def test_untrusted_content_is_escaped_not_injected(self, page):
        # Content-bearing fields render through the esc() helper —
        # untrusted strings never hit the trusted DOM as raw HTML.
        assert "const esc =" in page
        for escaped_use in ["esc(av.safe_derivative_text)",
                            "esc(hv.untrusted_content_warning)",
                            "esc(r.original_filename)",
                            "data.reasons.map(esc)"]:
            assert escaped_use in page, escaped_use

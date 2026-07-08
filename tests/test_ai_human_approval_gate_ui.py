"""CORE-A4.1 — Human Approval Gate read-only UI. PART 1 renders the queue and
detail with honesty labels; approve/reject controls are present but disabled
and explicitly labeled PART 2 (CORE-A4.2)."""
from finalis.portal.ui import PORTAL_PAGE


class TestApprovalsUi:
    def test_section_present(self):
        assert 'id="approvals-section"' in PORTAL_PAGE
        assert "Human Approval Gate" in PORTAL_PAGE

    def test_loader_registered(self):
        assert "loadApprovalsSection" in PORTAL_PAGE
        assert "if (window.loadApprovalsSection)" in PORTAL_PAGE

    def test_honesty_labels_rendered_in_section(self):
        # Section prose is line-wrapped in the source; assert on fragments
        # that survive wrapping.
        assert "does not approve or execute" in PORTAL_PAGE
        assert "decisions and grants are implemented in CORE-A4.2." \
            in PORTAL_PAGE
        assert "Server-side policy remains\nauthoritative." in PORTAL_PAGE \
            or "Server-side policy remains authoritative" in PORTAL_PAGE

    def test_decision_buttons_disabled_and_labeled_part2(self):
        assert "Approve (CORE-A4.2)" in PORTAL_PAGE
        assert "Reject (CORE-A4.2)" in PORTAL_PAGE
        assert "Approve/reject buttons arrive in CORE-A4.2 (PART 2)." \
            in PORTAL_PAGE

    def test_verify_control_present(self):
        assert "verifyApproval" in PORTAL_PAGE

    def test_reads_only_from_approval_endpoints(self):
        assert "get('/ai-approvals')" in PORTAL_PAGE
        assert "/ai-approvals/' + id" in PORTAL_PAGE

    def test_forbidden_unlocks_surfaced(self):
        assert "An approval can never unlock" in PORTAL_PAGE

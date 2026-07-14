"""CORE-A4.2 — Human Approval Gate portal UI. PART 2 exposes functional
approve/reject/request-changes/revoke controls, acknowledgements, the viewed
package hash, grant summary and consume-check, all under no-execution labels.
UI labels are convenience only; the server re-checks every decision."""
from finalis.portal.ui import PORTAL_PAGE


REQUIRED_LABELS = [
    "Approval does not execute the action.",
    "Consume-check validates approval scope only; it does not execute the "
    "action.",
    "Approval does not override consent, evidence, RBAC or proof failures.",
    "AI Employee cannot approve its own work.",
    "Only an authorized human approver can approve.",
    "Approval is scoped to this run, task, action and hash state.",
    "Approval grant must be revalidated before future use.",
    "This is not OAuth, GNAP, or an external bearer token.",
    "Server-side policy remains authoritative.",
]


class TestApprovalsUi:
    def test_section_present(self):
        assert 'id="approvals-section"' in PORTAL_PAGE
        assert "Human Approval Gate" in PORTAL_PAGE

    def test_loader_registered(self):
        assert "loadApprovalsSection" in PORTAL_PAGE
        assert "if (window.loadApprovalsSection)" in PORTAL_PAGE

    def test_all_required_labels_present(self):
        for lbl in REQUIRED_LABELS:
            assert lbl in PORTAL_PAGE, f"missing label: {lbl}"

    def test_decision_controls_present(self):
        assert "decideApproval" in PORTAL_PAGE
        for kind in ("approve", "reject", "changes", "revoke"):
            assert f"'{kind}')" in PORTAL_PAGE
        assert "'/' + path" in PORTAL_PAGE           # posts to the decision api

    def test_acknowledgement_and_challenge_inputs(self):
        assert 'class="ack"' in PORTAL_PAGE
        assert "approval-challenge" in PORTAL_PAGE
        assert "approval-viewed-hash" in PORTAL_PAGE

    def test_consume_check_control(self):
        assert "consumeCheck" in PORTAL_PAGE
        assert "/consume-check" in PORTAL_PAGE
        assert "/grant" in PORTAL_PAGE

    def test_grant_summary_and_verify(self):
        assert "Approval grant" in PORTAL_PAGE
        assert "verifyApproval" in PORTAL_PAGE

    def test_labels_cannot_unlock_reads_from_server(self):
        # The client only ever POSTs to server endpoints; it never fabricates
        # an approval locally.
        assert "get('/ai-approvals')" in PORTAL_PAGE

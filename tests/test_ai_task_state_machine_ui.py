"""CORE-A5 — Task Lifecycle portal UI (static). The lifecycle section renders
state, allowed transitions, transition history, completion status/blockers and
verify/replay/reconcile controls under no-execution labels. UI labels are
convenience only; the server re-checks every transition."""
from finalis.portal.ui import PORTAL_PAGE


REQUIRED_LABELS = [
    "State transition does not execute the action.",
    "Transition dry-run does not mutate state.",
    "Transition replay reconstructs lifecycle state; it does not re-run the "
    "task.",
    "Transition reconciliation compares stored and replayed state; it does not "
    "auto-heal silently.",
    "Completion Loop checks readiness only; it does not execute the task.",
    "Tool Broker is not implemented in this mission.",
    "LLM runtime is not implemented in this mission.",
    "Server-side task state is authoritative.",
]


class TestLifecycleUi:
    def test_section_present(self):
        assert 'id="lifecycle-section"' in PORTAL_PAGE
        assert "Task Lifecycle Kernel" in PORTAL_PAGE

    def test_loader_registered(self):
        assert "loadLifecycleSection" in PORTAL_PAGE
        assert "if (window.loadLifecycleSection)" in PORTAL_PAGE

    def test_all_required_labels_present(self):
        for lbl in REQUIRED_LABELS:
            assert lbl in PORTAL_PAGE, f"missing label: {lbl}"

    def test_controls_present(self):
        for fn in ["applyTransition", "verifyLifecycle", "replayLifecycle",
                   "reconcileLifecycle", "openLifecycle"]:
            assert fn in PORTAL_PAGE

    def test_reads_from_server_endpoints(self):
        assert "/ai-tasks/state-machine/verify" in PORTAL_PAGE
        assert "'/ai-tasks/' + id + '/state'" in PORTAL_PAGE
        assert "/transitions/reconcile" in PORTAL_PAGE

    def test_shows_completion_and_graph_status(self):
        assert "Completion —" in PORTAL_PAGE
        assert "Transition graph:" in PORTAL_PAGE

"""CORE-A5 — deterministic transition matrix (pure). Allowed edges resolve;
denied edges and terminal/expired origins are refused fail-closed."""
import pytest

from finalis.ai_employee import lifecycle as L


def _ctx(frm, event, **over):
    ctx = dict(tenant_match=True, actor_authorized=True, actor_type="human",
               actor_role="owner", from_state=frm, event=event, tenant_id="t",
               task_id="k", contract_hash_match=True, envelope_hash_match=True)
    ctx.update(over)
    return ctx


def _status(frm, event, **over):
    return L.decide_transition(_ctx(frm, event, **over))["transition_status"]


ALLOWED = [
    ("INTAKE_RECEIVED", "TASK_NORMALIZED"),
    ("NORMALIZED", "TASK_CONTRACTED"),
    ("CONTRACTED", "AUTHORITY_CHECK_COMPLETED"),
    ("AUTHORITY_CHECKED", "TASK_ACCEPTED"),
    ("ACCEPTED", "APPROVAL_REQUIRED_RECORDED"),
    ("APPROVAL_REQUIRED", "APPROVAL_REQUEST_LINKED"),
    ("APPROVED_READY", "TASK_MARKED_RUN_READY"),
    ("RUN_READY", "TASK_MARKED_RUNNING_LEDGER_ONLY"),
    ("RUNNING_LEDGER_ONLY", "DRAFT_CREATED"),
    ("DRAFT_READY", "TASK_MARKED_REVIEW_READY"),
    ("REVIEW_READY", "COMPLETION_CHECK_REQUESTED"),
    ("COMPLETION_BLOCKED", "TASK_MARKED_REVIEW_READY"),
]

DENIED_TERMINAL = [
    ("CANCELLED", "TASK_MARKED_RUN_READY"),
    ("FAILED", "TASK_MARKED_RUN_READY"),
    ("BLOCKED", "TASK_ACCEPTED"),
    ("EXPIRED", "TASK_ACCEPTED"),
    ("COMPLETED_NO_SIDE_EFFECTS", "TASK_MARKED_RUN_READY"),
    ("NOT_IMPLEMENTED", "TASK_ACCEPTED"),
]


class TestMatrix:
    @pytest.mark.parametrize("frm,event", ALLOWED)
    def test_allowed_edges(self, frm, event):
        assert _status(frm, event) == "ALLOWED"

    @pytest.mark.parametrize("frm,event", DENIED_TERMINAL)
    def test_terminal_origins_denied(self, frm, event):
        # from a terminal state every event is refused
        assert _status(frm, event) in ("DENIED", "BLOCKED")

    def test_authority_checked_to_blocked_on_hard_fail(self):
        # AUTHORITY_CHECKED -> BLOCKED is a valid edge; when authority is
        # blocked, only the block edge is meaningful.
        assert _status("AUTHORITY_CHECKED", "TASK_BLOCKED") == "ALLOWED"

    def test_approval_pending_needs_valid_grant(self):
        assert _status("APPROVAL_PENDING", "APPROVAL_GRANT_VALIDATED",
                       approval_grant_validation_status="NONE") \
            == "REQUIRES_APPROVAL"
        assert _status("APPROVAL_PENDING", "APPROVAL_GRANT_VALIDATED",
                       approval_grant_validation_status="VALID") == "ALLOWED"

    def test_completion_requires_readiness(self):
        assert _status("COMPLETION_CHECK_REQUIRED",
                       "TASK_COMPLETED_NO_SIDE_EFFECTS",
                       completion_ready=False) == "COMPLETION_BLOCKED"
        assert _status("COMPLETION_CHECK_REQUIRED",
                       "TASK_COMPLETED_NO_SIDE_EFFECTS",
                       completion_ready=True) == "ALLOWED"

    def test_reconciliation_required_cannot_go_run_ready(self):
        assert L.find_edge("RECONCILIATION_REQUIRED",
                           "TASK_MARKED_RUN_READY") is None
        assert _status("RECONCILIATION_REQUIRED", "TASK_MARKED_RUN_READY") \
            == "DENIED"

    def test_reconciliation_required_can_go_review(self):
        assert _status("RECONCILIATION_REQUIRED", "TASK_MARKED_REVIEW_READY") \
            == "ALLOWED"

    def test_unknown_edge_denied(self):
        assert _status("ACCEPTED", "TASK_COMPLETED_NO_SIDE_EFFECTS") == "DENIED"

    def test_expired_task_denied(self):
        assert _status("ACCEPTED", "DRAFT_CREATED", expired=True) == "EXPIRED"

    def test_universal_cancel_from_non_terminal(self):
        assert _status("ACCEPTED", "TASK_CANCELLED") == "ALLOWED"
        assert _status("RUN_READY", "TASK_EXPIRED") == "ALLOWED"

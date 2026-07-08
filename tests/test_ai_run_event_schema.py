"""CORE-A3 — event schema registry + lifecycle transition validator."""
import pytest

from finalis.ai_employee import run_ledger as R


def test_known_event_types_registered():
    for t in ("RUN_CREATED", "RUN_STARTED", "AUTHORITY_SNAPSHOT_RECORDED",
              "DRAFT_OUTPUT_PLACEHOLDER_CREATED", "RUN_CANCELLED",
              "RUN_COMPLETED_NO_SIDE_EFFECTS"):
        assert t in R.EVENT_SCHEMA
        assert R.EVENT_SCHEMA[t]["schema_version"] == R.EVENT_SCHEMA_VERSION


def test_unknown_event_type_absent():
    assert "TOTALLY_FAKE_EVENT" not in R.EVENT_SCHEMA


def test_future_placeholder_events_flagged():
    for t in ("APPROVAL_GATE_NOT_IMPLEMENTED_RECORDED",
              "TOOL_BROKER_NOT_IMPLEMENTED_RECORDED", "TOOL_CALL_PROPOSED"):
        assert R.EVENT_SCHEMA[t]["future_placeholder"] is True


def test_terminal_events_marked():
    for t in ("RUN_BLOCKED", "RUN_FAILED", "RUN_CANCELLED",
              "RUN_COMPLETED_NO_SIDE_EFFECTS"):
        assert R.EVENT_SCHEMA[t]["terminal"] is True


def test_untrusted_and_redaction_flags():
    assert R.EVENT_SCHEMA["TASK_ENVELOPE_SNAPSHOT_RECORDED"]["untrusted_ok"]
    assert R.EVENT_SCHEMA["TASK_ENVELOPE_SNAPSHOT_RECORDED"][
        "requires_redaction"]


@pytest.mark.parametrize("src,dst,ok", [
    ("CREATED", "STARTED", True),
    ("CREATED", "CANCELLED", True),
    ("STARTED", "PLANNING", True),
    ("PLANNING", "DRAFT_READY", True),
    ("PLANNING", "APPROVAL_REQUIRED", True),
    ("APPROVAL_REQUIRED", "PAUSED", True),
    ("DRAFT_READY", "COMPLETED_NO_SIDE_EFFECTS", True),
    # forbidden restarts
    ("BLOCKED", "STARTED", False),
    ("FAILED", "STARTED", False),
    ("CANCELLED", "STARTED", False),
    ("COMPLETED_NO_SIDE_EFFECTS", "STARTED", False),
    ("STARTED", "COMPLETED_NO_SIDE_EFFECTS", False),
])
def test_transition_validator(src, dst, ok):
    assert R.valid_transition(src, dst) is ok


def test_terminal_states_have_no_exits():
    for t in R.TERMINAL_STATUSES:
        assert R.TRANSITIONS[t] == set()

"""TOOL-B9.1 v4: recovery state machine (section 2) — the recovery lifecycle is
a fail-closed state machine. Every state in lr.RECOVERY_STATES is known; only the
transitions in lr.ALLOWED_TRANSITIONS are permitted and anything else fails
closed. TAMPERED can NEVER become CLEAN (only -> QUARANTINED); QUARANTINED, STUCK,
RECOVERY_FAILED and every ABORTED_* state are terminal with no outgoing edges.
Non-finalizing states (QUARANTINED/STUCK/TAMPERED/RECOVERY_FAILED/
ROLLBACK_NOT_EXECUTABLE_FOR_TARGET/ABORTED_*) never finalize a commit.
"""
from finalis.ai_employee import tool_local_recovery as lr
from tests import _b91_kernel as k


_ABORTED_STATES = [
    "ABORT_REQUESTED", "ABORTED_PRE_COMMIT", "ABORTED_DURING_VALIDATION",
    "ABORTED_DURING_SHADOW_STATE", "ABORTED_BEFORE_FINALIZATION",
    "ABORTED_AFTER_LOCAL_COMMIT",
]


def _non_finalizing(o):
    """Every fail-closed / blocked outcome: recovery is NOT applied and no
    external effect is ever produced."""
    assert o["recovery_applied"] is False
    assert o["produced_external_effect"] is False
    assert o["provider_called"] is False
    assert o["outbox_released"] is False


# --- kernel layer ----------------------------------------------------------
def test_state_machine_all_states_known():
    assert len(lr.RECOVERY_STATES) == 19
    for st in ("CLEAN", "RECOVERY_REQUIRED", "RECOVERY_PLANNED", "RECOVERING",
               "RECOVERED", "ROLLBACK_APPLIED_LOCAL",
               "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET", "QUARANTINED", "STUCK",
               "TAMPERED", "RECOVERY_FAILED"):
        assert st in lr.RECOVERY_STATES
    for st in _ABORTED_STATES:
        assert st in lr.RECOVERY_STATES


def test_state_machine_valid_transitions_allowed():
    valid = [
        ("CLEAN", "RECOVERY_REQUIRED"),
        ("RECOVERY_REQUIRED", "RECOVERY_PLANNED"),
        ("RECOVERY_PLANNED", "RECOVERING"),
        ("RECOVERING", "RECOVERED"),
        ("ROLLBACK_REQUESTED", "ROLLBACK_APPLIED_LOCAL"),
        ("ABORT_REQUESTED", "ABORTED_PRE_COMMIT"),
    ]
    for src, dst in valid:
        assert lr.is_transition_allowed(src, dst) is True, (src, dst)


def test_state_machine_invalid_transitions_fail_closed():
    invalid = [
        ("TAMPERED", "CLEAN"),
        ("CLEAN", "RECOVERED"),
        ("RECOVERING", "CLEAN"),
    ]
    for src, dst in invalid:
        assert lr.is_transition_allowed(src, dst) is False, (src, dst)


def test_state_machine_quarantined_is_terminal():
    for dst in lr.RECOVERY_STATES:
        assert lr.is_transition_allowed("QUARANTINED", dst) is False, dst


def test_state_machine_stuck_is_terminal():
    for dst in lr.RECOVERY_STATES:
        assert lr.is_transition_allowed("STUCK", dst) is False, dst


def test_state_machine_recovery_failed_is_terminal():
    for dst in lr.RECOVERY_STATES:
        assert lr.is_transition_allowed("RECOVERY_FAILED", dst) is False, dst


def test_state_machine_aborted_states_are_terminal():
    for src in _ABORTED_STATES:
        if src == "ABORT_REQUESTED":
            continue  # ABORT_REQUESTED is the only aborted src with edges
        for dst in lr.RECOVERY_STATES:
            assert lr.is_transition_allowed(src, dst) is False, (src, dst)


def test_state_machine_tampered_only_to_quarantined():
    assert lr.is_transition_allowed("TAMPERED", "QUARANTINED") is True
    for dst in lr.RECOVERY_STATES:
        if dst == "QUARANTINED":
            continue
        assert lr.is_transition_allowed("TAMPERED", dst) is False, dst


def test_state_machine_unknown_dst_or_src_false():
    assert lr.is_transition_allowed("CLEAN", "NOT_A_STATE") is False
    assert lr.is_transition_allowed("NOT_A_STATE", "CLEAN") is False


# --- kernel layer: outcome-driven state -> decision + non-finalizing --------
def test_state_machine_recovered_finalizes():
    o = k.prepare(desired_recovery_action="RECOVER")
    assert o["final_recovery_state"] == "RECOVERED"
    assert o["recovery_decision_status"] == "B91_DECISION_RECOVERED"
    assert o["recovery_applied"] is True


def test_state_machine_quarantined_non_finalizing():
    o = k.prepare(desired_recovery_action="RECOVER",
                  recovery_authority_basis={"source": "DOCUMENT"})
    assert o["final_recovery_state"] == "QUARANTINED"
    assert o["recovery_decision_status"] == "B91_DECISION_QUARANTINE"
    _non_finalizing(o)


def test_state_machine_stuck_non_finalizing():
    o = k.prepare(desired_recovery_action="DETECT_STUCK", lock_age_seconds=9999)
    assert o["final_recovery_state"] == "STUCK"
    assert o["dominant_signal"] == "STUCK_LOCK_HELD_TOO_LONG"
    assert o["recovery_decision_status"] == "B91_DECISION_STUCK"
    _non_finalizing(o)


def test_state_machine_tampered_non_finalizing():
    o = k.prepare(desired_recovery_action="RECOVER", poe_tamper=True)
    assert o["final_recovery_state"] == "TAMPERED"
    assert o["dominant_signal"] == "PROOF_OF_EXECUTION_TAMPERED"
    assert o["recovery_decision_status"] == "B91_DECISION_TAMPERED"
    _non_finalizing(o)


def test_state_machine_recovery_failed_non_finalizing():
    o = k.prepare(desired_recovery_action="RECOVER", recovery_authority_basis={})
    assert o["final_recovery_state"] == "RECOVERY_FAILED"
    assert o["dominant_signal"] == "RECOVERY_AUTHORITY_MISSING"
    assert o["recovery_decision_status"] == "B91_DECISION_RECOVERY_FAILED"
    _non_finalizing(o)


def test_state_machine_aborted_non_finalizing():
    o = k.prepare(desired_recovery_action="ABORT")
    assert o["final_recovery_state"] == "ABORTED_PRE_COMMIT"
    assert o["dominant_signal"] == "USER_ABORT_REQUESTED"
    assert o["recovery_decision_status"] == "B91_DECISION_ABORTED"
    _non_finalizing(o)


def test_state_machine_rollback_not_executable_non_finalizing():
    o = k.prepare(desired_recovery_action="ROLLBACK_LOCAL",
                  rollback_equivalence_fail=True)
    assert o["final_recovery_state"] == "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET"
    assert o["recovery_decision_status"] == "B91_DECISION_ROLLBACK_NOT_EXECUTABLE"
    _non_finalizing(o)


# --- API layer -------------------------------------------------------------
def test_api_state_machine_quarantine_action(gate):
    rid, o = gate.prepared_recovery(action="quarantine")
    assert o["final_recovery_state"] == "QUARANTINED"
    assert o["recovery_decision_status"] == "B91_DECISION_QUARANTINE"
    assert o["recovery_applied"] is False


def test_api_state_machine_stuck_action(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="stuck", lock_age_seconds=9999).json()
    assert o["final_recovery_state"] == "STUCK"
    assert o["recovery_decision_status"] == "B91_DECISION_STUCK"
    assert o["recovery_applied"] is False


def test_api_state_machine_abort_action(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="abort").json()
    assert o["final_recovery_state"] == "ABORTED_PRE_COMMIT"
    assert o["recovery_decision_status"] == "B91_DECISION_ABORTED"
    assert o["recovery_applied"] is False
    assert o["produced_external_effect"] is False

"""TOOL-B9.1 v4: recovery safety invariants — safety monotonicity (section 10)
and double-entry state reconciliation (section 9).

Recovery may NEVER increase authority, autonomy, write scope or externality, and
may never make the inert outbox releasable (safety monotonicity). Local state is
double-entry reconciled: the ledger, event-stream, certificate and replay-context
views must agree. Any monotonicity violation quarantines; any reconciliation
mismatch fails closed. No external effect is ever produced, even on a block.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from tests import _b91_kernel as k


_MONO_CHECKS = ("authority_not_increased", "autonomy_not_increased",
                "write_scope_not_broadened", "externality_not_increased",
                "outbox_not_releasable")


def _mono_violation(check_key, **over):
    """Prepare a RECOVER outcome that violates one monotonicity check."""
    o = k.prepare(desired_recovery_action="RECOVER", **over)
    assert o["final_recovery_state"] == "QUARANTINED"
    assert o["quarantine_required"] is True
    assert o["recovery_applied"] is False
    m = o["safety_monotonicity"]
    assert m["monotonicity_passed"] is False
    assert m["monotonicity_status"] == "VIOLATED"
    assert m["checks"][check_key] is False
    # Actual-effect fields ALWAYS stay False, even on a blocked recovery.
    assert o["produced_external_effect"] is False
    assert o["provider_called"] is False
    assert o["outbox_released"] is False
    return o


# --- kernel layer: safety monotonicity (section 10) ------------------------
def test_si_clean_monotonicity_passed():
    m = k.clean_outcome()["safety_monotonicity"]
    assert m["monotonicity_passed"] is True
    assert m["monotonicity_status"] == "MONOTONIC"
    for chk in _MONO_CHECKS:
        assert m["checks"][chk] is True


def test_si_monotonicity_authority_increase_quarantined():
    o = _mono_violation("authority_not_increased",
                        old_authority_level=1, new_authority_level=5)
    assert o["dominant_signal"] == "RECOVERY_SAFETY_MONOTONICITY_FAILED"


def test_si_monotonicity_autonomy_increase_quarantined():
    o = _mono_violation("autonomy_not_increased",
                        old_autonomy_level=1, new_autonomy_level=5)
    assert o["dominant_signal"] == "RECOVERY_SAFETY_MONOTONICITY_FAILED"


def test_si_monotonicity_write_scope_broadened_quarantined():
    o = _mono_violation("write_scope_not_broadened",
                        old_write_scope=["status"],
                        new_write_scope=["status", "secret"])
    assert o["dominant_signal"] == "RECOVERY_SAFETY_MONOTONICITY_FAILED"


def test_si_monotonicity_externality_increase_quarantined():
    o = _mono_violation("externality_not_increased",
                        old_externality_level=0, new_externality_level=2)
    assert o["dominant_signal"] == "RECOVERY_SAFETY_MONOTONICITY_FAILED"


def test_si_monotonicity_outbox_releasable_quarantined():
    # outbox_not_releasable is the fifth monotonicity check; a release attempt
    # dominates with its own signal but still fails the check and quarantines.
    o = _mono_violation("outbox_not_releasable", outbox_becomes_releasable=True)
    assert o["dominant_signal"] == "RECOVERY_OUTBOX_RELEASE_ATTEMPT"


def test_si_monotonicity_hash_recompute():
    m = k.clean_outcome()["safety_monotonicity"]
    assert _core_hash(m, "monotonicity_hash", "signal") == m["monotonicity_hash"]


# --- kernel layer: double-entry reconciliation (section 9) -----------------
def test_si_clean_reconciliation_passed():
    r = k.clean_outcome()["double_entry_reconciliation"]
    assert r["reconciliation_passed"] is True
    assert r["reconciliation_status"] == "RECONCILED"
    assert r["ledger_view_hash"] == r["event_stream_view_hash"] \
        == r["certificate_view_hash"] == r["replay_context_view_hash"]


def _reconcile_mismatch(mismatch, expected_signal):
    o = k.prepare(desired_recovery_action="RECOVER", reconcile_mismatch=mismatch)
    assert o["final_recovery_state"] == "RECOVERY_FAILED"
    assert o["dominant_signal"] == expected_signal
    assert o["recovery_applied"] is False
    r = o["double_entry_reconciliation"]
    assert r["reconciliation_passed"] is False
    assert r["reconciliation_status"] == "MISMATCH"
    # Even on a reconciliation failure, no external effect is produced.
    assert o["produced_external_effect"] is False
    assert o["outbox_released"] is False
    return r


def test_si_reconcile_ledger_event_mismatch():
    r = _reconcile_mismatch("ledger_event", "LEDGER_EVENT_STREAM_MISMATCH")
    assert r["ledger_view_hash"] != r["event_stream_view_hash"]


def test_si_reconcile_event_certificate_mismatch():
    r = _reconcile_mismatch("event_certificate", "EVENT_CERTIFICATE_MISMATCH")
    assert r["event_stream_view_hash"] != r["certificate_view_hash"]


def test_si_reconcile_certificate_replay_mismatch():
    r = _reconcile_mismatch("certificate_replay",
                            "CERTIFICATE_REPLAY_CONTEXT_MISMATCH")
    assert r["certificate_view_hash"] != r["replay_context_view_hash"]


def test_si_reconciliation_hash_recompute():
    r = k.clean_outcome()["double_entry_reconciliation"]
    assert _core_hash(r, "reconciliation_hash", "signal") \
        == r["reconciliation_hash"]


def test_si_clean_outcome_both_invariants_hold():
    o = k.clean_outcome()
    assert o["safety_monotonicity_passed"] is True
    assert o["double_entry_reconciliation_passed"] is True


# --- API layer -------------------------------------------------------------
def test_si_api_clean_run_invariants(gate):
    rid, o = gate.prepared_recovery(action="run")
    assert o["safety_monotonicity_passed"] is True
    assert o["double_entry_reconciliation_passed"] is True
    assert o["no_external_effect"] is True


def test_si_api_monotonicity_endpoint(gate):
    rid, _ = gate.prepared_recovery(action="run")
    m = gate.rc(rid, "monotonicity").json()["safety_monotonicity"]
    assert m["monotonicity_passed"] is True
    assert m["monotonicity_status"] == "MONOTONIC"
    for chk in _MONO_CHECKS:
        assert m["checks"][chk] is True


def test_si_api_reconciliation_endpoint(gate):
    rid, _ = gate.prepared_recovery(action="run")
    r = gate.rc(rid, "reconciliation").json()["double_entry_reconciliation"]
    assert r["reconciliation_passed"] is True
    assert r["ledger_view_hash"] == r["replay_context_view_hash"]


def test_si_api_monotonicity_violation_quarantined(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="run",
                     old_authority_level=1, new_authority_level=5).json()
    assert o["final_recovery_state"] == "QUARANTINED"
    assert o["dominant_signal"] == "RECOVERY_SAFETY_MONOTONICITY_FAILED"
    assert o["recovery_applied"] is False


def test_si_api_reconciliation_mismatch_fails_closed(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="run",
                     reconcile_mismatch="ledger_event").json()
    assert o["final_recovery_state"] == "RECOVERY_FAILED"
    assert o["dominant_signal"] == "LEDGER_EVENT_STREAM_MISMATCH"
    assert o["produced_external_effect"] is False

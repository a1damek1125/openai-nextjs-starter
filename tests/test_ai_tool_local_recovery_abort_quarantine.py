"""TOOL-B9.1 v4: emergency abort controller (section 13) + transaction
quarantine (section 17).

Emergency abort dominates every commit path but never deletes audit history,
never releases the inert outbox and never calls a provider. Quarantine makes a
transaction read-only and blocks commit finalization while PRESERVING all
evidence / audit / proof artifacts — it deletes nothing and mutates nothing
external. All EVIDENCE, never authority; no external effect on any path.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from tests import _b91_kernel as k


def _abort(**over):
    o = k.prepare(desired_recovery_action="ABORT", **over)
    assert o["recovery_applied"] is False
    assert o["quarantine_required"] is False
    # No external effect ever, even on an abort.
    assert o["outbox_released"] is False
    assert o["produced_external_effect"] is False
    assert o["provider_called"] is False
    return o


# --- kernel layer ----------------------------------------------------------
def test_abq_abort_clean_pre_commit():
    o = _abort()
    assert o["final_recovery_state"] == "ABORTED_PRE_COMMIT"
    assert o["dominant_signal"] == "USER_ABORT_REQUESTED"


def test_abq_tenant_abort_requested():
    o = _abort(tenant_abort=True)
    assert o["final_recovery_state"] == "ABORTED_PRE_COMMIT"
    assert o["dominant_signal"] == "TENANT_ABORT_REQUESTED"


def test_abq_global_abort_requested():
    o = _abort(global_abort=True)
    assert o["final_recovery_state"] == "ABORTED_PRE_COMMIT"
    assert o["dominant_signal"] == "GLOBAL_ABORT_REQUESTED"


def test_abq_kill_switch_dominates_recover():
    # A runtime kill switch aborts even a RECOVER action pre-commit.
    o = k.prepare(desired_recovery_action="RECOVER", kill_switch=True)
    assert o["final_recovery_state"] == "ABORTED_PRE_COMMIT"
    assert o["dominant_signal"] == "RUNTIME_KILL_SWITCH_ACTIVE"
    assert o["recovery_applied"] is False
    assert o["outbox_released"] is False


def test_abq_abort_stage_validation():
    o = _abort(abort_stage="validation")
    assert o["final_recovery_state"] == "ABORTED_DURING_VALIDATION"
    assert o["dominant_signal"] == "USER_ABORT_REQUESTED"


def test_abq_abort_stage_shadow():
    o = _abort(abort_stage="shadow")
    assert o["final_recovery_state"] == "ABORTED_DURING_SHADOW_STATE"
    assert o["dominant_signal"] == "USER_ABORT_REQUESTED"


def test_abq_abort_stage_pre_finalization():
    o = _abort(abort_stage="pre_finalization")
    assert o["final_recovery_state"] == "ABORTED_BEFORE_FINALIZATION"


def test_abq_abort_stage_post_commit():
    o = _abort(abort_stage="post_commit")
    assert o["final_recovery_state"] == "ABORTED_AFTER_LOCAL_COMMIT"


def test_abq_abort_controller_is_safe_when_active():
    ac = _abort()["abort_controller"]
    assert ac["abort_active"] is True
    assert ac["dominates_commit"] is True
    assert ac["blocks_new_local_commits"] is True
    assert ac["deletes_audit_history"] is False
    assert ac["releases_outbox"] is False
    assert ac["calls_providers"] is False


def test_abq_abort_never_deletes_audit_or_releases_outbox():
    o = _abort(abort_stage="post_commit")
    ac = o["abort_controller"]
    assert ac["deletes_audit_history"] is False
    assert ac["releases_outbox"] is False
    # And the top-level outcome mirrors: the inert outbox stays inert.
    assert o["outbox_released"] is False


def test_abq_quarantine_on_poe_tamper_preserves_everything():
    o = k.prepare(desired_recovery_action="RECOVER", poe_tamper=True)
    assert o["final_recovery_state"] == "TAMPERED"
    assert o["dominant_signal"] == "PROOF_OF_EXECUTION_TAMPERED"
    q = o["quarantine"]
    assert q["quarantined"] is True
    assert q["read_only"] is True
    assert q["blocks_commit_finalization"] is True
    assert q["preserves_evidence"] is True
    assert q["preserves_audit"] is True
    assert q["preserves_proof_artifacts"] is True
    assert q["deletes_records"] is False
    assert q["mutates_external"] is False


def test_abq_quarantine_action_quarantined():
    o = k.prepare(desired_recovery_action="QUARANTINE")
    assert o["final_recovery_state"] == "QUARANTINED"
    assert o["quarantine_required"] is True
    assert o["quarantine"]["quarantined"] is True
    assert o["outbox_released"] is False


def test_abq_abort_controller_hash_recompute():
    ac = _abort()["abort_controller"]
    # abort_controller_hash excludes its own key + "signal".
    assert _core_hash(ac, "abort_controller_hash", "signal") == \
        ac["abort_controller_hash"]


def test_abq_quarantine_hash_recompute():
    q = k.prepare(desired_recovery_action="QUARANTINE")["quarantine"]
    # quarantine_hash excludes only its own key (no "signal" to exclude).
    assert _core_hash(q, "quarantine_hash") == q["quarantine_hash"]


# --- API layer -------------------------------------------------------------
def test_abq_api_abort_action(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="abort").json()
    assert o["final_recovery_state"] == "ABORTED_PRE_COMMIT"
    assert o["dominant_signal"] == "USER_ABORT_REQUESTED"
    assert o["recovery_applied"] is False
    assert o["outbox_released"] is False


def test_abq_api_quarantine_action(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="quarantine").json()
    assert o["final_recovery_state"] == "QUARANTINED"
    assert o["quarantine_required"] is True


def test_abq_api_kill_switch_run_aborts(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="run", kill_switch=True).json()
    assert o["final_recovery_state"] == "ABORTED_PRE_COMMIT"
    assert o["dominant_signal"] == "RUNTIME_KILL_SWITCH_ACTIVE"


def test_abq_api_abort_subfield_endpoint(gate):
    rid, _ = gate.prepared_recovery(action="abort")
    ac = gate.rc(rid, "abort").json()["abort_controller"]
    assert ac["abort_active"] is True
    assert ac["releases_outbox"] is False
    assert ac["deletes_audit_history"] is False


def test_abq_api_quarantine_subfield_endpoint(gate):
    rid, _ = gate.prepared_recovery(action="quarantine")
    q = gate.rc(rid, "quarantine").json()["quarantine"]
    assert q["quarantined"] is True
    assert q["read_only"] is True
    assert q["preserves_evidence"] is True
    assert q["mutates_external"] is False

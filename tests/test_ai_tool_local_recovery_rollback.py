"""TOOL-B9.1 v4: local rollback executor + rollback equivalence (section 11).
Rollback is LOCAL-ONLY: a clean ROLLBACK_LOCAL reverts local reversible state to
the pre-commit hash (RollbackEquivalence: hash(state_after_rollback) ==
hash(before_commit)) and produces ROLLBACK_APPLIED_LOCAL with NO external effect
(no external/provider rollback, no outbox release). When equivalence cannot be
proved, the plan is missing, the target is not local, the current state is
incompatible, or idempotency is invalid, the rollback fails closed and NEVER
touches any external-effect surface.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from finalis.ai_employee import tool_local_recovery as lr
from tests import _b91_kernel as k


def _no_external_effect(o):
    """A rollback (clean or blocked) never sets any external-effect flag."""
    assert o["produced_external_effect"] is False
    assert o["provider_called"] is False
    assert o["message_sent"] is False
    assert o["payment_executed"] is False
    assert o["external_crm_mutated"] is False
    assert o["outbox_released"] is False


# --- kernel layer ----------------------------------------------------------
def test_rollback_clean_applied_local():
    o = k.prepare(desired_recovery_action="ROLLBACK_LOCAL")
    assert o["final_recovery_state"] == "ROLLBACK_APPLIED_LOCAL"
    assert o["recovery_decision_status"] == "B91_DECISION_ROLLBACK_APPLIED_LOCAL"
    assert o["rollback_applied_local"] is True
    assert o["recovery_applied"] is True


def test_rollback_executor_result_and_equivalence():
    o = k.prepare(desired_recovery_action="ROLLBACK_LOCAL")
    rbk = o["rollback_executor"]
    assert rbk["rollback_result"] == "ROLLBACK_APPLIED_LOCAL"
    assert rbk["rollback_executable_local"] is True
    assert rbk["rollback_equivalence"] is True
    assert rbk["rollback_equivalence_status"] == "EQUIVALENT"
    assert rbk["rollback_target_is_local"] is True


def test_rollback_executor_no_external_surface():
    rbk = k.prepare(desired_recovery_action="ROLLBACK_LOCAL")["rollback_executor"]
    assert rbk["external_rollback"] is False
    assert rbk["provider_rollback"] is False
    assert rbk["outbox_released"] is False


def test_rollback_clean_no_external_effect():
    o = k.prepare(desired_recovery_action="ROLLBACK_LOCAL")
    _no_external_effect(o)
    assert o["no_external_effect"] is True
    assert o["inert_outbox_preserved"] is True


def test_rollback_equivalence_fail_not_executable():
    o = k.prepare(desired_recovery_action="ROLLBACK_LOCAL",
                  rollback_equivalence_fail=True)
    assert o["final_recovery_state"] == "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET"
    assert o["dominant_signal"] == "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET"
    assert o["recovery_applied"] is False
    rbk = o["rollback_executor"]
    assert rbk["rollback_equivalence"] is False
    assert rbk["rollback_equivalence_status"] == "NOT_PROVABLE"
    assert rbk["rollback_result"] == "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET"
    _no_external_effect(o)


def test_rollback_plan_missing_recovery_failed():
    o = k.prepare(desired_recovery_action="ROLLBACK_LOCAL",
                  rollback_plan_missing=True)
    assert o["final_recovery_state"] == "RECOVERY_FAILED"
    assert o["dominant_signal"] == "ROLLBACK_PLAN_MISSING"
    assert o["recovery_applied"] is False
    assert o["rollback_executor"]["rollback_executable_local"] is False
    _no_external_effect(o)


def test_rollback_target_not_local_not_executable():
    o = k.prepare(desired_recovery_action="ROLLBACK_LOCAL",
                  rollback_target_not_local=True)
    assert o["final_recovery_state"] == "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET"
    assert o["dominant_signal"] == "ROLLBACK_TARGET_NOT_LOCAL"
    assert o["recovery_applied"] is False
    assert o["rollback_executor"]["rollback_target_is_local"] is False
    _no_external_effect(o)


def test_rollback_current_state_incompatible_not_executable():
    o = k.prepare(desired_recovery_action="ROLLBACK_LOCAL",
                  rollback_current_state_incompatible=True)
    assert o["final_recovery_state"] == "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET"
    assert o["dominant_signal"] == "ROLLBACK_CURRENT_STATE_INCOMPATIBLE"
    assert o["recovery_applied"] is False
    _no_external_effect(o)


def test_rollback_idempotency_invalid_not_executable():
    o = k.prepare(desired_recovery_action="ROLLBACK_LOCAL",
                  rollback_idempotency_invalid=True)
    assert o["final_recovery_state"] == "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET"
    assert o["dominant_signal"] == "ROLLBACK_IDEMPOTENCY_INVALID"
    assert o["recovery_applied"] is False
    _no_external_effect(o)


def test_rollback_exec_hash_recompute():
    rbk = k.prepare(desired_recovery_action="ROLLBACK_LOCAL")["rollback_executor"]
    assert _core_hash(rbk, "rollback_exec_hash", "signal") == \
        rbk["rollback_exec_hash"]


def test_rollback_exec_hash_recompute_on_blocked():
    o = k.prepare(desired_recovery_action="ROLLBACK_LOCAL",
                  rollback_equivalence_fail=True)
    rbk = o["rollback_executor"]
    assert _core_hash(rbk, "rollback_exec_hash", "signal") == \
        rbk["rollback_exec_hash"]


def test_rollback_non_rollback_action_not_requested():
    # A RECOVER (non-rollback) action leaves the executor idle, never external.
    rbk = k.prepare(desired_recovery_action="RECOVER")["rollback_executor"]
    assert rbk["rollback_result"] == "NOT_REQUESTED"
    assert rbk["external_rollback"] is False
    assert rbk["provider_rollback"] is False
    assert rbk["outbox_released"] is False


# --- API layer -------------------------------------------------------------
def test_api_rollback_local_action_applied(gate):
    txid, _ = gate.committed_local_tx()
    r = gate.recover(txid, action="rollback-local")
    assert r.status_code == 200
    o = r.json()
    assert o["final_recovery_state"] == "ROLLBACK_APPLIED_LOCAL"
    assert o["rollback_applied_local"] is True
    _no_external_effect(o)


def test_api_rollback_subfield_endpoint(gate):
    rid, _ = gate.prepared_recovery(action="rollback-local")
    r = gate.rc(rid, "rollback")
    assert r.status_code == 200
    rbk = r.json()["rollback_executor"]
    assert rbk["rollback_result"] == "ROLLBACK_APPLIED_LOCAL"
    assert rbk["rollback_equivalence"] is True
    assert rbk["external_rollback"] is False
    assert rbk["provider_rollback"] is False


def test_api_rollback_never_sets_external_effect(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="rollback-local").json()
    assert o["no_external_effect"] is True
    assert o["inert_outbox_preserved"] is True
    _no_external_effect(o)


def test_api_rollback_equivalence_fail_blocked(gate):
    txid, _ = gate.committed_local_tx()
    o = gate.recover(txid, action="rollback-local",
                     rollback_equivalence_fail=True).json()
    assert o["final_recovery_state"] == "ROLLBACK_NOT_EXECUTABLE_FOR_TARGET"
    assert o["recovery_applied"] is False
    _no_external_effect(o)

"""TOOL-B9 v5: NoExternalEffect theorem + emergency abort / rollback readiness.

The Finalis Transaction Twin PROVES it produces NO external effect: for every
inert-outbox item nothing is released, no provider is called, no delivery is
attempted and no external state is mutated. Any direct attempt marker (an
external effect or a provider call) is QUARANTINED with NO commit applied. The
runtime is also rollback-ready and supports pre-commit emergency abort — and on
ANY blocked outcome the external-effect flags stay False.
"""
from finalis.ai_employee.tool_local_transaction import _core_hash
from tests import _b9_kernel as k
from tests.conftest import OWNER


# --- kernel layer ----------------------------------------------------------
def test_nee_clean_theorem_holds():
    theorem = k.clean_outcome()["no_external_effect_theorem"]
    assert theorem["theorem_holds"] is True
    assert theorem["theorem_status"] == "PROVED"
    assert theorem["signals_detected"] == []
    assert theorem["detected_attempt_markers"] == []


def test_nee_clean_theorem_for_all_outbox_items_proved():
    fa = k.clean_outcome()["no_external_effect_theorem"]["for_all_outbox_items"]
    assert fa["released_false"] is True
    assert fa["provider_called_false"] is True
    assert fa["delivery_attempted_false"] is True
    assert fa["external_state_mutated_false"] is True


def test_nee_external_effect_attempt_quarantined():
    o = k.prepare(attempt_markers={"external_effect": True})
    assert o["b9_status"] == "B9_QUARANTINED"
    assert o["dominant_signal"] == "EXTERNAL_EFFECT_ATTEMPT"
    assert o["local_commit_applied"] is False


def test_nee_provider_call_attempt_quarantined():
    o = k.prepare(attempt_markers={"provider_call": True})
    assert o["b9_status"] == "B9_QUARANTINED"
    assert o["dominant_signal"] == "PROVIDER_CALL_ATTEMPT"
    assert o["local_commit_applied"] is False


def test_nee_abort_pre_commit_transaction_aborted():
    o = k.prepare(abort_stage="pre_commit")
    assert o["b9_status"] == "B9_ABORTED"
    assert o["dominant_signal"] == "TRANSACTION_ABORTED"
    assert o["local_commit_applied"] is False


def test_nee_abort_rollback_readiness_reflects_abort():
    rr = k.prepare(abort_stage="pre_commit")["rollback_readiness"]
    assert rr["readiness_status"] == "ABORTED"
    assert rr["abort_stage"] == "pre_commit"
    assert rr["signal"] == "TRANSACTION_ABORTED"


def test_nee_clean_rollback_ready():
    rr = k.clean_outcome()["rollback_readiness"]
    assert rr["rollback_ready"] is True
    assert rr["readiness_status"] == "READY"
    assert rr["abort_stage"] is None
    assert rr["kill_switch_state"] == "INACTIVE"


def test_nee_rollback_supports_every_abort_stage():
    rr = k.clean_outcome()["rollback_readiness"]
    assert rr["supports_pre_commit_abort"] is True
    assert rr["supports_validation_abort"] is True
    assert rr["supports_shadow_abort"] is True
    assert rr["supports_pre_finalization_abort"] is True
    assert rr["supports_post_commit_rollback_request"] is True


def test_nee_blocked_outcomes_never_set_external_flags():
    # Whatever the reason a transaction is blocked, NO external effect flag may
    # ever be set — the twin cannot leak an effect on a rejection path.
    blocked = [
        {"attempt_markers": {"external_effect": True}},
        {"attempt_markers": {"provider_call": True}},
        {"abort_stage": "pre_commit"},
        {"kill_switch": True},
        {"authority_basis": {"source": "DOCUMENT"}},
        {"outbox_release_attempts": 1},
        {"replay_detected": True},
    ]
    for over in blocked:
        o = k.prepare(**over)
        assert o["local_commit_applied"] is False
        assert o["is_external"] is False
        assert o["is_execution"] is False
        assert o["produced_external_effect"] is False
        assert o["provider_called"] is False
        assert o["message_sent"] is False
        assert o["payment_executed"] is False
        assert o["external_crm_mutated"] is False


def test_nee_theorem_hash_recomputes():
    theorem = k.clean_outcome()["no_external_effect_theorem"]
    assert _core_hash(theorem, "no_external_effect_hash",
                      "signals_detected") == theorem["no_external_effect_hash"]


def test_nee_rollback_readiness_hash_recomputes():
    rr = k.clean_outcome()["rollback_readiness"]
    assert _core_hash(rr, "rollback_readiness_hash",
                      "signal") == rr["rollback_readiness_hash"]


def test_nee_attempt_marker_changes_decision_hash():
    clean = k.prepare()["b9_decision_hash"]
    attempted = k.prepare(
        attempt_markers={"external_effect": True})["b9_decision_hash"]
    assert clean != attempted


# --- API layer -------------------------------------------------------------
def test_nee_api_abort_returns_aborted(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    a = gate.lt(tid, "/abort", method="POST").json()
    assert a["abort_status"] == "ABORTED"
    assert a["no_external_effect"] is True


def test_nee_api_abort_includes_rollback_fields(gate):
    tid, o = gate.prepared_local_tx(op="commit-local")
    a = gate.lt(tid, "/abort", method="POST").json()
    assert a["rollback_ready"] is True
    assert a["rollback_hash"] == o["rollback_readiness"]["rollback_hash"]


def test_nee_api_abort_requires_case_update_permission(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.lt(tid, "/abort", method="POST")
    assert r.status_code == 200


def test_nee_api_no_external_effect_endpoint(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.lt(tid, "/no-external-effect")
    assert r.status_code == 200
    theorem = r.json()["no_external_effect_theorem"]
    assert theorem["theorem_holds"] is True
    assert theorem["theorem_status"] == "PROVED"


def test_nee_api_rollback_plan_endpoint(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.lt(tid, "/rollback-plan")
    assert r.status_code == 200
    rr = r.json()["rollback_readiness"]
    assert rr["rollback_ready"] is True
    assert rr["rollback_plan"]


def test_nee_api_twin_blocks_external_effects(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    twin = gate.lt(tid, "/twin").json()["finalis_transaction_twin"]
    assert "EXTERNAL_EFFECT" in twin["blocked_external_effects"]
    assert "PROVIDER_CALL" in twin["blocked_external_effects"]
    assert twin["inert_outbox"] == []

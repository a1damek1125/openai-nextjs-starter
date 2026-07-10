"""TOOL-B9.1 v4: Recovery runtime core — clean local recovery, no external
effect, chaos sentinel, Proof-of-Recovery, reproducibility.

The recovery runtime is LOCAL-ONLY: it produces NO external effect (no provider
call, message, payment, external CRM/evidence mutation) and never releases the
inert outbox. B8 stays evidence only; the B9 certificate, Proof-of-Execution,
Proof-of-Recovery and Recovery Safety Case are proof, NOT authority.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from finalis.ai_employee import tool_local_recovery as lr
from tests import _b91_kernel as k


# --- kernel layer ----------------------------------------------------------
def test_clean_recover_recovered():
    o = k.clean_outcome(desired_recovery_action="RECOVER")
    assert o["final_recovery_state"] == "RECOVERED"
    assert o["recovery_decision_status"] == "B91_DECISION_RECOVERED"
    assert o["recovery_applied"] is True
    assert o["dominant_signal"] == "RECOVERY_CLEAN"


def test_clean_action_terminal_states():
    assert k.prepare(desired_recovery_action="STATUS")[
        "final_recovery_state"] == "CLEAN"
    assert k.prepare(desired_recovery_action="PLAN")[
        "final_recovery_state"] == "RECOVERY_PLANNED"
    assert k.prepare(desired_recovery_action="ROLLBACK_LOCAL")[
        "final_recovery_state"] == "ROLLBACK_APPLIED_LOCAL"
    assert k.prepare(desired_recovery_action="CRASH_DRILL")[
        "final_recovery_state"] == "RECOVERY_REQUIRED"
    assert k.prepare(desired_recovery_action="QUARANTINE")[
        "final_recovery_state"] == "QUARANTINED"


def test_clean_no_external_effect_and_evidence_only():
    o = k.clean_outcome()
    assert o["no_external_effect"] is True
    assert o["inert_outbox_preserved"] is True
    assert o["is_external"] is False and o["is_execution"] is False
    assert o["produced_external_effect"] is False
    assert o["provider_called"] is False and o["message_sent"] is False
    assert o["payment_executed"] is False and o["external_crm_mutated"] is False
    assert o["outbox_released"] is False
    assert o["b8_evidence_only"] is True
    assert o["b9_certificate_is_authority"] is False
    assert o["proof_of_recovery_is_authority"] is False
    assert o["recovery_safety_case_is_authority"] is False


def test_clean_monotonicity_and_reconciliation_and_idempotency():
    o = k.clean_outcome()
    assert o["safety_monotonicity_passed"] is True
    assert o["double_entry_reconciliation_passed"] is True
    assert o["idempotency_preserved"] is True


def test_chaos_sentinel_all_phases_safe():
    o = k.clean_outcome()
    h = o["b91_chaos_harness"]
    assert h["phase_count"] == 21
    assert h["all_crashes_safe"] is True
    assert len(h["phases"]) == 21
    for ph in h["phases"]:
        assert ph["no_external_effect"] is True
        assert ph["inert_outbox_preserved"] is True
        assert ph["safe"] is True
    assert o["b91_release_gate_report"]["release_gate_status"] == "PASSED"


def test_proof_of_recovery_stream_complete():
    o = k.clean_outcome()
    por = o["por_stream"]
    assert por["event_count"] == 17
    assert por["stream_status"] == "COMPLETE"
    assert por["chain_valid"] is True
    assert o["proof_of_recovery"]["proof_of_recovery_valid"] is True


def test_proof_bundle_and_checkpoints_counts():
    o = k.clean_outcome()
    assert o["b91_recovery_proof_bundle"]["component_count"] == 24
    assert len(o["recovery_checkpoints"]["checkpoints"]) == 9


def test_decision_hash_reproducible():
    assert k.prepare()["b91_decision_hash"] == k.prepare()["b91_decision_hash"]


def test_certificate_and_safety_case_hash_recompute():
    o = k.clean_outcome()
    c = o["recovery_certificate"]
    assert _core_hash(c, "recovery_certificate_hash", "verification_status") == \
        c["recovery_certificate_hash"]
    sc = o["recovery_safety_case"]
    assert _core_hash(sc, "safety_case_hash", "signal", "verification_status") \
        == sc["safety_case_hash"]


def test_missing_transaction_fails_closed():
    o = lr.prepare_recovery_outcome(
        recovery_id="r", transaction_id="tx", tenant_id="t1", actor_id="u",
        actor_type="human", b9_outcome=None, desired_recovery_action="RECOVER",
        created_at="T")
    assert o["final_recovery_state"] == "RECOVERY_FAILED"
    assert o["dominant_signal"] == "B9_TRANSACTION_MISSING"
    assert o["no_external_effect"] is True


# --- API layer -------------------------------------------------------------
def test_api_clean_recovery_run(gate):
    rid, o = gate.prepared_recovery(action="run")
    assert o["final_recovery_state"] == "RECOVERED"
    assert o["recovery_applied"] is True
    assert o["no_external_effect"] is True


def test_api_recovery_twin_and_verify(gate):
    from tests.conftest import OWNER
    rid, _ = gate.prepared_recovery(action="run")
    twin = gate.rc(rid, "twin").json()["twin"]
    assert twin["recovery_twin_hash"]
    v = gate.c.post(
        "/ai-tools/local-transactions/recovery/verify?recovery_id=" + rid,
        headers=gate.h(OWNER)).json()
    assert v["b91_decision_hash_valid"] is True
    assert v["verification_status"] == "VALID"


def test_api_registry_and_policy(gate):
    from tests.conftest import OWNER
    gate.prepared_recovery(action="run")
    reg = gate.c.get("/ai-tools/local-transactions/recovery/registry",
                     headers=gate.h(OWNER)).json()
    assert reg["recovery_outcome_count"] >= 1
    pol = gate.c.get("/ai-tools/local-transactions/recovery/policy",
                     headers=gate.h(OWNER)).json()
    assert pol["local_recovery_only"] is True
    assert pol["external_effect"] is False
    assert pol["b8_is_evidence_only"] is True
    assert pol["production_ready"] is False

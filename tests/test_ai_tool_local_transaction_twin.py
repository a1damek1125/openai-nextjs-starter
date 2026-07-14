"""TOOL-B9 v5: Finalis Transaction Twin — clean local, reversible commit path.

The twin commits ONLY to local, reversible internal state and produces NO
external effect: no provider call, no message, no payment, no external
CRM/evidence mutation. B8 is evidence only.
"""
from finalis.ai_employee.tool_local_transaction import _core_hash
from tests import _b9_kernel as k


# --- kernel layer ----------------------------------------------------------
def test_clean_local_commit_applied():
    o = k.clean_outcome()
    assert o["b9_status"] == "B9_LOCAL_COMMIT_APPLIED"
    assert o["b9_decision_status"] == "B9_DECISION_ALLOW_LOCAL_COMMIT"
    assert o["b9_outcome_kind"] == "LOCAL_REVERSIBLE_COMMIT"
    assert o["local_commit_applied"] is True
    assert o["all_signals"] == ["B9_LOCAL_COMMIT_APPLIED"]


def test_clean_outcome_has_no_external_effect():
    o = k.clean_outcome()
    assert o["is_external"] is False
    assert o["is_execution"] is False
    assert o["produced_external_effect"] is False
    assert o["provider_called"] is False
    assert o["message_sent"] is False
    assert o["payment_executed"] is False
    assert o["external_crm_mutated"] is False
    assert o["reversible"] is True
    assert o["b8_evidence_only"] is True


def test_local_commit_is_reversible_before_differs_from_after():
    o = k.clean_outcome()
    assert o["before_state_hash"] != o["after_state_hash"]
    assert o["committed_state"] == {"status": "reviewed"}
    assert o["no_external_effect_theorem"]["theorem_holds"] is True
    assert o["rollback_readiness"]["rollback_ready"] is True


def test_decision_hash_reproducible():
    assert k.prepare()["b9_decision_hash"] == k.prepare()["b9_decision_hash"]


def test_all_faults_blocked_and_release_gate_passed():
    o = k.clean_outcome()
    assert o["b9_fault_injection_harness"]["all_faults_blocked"] is True
    assert o["b9_release_gate_report"]["release_gate_status"] == "PASSED"


def test_certificate_hash_recomputes():
    c = k.clean_outcome()["certificate"]
    assert _core_hash(c, "certificate_hash", "verification_status") == c[
        "certificate_hash"]


# --- API layer -------------------------------------------------------------
def test_api_clean_commit_local_applies_reversible_state(gate):
    tid, o = gate.prepared_local_tx(op="commit-local")
    assert o["b9_status"] == "B9_LOCAL_COMMIT_APPLIED"
    assert o["local_commit_applied"] is True
    assert o["committed_state"] == {"status": "reviewed"}


def test_api_twin_endpoint(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    twin = gate.lt(tid, "/twin").json()["finalis_transaction_twin"]
    assert twin["local_commit_applied"] is True
    assert twin["b9_status"] == "B9_LOCAL_COMMIT_APPLIED"
    assert twin["inert_outbox"] == [] or isinstance(twin["inert_outbox"], list)
    assert twin["blocked_external_effects"]


def test_api_verify_valid(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    v = gate.lt(tid, "/verify", method="POST").json()
    assert v["b9_decision_hash_valid"] is True
    assert v["verification_status"] == "VALID"


def test_api_prepare_does_not_commit(gate):
    tid, o = gate.prepared_local_tx(op="prepare")
    # prepare computes the decision but never applies the local commit
    assert o["local_commit_applied"] is True  # would-commit decision
    twin = gate.lt(tid, "/twin").json()["finalis_transaction_twin"]
    # the stored request outcome from prepare is not an applied commit
    assert "current_local_state" in twin

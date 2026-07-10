"""TOOL-B9.2 v5: Proof-of-Work-Outcome — a clean run proves; every missing or
invalid factor invalidates the PoWO; the PoWO is derived evidence that authorizes
nothing.
"""
from tests import _b92_kernel as k


def _degrades(over, expected_signal, expected_truth=None):
    o = k.prepare(**over)
    assert o["proof_of_work_outcome_valid"] is False
    assert o["work_run_state"] != "WORK_OUTCOME_CERTIFIED"
    assert expected_signal in o["all_signals"]
    if expected_truth is not None:
        assert o["work_outcome_truth_state"] == expected_truth
    # No external effect ever, even on an invalidated PoWO.
    assert o["produced_external_effect"] is False
    assert o["outbox_released"] is False
    return o


def test_clean_powo_valid_all_factors_true():
    o = k.clean_outcome()
    assert o["proof_of_work_outcome_valid"] is True
    factors = o["proof_of_work_outcome"]["factors"]
    assert all(factors.values())
    assert len(factors) >= 20


def test_missing_origin_invalidates():
    _degrades({"origin_ambiguous": True}, "WORK_ORIGIN_AMBIGUOUS")


def test_identity_ambiguity_invalidates():
    _degrades({"source_principal_id": None, "effective_principal_id": None},
              "PRINCIPAL_CONTINUITY_UNKNOWN")


def test_disputed_critical_memory_invalidates():
    _degrades({"memory_facts": [{"id": "m", "trust": "DISPUTED",
                                 "critical": True, "used": True}]},
              "MEMORY_CRITICAL_FACT_DISPUTED")


def test_approval_mismatch_invalidates():
    _degrades({"approved_action": "A", "actual_action": "B"},
              "APPROVAL_ACTION_MISMATCH")


def test_invalid_transaction_binding_invalidates():
    o = _degrades({"bind_b9": False}, "TRANSACTION_BINDING_MISSING")
    assert o["proof_of_work_outcome"]["factors"]["TransactionTwinValid"] is False


def test_missing_artifact_lineage_invalidates_when_expected():
    _degrades({"artifacts": []}, "ARTIFACT_LINEAGE_MISSING")


def test_stale_revocation_epoch_invalidates():
    _degrades({"bound_principal_epoch": 1, "current_principal_epoch": 2},
              "REVOCATION_DETECTED", expected_truth="REVOKED")


def test_secret_exposure_tampered():
    o = _degrades({"secret_exposed_to_model": True},
                  "SECRET_EXPOSURE_TO_MODEL_DETECTED", expected_truth="TAMPERED")
    assert o["work_run_state"] == "QUARANTINED"


def test_external_effect_contradicted():
    o = _degrades({"attempt_markers": {"provider_call": True}},
                  "WORK_EXTERNAL_EFFECT_DETECTED", expected_truth="CONTRADICTED")
    assert o["work_run_state"] == "QUARANTINED"


def test_no_artifact_expected_still_proves():
    o = k.prepare(artifact_expected=False, artifacts=[])
    assert o["proof_of_work_outcome_valid"] is True
    assert o["work_outcome_truth_state"] == "PROVEN"


def test_observer_failure_not_certified():
    o = k.prepare(observer_unavailable=True)
    # Observer failure must never appear as successful (certified) work.
    assert o["work_outcome_certified"] is False
    assert o["work_run_state"] != "WORK_OUTCOME_CERTIFIED"


def test_powo_authorizes_nothing():
    powo = k.clean_outcome()["proof_of_work_outcome"]
    for f in ("authorizes_execution", "authorizes_commit", "authorizes_recovery",
              "authorizes_delivery"):
        assert powo[f] is False


def test_powo_changes_hash_on_degradation():
    clean = k.prepare()["proof_of_work_outcome"]["proof_of_work_outcome_hash"]
    bad = k.prepare(approval_revoked=True)["proof_of_work_outcome"][
        "proof_of_work_outcome_hash"]
    assert clean != bad


# --- API layer -------------------------------------------------------------
def test_api_powo_endpoint_valid(gate):
    wrid, _ = gate.observed_work()
    powo = gate.wo(wrid, "proof-of-work-outcome").json()[
        "proof_of_work_outcome"]
    assert powo["verification_status"] == "VALID"
    assert powo["proof_of_work_outcome_valid"] is True


def test_api_missing_evidence_endpoint(gate):
    wrid, _ = gate.observed_work()
    neg = gate.wo(wrid, "missing-evidence").json()["negative_space"]
    assert neg["no_critical_missing"] is True

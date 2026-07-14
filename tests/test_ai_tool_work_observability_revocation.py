"""TOOL-B9.2 v5: Revocation epochs + propagation (sections 14, 15) and the
read-only transaction/recovery binding over B9/B9.1 (section 19 part).

B9.2 only OBSERVES revocation — it never performs it. A stale/advanced epoch or a
detected revocation that has not safely propagated degrades the work outcome and
invalidates the Proof-of-Work-Outcome (derived evidence only; B9/B9.1 still
control whether execution actually blocks). The transaction/recovery bindings are
read-only projections of the B9/B9.1 evidence and mutate nothing.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from finalis.ai_employee import tool_work_observability as wo
from tests import _b92_kernel as k


def _rev_degrades(over, expected_signal, expected_state, expected_truth):
    o = k.prepare(**over)
    assert o["work_run_state"] == expected_state
    assert o["work_outcome_truth_state"] == expected_truth
    assert o["proof_of_work_outcome_valid"] is False
    assert expected_signal in o["all_signals"]
    # Never any real external effect, even on a revoked/rejected outcome.
    assert o["produced_external_effect"] is False
    assert o["outbox_released"] is False
    return o


# --- kernel layer: revocation epochs + propagation -------------------------
def test_rev_clean_revocation_status_clean():
    rev = k.clean_outcome()["revocation"]
    assert rev["revocation_status"] == "CLEAN"
    assert rev["revocation_detected"] is False
    assert rev["revocation_still_valid"] is True


def test_rev_b92_never_performs_revocation():
    # B9.2 only observes; it never performs revocation.
    rev = k.clean_outcome()["revocation"]
    assert rev["performs_revocation"] is False


def test_rev_clean_propagation_invariants_present():
    rev = k.clean_outcome()["revocation"]
    assert rev["revoked_principal_blocks_new_work"] is True
    assert rev["revoked_integration_blocks_gateway"] is True
    assert rev["disabled_schedule_blocks_run"] is True
    assert rev["kill_switch_blocks_finalization"] is True
    assert rev["revocation_scopes"] == wo.REVOCATION_SCOPES


def test_rev_stale_epoch_rejected_and_powo_invalid():
    # A bound epoch of 1 with a current epoch of 2 is a stale/advanced epoch:
    # revocation is detected and the PoWO is invalid.
    o = _rev_degrades({"bound_principal_epoch": 1, "current_principal_epoch": 2},
                      "REVOCATION_DETECTED", "REJECTED", "REVOKED")
    rev = o["revocation"]
    assert rev["revocation_detected"] is True
    assert rev["revocation_still_valid"] is False
    assert "principal_epoch" in rev["advanced_epochs"]
    assert rev["bound_epochs"]["principal_epoch"] == 1
    assert rev["current_epochs"]["principal_epoch"] == 2


def test_rev_stale_epoch_invalidates_powo_factor():
    o = k.prepare(bound_principal_epoch=1, current_principal_epoch=2)
    factors = o["proof_of_work_outcome"]["factors"]
    assert factors["RevocationPropagationSafe"] is False


def test_rev_propagation_missing_signal():
    o = _rev_degrades(
        {"revocation_detected": True, "propagation_state": "PROPAGATION_MISSING"},
        "REVOCATION_PROPAGATION_MISSING", "REJECTED", "REVOKED")
    assert o["revocation"]["propagation_state"] == "PROPAGATION_MISSING"
    assert o["revocation"]["propagation_safe"] is False


def test_rev_propagation_late_signal():
    o = _rev_degrades(
        {"revocation_detected": True, "propagation_state": "PROPAGATION_LATE"},
        "REVOCATION_PROPAGATION_LATE", "REJECTED", "REVOKED")
    assert o["revocation"]["propagation_state"] == "PROPAGATION_LATE"


def test_rev_status_hash_recompute():
    rev = k.clean_outcome()["revocation"]
    assert _core_hash(rev, "revocation_status_hash", "signal") == \
        rev["revocation_status_hash"]


# --- kernel layer: transaction binding (read-only over B9) -----------------
def test_txn_clean_binding_read_only_and_binds_b9_evidence():
    b9 = k.clean_b9()
    o = k.prepare(b9_outcome=b9)
    tb = o["transaction_binding"]
    assert tb["read_only"] is True
    assert tb["mutates_transaction"] is False
    assert tb["binding_status"] == "VALID"
    # The binding projects the B9 outcome's hashes (evidence only).
    assert tb["transaction_id"] == b9["transaction_id"]
    assert tb["transaction_twin_hash"] == \
        (b9.get("transaction_envelope") or {}).get("canonical_hash")
    assert tb["poe_hash"] == (b9.get("poe_stream") or {}).get("poe_stream_hash")
    assert tb["transaction_certificate_hash"] == \
        (b9.get("certificate") or {}).get("certificate_hash")


def test_txn_clean_does_not_mutate_transaction_globally():
    o = k.clean_outcome()
    assert o["mutates_transaction"] is False
    assert o["read_only_over_b9_and_b9_1"] is True


def test_txn_binding_missing_when_unbound():
    o = _rev_degrades({"bind_b9": False}, "TRANSACTION_BINDING_MISSING",
                      "OBSERVATION_COMPLETE", "PARTIAL")
    tb = o["transaction_binding"]
    assert tb["binding_status"] == "INVALID"
    assert tb["transaction_id"] is None
    assert o["proof_of_work_outcome"]["factors"]["TransactionTwinValid"] is False


def test_txn_binding_hash_recompute():
    tb = k.clean_outcome()["transaction_binding"]
    assert _core_hash(tb, "transaction_binding_hash", "signal") == \
        tb["transaction_binding_hash"]


# --- kernel layer: recovery binding (read-only over B9.1) ------------------
def test_rec_binding_when_no_b91_outcome():
    rb = k.prepare()["recovery_binding"]
    # No B9.1 recovery bound -> recovery is not applicable and nothing is bound.
    assert rb["recovery_applicable"] is False
    assert rb["recovery_id"] is None
    assert rb["read_only"] is True
    assert rb["mutates_recovery"] is False


def test_rec_binding_valid_when_b91_bound():
    o = k.prepare(bind_b91=True)
    rb = o["recovery_binding"]
    assert rb["recovery_applicable"] is True
    assert rb["binding_status"] == "VALID"
    assert rb["recovery_id"] is not None
    # Binding a clean B9.1 recovery keeps the run certified.
    assert o["work_run_state"] == "WORK_OUTCOME_CERTIFIED"
    assert o["mutates_recovery"] is False


def test_rec_binding_hash_recompute():
    rb = k.prepare(bind_b91=True)["recovery_binding"]
    assert _core_hash(rb, "recovery_binding_hash", "signal") == \
        rb["recovery_binding_hash"]


def test_rev_txn_rec_no_authority_granted():
    o = k.clean_outcome()
    assert o["is_authority"] is False
    for f in ("authorizes_recovery", "authorizes_rollback", "authorizes_commit"):
        assert o[f] is False


# --- API layer -------------------------------------------------------------
def test_api_rev_revocation_endpoint_clean(gate):
    wrid, _ = gate.observed_work()
    rev = gate.wo(wrid, "revocation").json()["revocation"]
    assert rev["revocation_status"] == "CLEAN"
    assert rev["performs_revocation"] is False


def test_api_txn_transaction_endpoint_binds_evidence(gate):
    wrid, _ = gate.observed_work()
    tb = gate.wo(wrid, "transaction").json()["transaction_binding"]
    assert tb["binding_status"] == "VALID"
    assert tb["read_only"] is True
    assert tb["mutates_transaction"] is False
    assert tb["transaction_twin_hash"] is not None


def test_api_rec_recovery_endpoint_bound(gate):
    wrid, _ = gate.observed_work(bind_recovery=True)
    rb = gate.wo(wrid, "recovery").json()["recovery_binding"]
    assert rb["recovery_applicable"] is True
    assert rb["mutates_recovery"] is False


def test_api_rev_stale_epoch_rejected(gate):
    wrid, o = gate.observed_work(bound_principal_epoch=1, current_principal_epoch=2)
    assert o["work_run_state"] == "REJECTED"
    assert o["work_outcome_truth_state"] == "REVOKED"
    assert "REVOCATION_DETECTED" in o["all_signals"]
    rev = gate.wo(wrid, "revocation").json()["revocation"]
    assert rev["revocation_detected"] is True


def test_api_rev_propagation_missing_rejected(gate):
    wrid, o = gate.observed_work(
        revocation_detected=True, propagation_state="PROPAGATION_MISSING")
    assert o["work_run_state"] == "REJECTED"
    assert "REVOCATION_PROPAGATION_MISSING" in o["all_signals"]

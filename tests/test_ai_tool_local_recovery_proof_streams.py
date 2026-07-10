"""TOOL-B9.1 v4: Proof-of-Execution stream recovery (section 4) plus
Proof-of-Recovery event stream / proof (sections 5, 6, 7). The runtime
reclassifies the original B9 Proof-of-Execution stream (COMPLETE, prefix-valid
incomplete, out-of-order, duplicate, broken-chain, unrecoverable, tampered) and
builds a fresh hash-chained Proof-of-Recovery event stream plus a
Proof-of-Recovery proof. Tampered proofs quarantine; a missing recovery audit
invalidates the proof. All local, no external effect.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from finalis.ai_employee import tool_local_recovery as lr
from tests import _b91_kernel as k


# --- kernel layer: Proof-of-Execution stream recovery ----------------------
def test_proof_poe_recovery_complete_on_clean():
    p = k.clean_outcome()["poe_stream_recovery"]
    assert p["classification"] == "COMPLETE"
    assert p["prefix_valid"] is True
    assert p["stream_recoverable"] is True
    assert p["signal"] is None


def test_proof_poe_missing_events_incomplete_recoverable():
    o = k.prepare(desired_recovery_action="RECOVER",
                  poe_missing_events=["AUDIT_RECORDED"])
    assert o["final_recovery_state"] == "RECOVERY_REQUIRED"
    assert o["dominant_signal"] == "POE_STREAM_INCOMPLETE"
    p = o["poe_stream_recovery"]
    assert p["classification"] == "PREFIX_VALID_INCOMPLETE"
    assert p["prefix_valid"] is True
    assert p["stream_recoverable"] is True


def test_proof_poe_reorder_order_invalid():
    o = k.prepare(desired_recovery_action="RECOVER", poe_reorder=True)
    assert o["final_recovery_state"] == "RECOVERY_FAILED"
    assert o["dominant_signal"] == "POE_EVENT_ORDER_INVALID"
    assert o["poe_stream_recovery"]["classification"] == "OUT_OF_ORDER"
    assert o["poe_stream_recovery"]["stream_recoverable"] is False


def test_proof_poe_duplicate_event():
    o = k.prepare(desired_recovery_action="RECOVER", poe_duplicate=True)
    assert o["final_recovery_state"] == "RECOVERY_FAILED"
    assert o["dominant_signal"] == "POE_DUPLICATE_EVENT"
    assert o["poe_stream_recovery"]["classification"] == "DUPLICATE"


def test_proof_poe_broken_chain():
    o = k.prepare(desired_recovery_action="RECOVER", poe_broken_chain=True)
    assert o["final_recovery_state"] == "RECOVERY_FAILED"
    assert o["dominant_signal"] == "POE_BROKEN_CHAIN"
    assert o["poe_stream_recovery"]["classification"] == "BROKEN_CHAIN"


def test_proof_poe_unrecoverable():
    o = k.prepare(desired_recovery_action="RECOVER", poe_unrecoverable=True)
    assert o["final_recovery_state"] == "RECOVERY_FAILED"
    assert o["dominant_signal"] == "POE_STREAM_UNRECOVERABLE"
    p = o["poe_stream_recovery"]
    assert p["classification"] == "UNRECOVERABLE"
    assert p["stream_recoverable"] is False


def test_proof_poe_tamper_quarantined():
    o = k.prepare(desired_recovery_action="RECOVER", poe_tamper=True)
    assert o["final_recovery_state"] == "TAMPERED"
    assert o["dominant_signal"] == "PROOF_OF_EXECUTION_TAMPERED"
    assert o["quarantine_required"] is True
    assert o["poe_stream_recovery"]["classification"] == "TAMPERED"
    # No actual external effect even on a tampered/quarantined outcome.
    assert o["produced_external_effect"] is False
    assert o["outbox_released"] is False


# --- kernel layer: Proof-of-Recovery event stream + proof ------------------
def test_proof_por_stream_complete_on_clean():
    por = k.clean_outcome()["por_stream"]
    assert por["event_count"] == 17
    assert por["stream_status"] == "COMPLETE"
    assert por["chain_valid"] is True
    assert por["event_order_valid"] is True


def test_proof_por_stream_events_match_por_events():
    assert len(lr.POR_EVENTS) == 17
    por = k.clean_outcome()["por_stream"]
    assert por["required_event_count"] == 17


def test_proof_por_tamper_quarantined():
    o = k.prepare(desired_recovery_action="RECOVER", por_tamper=True)
    assert o["final_recovery_state"] == "TAMPERED"
    assert o["dominant_signal"] == "PROOF_OF_RECOVERY_TAMPERED"
    assert o["quarantine_required"] is True
    assert o["por_stream"]["stream_status"] == "INVALID"


def test_proof_por_missing_recovery_audit_invalid():
    o = k.prepare(desired_recovery_action="RECOVER",
                  por_missing_events=["RECOVERY_AUDIT_RECORDED"])
    assert o["final_recovery_state"] == "RECOVERY_FAILED"
    assert o["dominant_signal"] == "PROOF_OF_RECOVERY_INVALID"
    assert o["por_stream"]["stream_status"] == "INVALID"


def test_proof_of_recovery_valid_on_clean():
    pr = k.clean_outcome()["proof_of_recovery"]
    assert pr["proof_of_recovery_valid"] is True
    assert pr["proof_status"] == "VALID"
    assert all(pr["factors"].values())


def test_proof_of_recovery_invalid_when_factor_fails():
    o = k.prepare(desired_recovery_action="RECOVER",
                  por_missing_events=["RECOVERY_AUDIT_RECORDED"])
    pr = o["proof_of_recovery"]
    assert pr["proof_of_recovery_valid"] is False
    assert pr["proof_status"] == "INVALID"
    assert pr["factors"]["recovery_event_stream_complete"] is False


def test_proof_por_stream_hash_recompute():
    por = k.clean_outcome()["por_stream"]
    assert _core_hash(por, "por_stream_hash", "signal") == \
        por["por_stream_hash"]


def test_proof_poe_recovery_hash_recompute():
    poe = k.clean_outcome()["poe_stream_recovery"]
    assert _core_hash(poe, "poe_recovery_hash", "signal") == \
        poe["poe_recovery_hash"]


def test_proof_of_recovery_hash_recompute():
    pr = k.clean_outcome()["proof_of_recovery"]
    assert _core_hash(pr, "proof_of_recovery_hash", "signal") == \
        pr["proof_of_recovery_hash"]


# --- API layer -------------------------------------------------------------
def test_proof_api_por_stream_endpoint(gate):
    rid, _ = gate.prepared_recovery(action="run")
    r = gate.rc(rid, "por-stream")
    assert r.status_code == 200
    por = r.json()["por_stream"]
    assert por["event_count"] == 17
    assert por["stream_status"] == "COMPLETE"
    assert por["chain_valid"] is True


def test_proof_api_poe_recovery_endpoint(gate):
    rid, _ = gate.prepared_recovery(action="run")
    r = gate.rc(rid, "poe-recovery")
    assert r.status_code == 200
    poe = r.json()["poe_stream_recovery"]
    assert poe["classification"] == "COMPLETE"
    assert poe["stream_recoverable"] is True


def test_proof_api_proof_of_recovery_endpoint(gate):
    rid, _ = gate.prepared_recovery(action="run")
    r = gate.rc(rid, "proof-of-recovery")
    assert r.status_code == 200
    pr = r.json()["proof_of_recovery"]
    assert pr["proof_of_recovery_valid"] is True

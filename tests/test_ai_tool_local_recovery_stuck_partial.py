"""TOOL-B9.1 v4: stuck transaction detector (section 16) + partial commit
detector (section 12) + idempotent recovery guard (section 15) + conflict
recovery (section 18).

A stuck transaction does NOT self-heal into execution (it is reviewable, never
auto-progressed). A crash-induced partial commit quarantines with a remediation
recommendation. Recovery is idempotent: a mismatched replay fails closed and a
recommit of an aborted/quarantined/rolled-back transaction quarantines. Lock
conflicts fail closed (a stolen active lock quarantines; a conflicting or
cross-tenant-ambiguous recovery is stuck) while an interrupted lock acquisition
recovers safely. All EVIDENCE, never authority; no external effect on any path.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from tests import _b91_kernel as k


def _stuck(**over):
    o = k.prepare(desired_recovery_action="DETECT_STUCK", **over)
    assert o["final_recovery_state"] == "STUCK"
    # Stuck does NOT self-heal into execution.
    assert o["recovery_applied"] is False
    assert o["outbox_released"] is False
    sd = o["stuck_detector"]
    assert sd["stuck_detected"] is True
    assert sd["auto_progress"] is False
    assert sd["reviewable"] is True
    return o


def _partial(sig, **over):
    o = k.prepare(desired_recovery_action="RECOVER", **over)
    assert o["final_recovery_state"] == "QUARANTINED"
    assert o["dominant_signal"] == sig
    assert o["partial_commit_detector"]["partial_commit_detected"] is True
    assert o["outbox_released"] is False
    return o


# --- kernel layer: stuck detector ------------------------------------------
def test_sp_stuck_lock_held_too_long():
    assert _stuck(lock_age_seconds=9999)[
        "dominant_signal"] == "STUCK_LOCK_HELD_TOO_LONG"


def test_sp_stuck_recovering_too_long():
    assert _stuck(recovering_age_seconds=9999)[
        "dominant_signal"] == "STUCK_RECOVERING_TOO_LONG"


def test_sp_stuck_repeated_recovery_failure():
    assert _stuck(repeated_recovery_failures=5)[
        "dominant_signal"] == "STUCK_REPEATED_RECOVERY_FAILURE"


def test_sp_stuck_repeated_idempotency_conflict():
    assert _stuck(repeated_idempotency_conflicts=5)[
        "dominant_signal"] == "STUCK_REPEATED_IDEMPOTENCY_CONFLICT"


# --- kernel layer: partial commit detector ---------------------------------
def test_sp_partial_commit_signal_map():
    cases = [
        ({"missing_commit_record": True}, "PARTIAL_COMMIT_CERT_WITHOUT_COMMIT"),
        ({"missing_certificate": True}, "PARTIAL_COMMIT_COMMIT_WITHOUT_CERT"),
        ({"missing_poe": True}, "PARTIAL_COMMIT_COMMIT_WITHOUT_POE"),
        ({"after_state_mismatch": True}, "PARTIAL_COMMIT_AFTER_STATE_MISMATCH"),
        ({"missing_rollback_plan": True}, "PARTIAL_COMMIT_ROLLBACK_PLAN_MISSING"),
        ({"missing_audit": True}, "PARTIAL_COMMIT_AUDIT_MISSING"),
        ({"graph_inconsistent": True}, "PARTIAL_COMMIT_GRAPH_INCONSISTENT"),
    ]
    for over, sig in cases:
        _partial(sig, **over)


def test_sp_partial_commit_detector_fields():
    o = _partial("PARTIAL_COMMIT_CERT_WITHOUT_COMMIT", missing_commit_record=True)
    pcd = o["partial_commit_detector"]
    assert pcd["detector_status"] == "PARTIAL"
    assert pcd["remediation_recommendation"]
    assert pcd["remediation_recommendation"] != "none"


# --- kernel layer: idempotency guard ---------------------------------------
def test_sp_idempotency_clean_preserved():
    o = k.clean_outcome()
    assert o["idempotency_preserved"] is True
    assert o["idempotency_guard"]["idempotency_preserved"] is True


def test_sp_idempotency_mismatch_fails_closed():
    o = k.prepare(desired_recovery_action="RECOVER", idempotency_key="k",
                  prior_recovery={"k": "different"})
    assert o["final_recovery_state"] == "RECOVERY_FAILED"
    assert o["dominant_signal"] == "RECOVERY_IDEMPOTENCY_MISMATCH"
    assert o["recovery_applied"] is False


def test_sp_replay_after_rollback_quarantined():
    o = k.prepare(desired_recovery_action="RECOVER", replay_after_rollback=True)
    assert o["final_recovery_state"] == "QUARANTINED"
    assert o["dominant_signal"] == "REPLAY_AFTER_ROLLBACK_RECOMMIT"


def test_sp_revive_aborted_quarantined():
    o = k.prepare(desired_recovery_action="RECOVER", revive_aborted=True)
    assert o["final_recovery_state"] == "QUARANTINED"
    assert o["dominant_signal"] == "ABORTED_TRANSACTION_REVIVAL"


def test_sp_revive_quarantined_quarantined():
    o = k.prepare(desired_recovery_action="RECOVER", revive_quarantined=True)
    assert o["final_recovery_state"] == "QUARANTINED"
    assert o["dominant_signal"] == "QUARANTINED_TRANSACTION_REVIVAL"


# --- kernel layer: conflict recovery ---------------------------------------
def test_sp_steal_active_lock_quarantined():
    o = k.prepare(desired_recovery_action="RECOVER", steal_active_lock=True)
    assert o["final_recovery_state"] == "QUARANTINED"
    assert o["dominant_signal"] == "STOLEN_ACTIVE_LOCK"
    # An active lock is never actually stolen.
    assert o["conflict_recovery"]["active_lock_stolen"] is False


def test_sp_conflicting_recovery_stuck():
    o = k.prepare(desired_recovery_action="RECOVER", conflicting_recovery=True)
    assert o["final_recovery_state"] == "STUCK"
    assert o["dominant_signal"] == "CONFLICTING_RECOVERY_DETECTED"


def test_sp_cross_tenant_lock_ambiguity_stuck():
    o = k.prepare(desired_recovery_action="RECOVER",
                  cross_tenant_lock_ambiguity=True)
    assert o["final_recovery_state"] == "STUCK"
    assert o["dominant_signal"] == "CROSS_TENANT_RECOVERY_AMBIGUITY"


def test_sp_interrupted_lock_acquisition_recovers():
    o = k.prepare(desired_recovery_action="RECOVER",
                  interrupted_lock_acquisition=True)
    assert o["final_recovery_state"] == "RECOVERED"
    assert o["dominant_signal"] == "RECOVERY_CLEAN"
    cr = o["conflict_recovery"]
    assert cr["recovered"] is True
    assert cr["interrupted_lock_recovered"] is True


# --- kernel layer: hash recompute ------------------------------------------
def test_sp_component_hash_recompute():
    stuck = _stuck(lock_age_seconds=9999)["stuck_detector"]
    assert _core_hash(stuck, "stuck_detector_hash", "signal") == \
        stuck["stuck_detector_hash"]
    pcd = _partial("PARTIAL_COMMIT_AUDIT_MISSING",
                   missing_audit=True)["partial_commit_detector"]
    assert _core_hash(pcd, "partial_commit_hash", "signal") == \
        pcd["partial_commit_hash"]
    idem = k.prepare(desired_recovery_action="RECOVER", idempotency_key="k",
                     prior_recovery={"k": "different"})["idempotency_guard"]
    assert _core_hash(idem, "idempotency_hash", "signal") == \
        idem["idempotency_hash"]
    conf = k.prepare(desired_recovery_action="RECOVER",
                     conflicting_recovery=True)["conflict_recovery"]
    assert _core_hash(conf, "conflict_recovery_hash", "signal") == \
        conf["conflict_recovery_hash"]


# --- API layer -------------------------------------------------------------
def test_sp_api_stuck_endpoint(gate):
    rid, o = gate.prepared_recovery(action="stuck", lock_age_seconds=9999)
    assert o["final_recovery_state"] == "STUCK"
    assert o["dominant_signal"] == "STUCK_LOCK_HELD_TOO_LONG"
    sd = gate.rc(rid, "stuck").json()["stuck_detector"]
    assert sd["stuck_detected"] is True
    assert sd["auto_progress"] is False
    assert sd["reviewable"] is True


def test_sp_api_partial_commit_endpoint(gate):
    rid, o = gate.prepared_recovery(action="run", missing_commit_record=True)
    assert o["final_recovery_state"] == "QUARANTINED"
    assert o["dominant_signal"] == "PARTIAL_COMMIT_CERT_WITHOUT_COMMIT"
    pcd = gate.rc(rid, "partial-commit").json()["partial_commit_detector"]
    assert pcd["partial_commit_detected"] is True
    assert pcd["remediation_recommendation"] != "none"


def test_sp_api_conflict_endpoint(gate):
    rid, o = gate.prepared_recovery(action="run", steal_active_lock=True)
    assert o["final_recovery_state"] == "QUARANTINED"
    assert o["dominant_signal"] == "STOLEN_ACTIVE_LOCK"
    cr = gate.rc(rid, "conflict").json()["conflict_recovery"]
    assert cr["active_lock_stolen"] is False


def test_sp_api_inert_outbox_endpoint(gate):
    rid, o = gate.prepared_recovery(action="run")
    assert o["final_recovery_state"] == "RECOVERED"
    io = gate.rc(rid, "inert-outbox").json()["inert_outbox_preservation"]
    assert io["inert"] is True
    assert io["outbox_status"] == "INERT"

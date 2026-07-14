"""EMP-A1 v1: Employee Work Inbox — calibration state machine (section 21),
nested-interval safety (section 19.1), drift guard + conservative fallback
(sections 17-18).

Calibration/conformal estimation is schema-only and DISABLED by default. The
risk-and-stability kernel may only TIGHTEN safety (defer), never admit past a
deterministic safety denial. A prediction can never reduce a deterministic
floor; a non-HEALTHY calibration forces the deterministic upper envelope. Drift
that reduces EFFICIENCY (not safety) does not block; out-of-distribution drift
blocks admission until a governed recalibration re-enables it.
"""
from finalis.ai_employee import employee_work_inbox as wi
from tests import _emp_a1_kernel as k


# Calibration_state -> expected calibration reason code (section 21).
_CAL_CODE = {
    "DISABLED": "WORK_ITEM_CALIBRATION_DISABLED",
    "COLD_START": "WORK_ITEM_CALIBRATION_COLD_START",
    "HEALTHY": "WORK_ITEM_CALIBRATION_HEALTHY",
    "DEGRADED": "WORK_ITEM_CALIBRATION_DEGRADED",
    "SHIFT_SUSPECTED": "WORK_ITEM_CALIBRATION_DEGRADED",
    "OUT_OF_DISTRIBUTION": "WORK_ITEM_CALIBRATION_DEGRADED",
    "EXPIRED": "WORK_ITEM_CALIBRATION_EXPIRED",
}


# --- kernel layer: calibration state machine -------------------------------
def test_caldrift_default_calibration_disabled():
    cal = k.clean()["calibration"]
    assert cal["calibration_state"] == "DISABLED"
    assert cal["fallback_applied"] is True
    assert cal["prediction_available_for_safety"] is False
    assert "WORK_ITEM_CALIBRATION_DISABLED" in k.clean()["reason_codes"]


def test_caldrift_disabled_still_admits_ready():
    o = k.clean()
    assert o["disposition"] == "ADMIT_READY"
    assert o["resulting_state"] == "READY"


def test_caldrift_cold_start_reason_code():
    o = k.evaluate(calibration_state="COLD_START")
    assert o["calibration"]["reason_code"] == "WORK_ITEM_CALIBRATION_COLD_START"
    assert "WORK_ITEM_CALIBRATION_COLD_START" in o["reason_codes"]


def test_caldrift_healthy_reason_code():
    o = k.evaluate(calibration_state="HEALTHY")
    assert o["calibration"]["reason_code"] == "WORK_ITEM_CALIBRATION_HEALTHY"
    assert "WORK_ITEM_CALIBRATION_HEALTHY" in o["reason_codes"]


def test_caldrift_degraded_reason_code():
    o = k.evaluate(calibration_state="DEGRADED")
    assert "WORK_ITEM_CALIBRATION_DEGRADED" in o["reason_codes"]


def test_caldrift_shift_suspected_maps_degraded():
    o = k.evaluate(calibration_state="SHIFT_SUSPECTED")
    assert o["calibration"]["reason_code"] == "WORK_ITEM_CALIBRATION_DEGRADED"
    assert "WORK_ITEM_CALIBRATION_DEGRADED" in o["reason_codes"]


def test_caldrift_out_of_distribution_state_maps_degraded():
    o = k.evaluate(calibration_state="OUT_OF_DISTRIBUTION")
    assert o["calibration"]["reason_code"] == "WORK_ITEM_CALIBRATION_DEGRADED"
    assert "WORK_ITEM_CALIBRATION_DEGRADED" in o["reason_codes"]


def test_caldrift_expired_reason_code():
    o = k.evaluate(calibration_state="EXPIRED")
    assert o["calibration"]["reason_code"] == "WORK_ITEM_CALIBRATION_EXPIRED"
    assert "WORK_ITEM_CALIBRATION_EXPIRED" in o["reason_codes"]


def test_caldrift_every_state_maps_its_reason_code():
    for state in wi.CALIBRATION_STATES:
        o = k.evaluate(calibration_state=state)
        assert o["calibration"]["calibration_state"] == state
        assert o["calibration"]["reason_code"] == _CAL_CODE[state]
        assert _CAL_CODE[state] in o["reason_codes"]


# --- kernel layer: nested intervals + action calibration (section 19.1) ----
def test_caldrift_non_nested_interval_rejected():
    o = k.evaluate(calibration_state="HEALTHY", intervals_nested=False)
    assert o["disposition"] == "REJECTED"
    assert o["resulting_state"] == "REJECTED"
    assert "WORK_ITEM_NON_NESTED_INTERVAL_REJECTED" in o["reason_codes"]


def test_caldrift_action_calibration_mismatch_rejected():
    o = k.evaluate(calibration_state="HEALTHY", action_calibration_mismatch=True)
    assert o["disposition"] == "REJECTED"
    assert o["resulting_state"] == "REJECTED"
    assert "WORK_ITEM_ACTION_CALIBRATION_MISMATCH" in o["reason_codes"]


# --- kernel layer: conservative fallback (sections 17-18) ------------------
def test_caldrift_non_healthy_forces_deterministic_fallback():
    for state in wi.CALIBRATION_FALLBACK_STATES:
        cal = k.evaluate(calibration_state=state)["calibration"]
        assert cal["fallback_applied"] is True
        assert cal["prediction_available_for_safety"] is False


def test_caldrift_healthy_does_not_force_fallback():
    cal = k.evaluate(calibration_state="HEALTHY")["calibration"]
    assert cal["fallback_applied"] is False
    assert cal["prediction_available_for_safety"] is True


def test_caldrift_prediction_cannot_reduce_floor_under_fallback():
    # A conformal upper of zero cannot lower the deterministic safety_upper.
    o = k.evaluate(calibration_state="DEGRADED",
                   conformal_upper={r: 0 for r in wi.DEMAND_RESOURCES})
    dem = o["demand_envelope"]
    for r in wi.DEMAND_RESOURCES:
        assert dem["safety_upper"][r] >= dem["deterministic_floor"][r]
    assert dem["prediction_reduced_floor"] is False


# --- kernel layer: drift guard (sections 17-18) ----------------------------
def test_caldrift_drift_not_detected_default():
    dr = k.clean()["drift"]
    assert dr["drift_state"] == "DRIFT_NOT_DETECTED"
    assert dr["blocks_admission"] is False
    assert dr["observer_health_signal"] is False
    assert "WORK_ITEM_DRIFT_NOT_DETECTED" in k.clean()["reason_codes"]


def test_caldrift_drift_suspected_does_not_block():
    o = k.evaluate(drift_state="DRIFT_SUSPECTED")
    # Reduces efficiency, not safety — still admits READY.
    assert o["disposition"] == "ADMIT_READY"
    assert o["resulting_state"] == "READY"


def test_caldrift_drift_suspected_flags():
    dr = k.evaluate(drift_state="DRIFT_SUSPECTED")["drift"]
    assert dr["conservative_fallback_applied"] is True
    assert dr["requires_governed_recalibration"] is True
    assert dr["observer_health_signal"] is True
    assert dr["reduces_efficiency_not_safety"] is True
    assert dr["blocks_admission"] is False


def test_caldrift_out_of_distribution_blocks_admission():
    o = k.evaluate(drift_state="OUT_OF_DISTRIBUTION")
    assert o["disposition"] == "DEFERRED_DRIFT"
    assert o["resulting_state"] == "DEFERRED_DRIFT"
    assert o["drift"]["blocks_admission"] is True
    assert "WORK_ITEM_DEFERRED_DRIFT" in o["reason_codes"]


def test_caldrift_out_of_distribution_governed_recalibration_admits():
    o = k.evaluate(drift_state="OUT_OF_DISTRIBUTION",
                   governed_recalibration=True)
    assert o["disposition"] == "ADMIT_READY"
    assert o["resulting_state"] == "READY"
    assert o["drift"]["blocks_admission"] is False


def test_caldrift_out_of_distribution_auto_reenable_prevented():
    dr = k.evaluate(drift_state="OUT_OF_DISTRIBUTION")["drift"]
    assert dr["auto_reenable_prevented"] is True
    assert dr["requires_governed_recalibration"] is True


def test_caldrift_reduces_efficiency_not_safety_always():
    for d in wi.DRIFT_STATES:
        assert k.evaluate(drift_state=d)["drift"][
            "reduces_efficiency_not_safety"] is True


def test_caldrift_observer_health_signal_only_when_drift():
    assert k.evaluate(drift_state="DRIFT_NOT_DETECTED")["drift"][
        "observer_health_signal"] is False
    assert k.evaluate(drift_state="DRIFT_SUSPECTED")["drift"][
        "observer_health_signal"] is True
    assert k.evaluate(drift_state="OUT_OF_DISTRIBUTION")["drift"][
        "observer_health_signal"] is True


def test_caldrift_no_external_effect_on_drift_defer():
    o = k.evaluate(drift_state="OUT_OF_DISTRIBUTION")
    for f in ("run_created", "tool_transaction_started", "provider_called",
              "outbox_released", "external_state_mutated"):
        assert o[f] is False


# --- API layer -------------------------------------------------------------
def test_caldrift_api_calibration_endpoint(gate):
    from tests.conftest import OWNER
    r = gate.c.get("/ai-employee/work-inbox/calibration",
                   headers=gate.h(OWNER))
    assert r.status_code == 200
    j = r.json()
    assert j["calibration_disabled_by_default"] is True
    assert j["default_calibration_state"] == "DISABLED"
    assert j["calibration_states"] == wi.CALIBRATION_STATES


def test_caldrift_api_drift_endpoint(gate):
    from tests.conftest import OWNER
    r = gate.c.get("/ai-employee/work-inbox/drift", headers=gate.h(OWNER))
    assert r.status_code == 200
    j = r.json()
    assert j["drift_states"] == wi.DRIFT_STATES
    assert "CALIBRATION_DISABLED_OR_NOT_EXECUTION_VALIDATED" in \
        j["honesty_labels"]

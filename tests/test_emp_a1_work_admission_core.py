"""EMP-A1 v1: Employee Work Inbox core — clean admission, pure reference kernel
determinism, demand envelope safety, no external effect, exact retry, handoff.

The admission fabric is intake+admission only: it never executes work, creates
an EMP-A2 run, calls a provider/tool, starts a TOOL-B9 transaction, or produces
any external effect. Calibration is disabled by default; unknown demand is never
zero; a prediction can never reduce a deterministic safety floor.
"""
from finalis.ai_employee import employee_work_inbox as wi
from tests import _emp_a1_kernel as k


# --- kernel layer ----------------------------------------------------------
def test_clean_admits_ready():
    o = k.clean()
    assert o["disposition"] == "ADMIT_READY"
    assert o["resulting_state"] == "READY"
    assert o["safety_denied"] is False
    assert o["charge_allowed"] is True
    assert "ADMIT_READY" in o["reason_codes"]


def test_clean_no_external_effect_flags():
    o = k.clean()
    for f in ("run_created", "tool_transaction_started", "provider_called",
              "tool_called", "message_sent", "payment_executed",
              "external_crm_mutated", "outbox_released",
              "external_state_mutated"):
        assert o[f] is False


def test_decision_hash_reproducible():
    assert k.clean()["decision_hash"] == k.clean()["decision_hash"]


def test_demand_envelope_ordering():
    dem = k.clean()["demand_envelope"]
    for r in wi.DEMAND_RESOURCES:
        assert 0 <= dem["deterministic_floor"][r] <= dem["nominal"][r] <= \
            dem["safety_upper"][r]
    assert dem["unknown_is_zero"] is False


def test_unknown_demand_never_zero():
    dem = k.evaluate(demand_unknown=True)["demand_envelope"]
    assert all(v > 0 for v in dem["safety_upper"].values())


def test_prediction_cannot_reduce_floor():
    # A conformal upper below the deterministic floor never lowers safety_upper.
    o = k.evaluate(calibration_state="HEALTHY",
                   conformal_upper={r: 0 for r in wi.DEMAND_RESOURCES})
    dem = o["demand_envelope"]
    for r in wi.DEMAND_RESOURCES:
        assert dem["safety_upper"][r] >= dem["deterministic_floor"][r]
    assert dem["prediction_reduced_floor"] is False


def test_calibration_disabled_by_default():
    cal = k.clean()["calibration"]
    assert cal["calibration_state"] == "DISABLED"
    assert cal["fallback_applied"] is True
    assert cal["prediction_available_for_safety"] is False


def test_exact_retry_charges_nothing():
    snap = {"tenant_id": "t1", "existing_by_key": {
        ("t1", "idem-1"): {"work_item_id": "wi-1",
                           "canonical_request_hash": "H"}}}
    o = k.evaluate(snapshot=snap, canonical_request_hash="H")
    assert o["idempotency"]["idempotency_status"] == "EXACT_RETRY"
    assert o["charge_allowed"] is False
    assert o["disposition"] == "ADMIT_READY"


def test_conflict_same_key_different_request():
    snap = {"tenant_id": "t1", "existing_by_key": {
        ("t1", "idem-1"): {"work_item_id": "wi-1",
                           "canonical_request_hash": "H"}}}
    o = k.evaluate(snapshot=snap, canonical_request_hash="DIFFERENT")
    assert o["idempotency"]["idempotency_status"] == "CONFLICT"
    assert o["disposition"] == "CONFLICT"
    assert "IDEMPOTENCY_PAYLOAD_CONFLICT" in o["reason_codes"]


def test_bounded_model_check_holds():
    mc = wi.run_bounded_model_check()
    assert mc["all_invariants_hold"] is True
    assert mc["violations"] == []
    assert mc["invariant_count"] >= 12


def test_safety_denial_cannot_admit():
    # Optimization can never override a safety denial.
    o = k.evaluate(source_type="SLACK")
    assert o["safety_denied"] is True
    assert o["disposition"] != "ADMIT_READY"


# --- API layer -------------------------------------------------------------
def test_api_clean_admits_ready(gate):
    wid, o = gate.admitted_work()
    assert o["disposition"] == "ADMIT_READY"
    assert o["work_item"]["work_item_state"] == "READY"
    assert wid


def test_api_exact_retry(gate):
    body = gate.clean_work_intake(idempotency_key="fixed-1")
    o1 = gate.submit_work(body=body).json()
    o2 = gate.submit_work(body=dict(body)).json()
    assert o2["idempotency_status"] == "EXACT_RETRY"
    assert o2["charged"] is False
    assert o1["work_item"]["work_item_id"] == o2["work_item"]["work_item_id"]


def test_api_conflict(gate):
    body = gate.clean_work_intake(idempotency_key="fixed-2")
    gate.submit_work(body=body)
    o = gate.submit_work(body=dict(
        body, canonical_parameters={"target": "case:DIFFERENT"})).json()
    assert o["disposition"] == "CONFLICT"
    assert o["idempotency_status"] == "CONFLICT"


def test_api_events_projection_rebuild(gate):
    wid, _ = gate.admitted_work()
    ev = gate.wki(wid, "/events").json()
    assert ev["projection_rebuild"]["result"] == "PROJECTION_REBUILD_IDENTICAL"


def test_api_handoff_prepared_no_run(gate):
    wid, hr = gate.ready_to_handoff()
    hj = hr.json()
    assert hj["work_item"]["work_item_state"] == "HANDOFF_READY"
    assert hj["no_emp_a2_run_created"] is True
    assert hj["handoff_capability"]["capability_hash"]
    assert hj["handoff_capability"]["emp_a1_created_run"] is False


def test_api_policy_flags(gate):
    from tests.conftest import OWNER
    pol = gate.c.get("/ai-employee/work-inbox/policy",
                     headers=gate.h(OWNER)).json()
    assert pol["inbox_and_admission_only"] is True
    assert pol["creates_emp_a2_run"] is False
    assert pol["executes_work"] is False
    assert pol["calibration_enabled"] is False
    assert pol["production_ready"] is False
    assert pol["spec_revision"] == 8

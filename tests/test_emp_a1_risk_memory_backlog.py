"""EMP-A1 v1: Employee Work Inbox — modular risk budget (section 20),
admission memory (section 24), and the virtual backlog stability controller
(section 25).

The modular risk budget stays DORMANT until a calibrated predictor exists
(calibration HEALTHY); the total alpha error budget can never be increased.
Admission memory charges a shared base allowance per flow and defers over
capacity; an exact retry is never charged. The virtual backlog is an
ADMISSION-SIDE PROXY (estimated demand, not actual usage) — sustained
instability may defer even when one snapshot looks sufficient.
"""
from finalis.ai_employee import employee_work_inbox as wi
from tests import _emp_a1_kernel as k


# Backlog_state -> expected backlog reason code (section 25).
_BACKLOG_CODE = {
    "BACKLOG_STABLE": "WORK_ITEM_BACKLOG_STABLE",
    "BACKLOG_GROWING": "WORK_ITEM_BACKLOG_GROWING",
    "BACKLOG_PERSISTENTLY_UNSTABLE": "WORK_ITEM_BACKLOG_PERSISTENTLY_UNSTABLE",
    "BACKLOG_CAPACITY_UNKNOWN": "WORK_ITEM_BACKLOG_CAPACITY_UNKNOWN",
}


# --- kernel layer: modular risk budget (section 20) ------------------------
def test_rmb_risk_budget_dormant_when_disabled():
    rb = k.clean()["risk_budget"]
    assert rb["dormant"] is True
    assert rb["risk_budget_status"] == "RISK_BUDGET_AVAILABLE"


def test_rmb_alpha_total_never_increased():
    assert k.clean()["risk_budget"]["alpha_total_not_increased"] is True
    assert k.evaluate(calibration_state="HEALTHY")["risk_budget"][
        "alpha_total_not_increased"] is True


def test_rmb_risk_budget_active_when_healthy():
    rb = k.evaluate(calibration_state="HEALTHY")["risk_budget"]
    assert rb["dormant"] is False
    assert rb["risk_budget_status"] == "RISK_BUDGET_AVAILABLE"


def test_rmb_risk_budget_exhausted_defers():
    o = k.evaluate(calibration_state="HEALTHY",
                   risk_budget_status="RISK_BUDGET_EXHAUSTED")
    assert o["disposition"] == "DEFERRED_RISK"
    assert o["resulting_state"] == "DEFERRED_RISK"
    assert "WORK_ITEM_DEFERRED_RISK" in o["reason_codes"]


def test_rmb_risk_budget_exhausted_via_spent_units():
    o = k.evaluate(snapshot={"tenant_id": "t1",
                             "flow_state": {"risk_spent": 100}},
                   calibration_state="HEALTHY")
    assert o["risk_budget"]["risk_budget_status"] == "RISK_BUDGET_EXHAUSTED"
    assert o["disposition"] == "DEFERRED_RISK"


def test_rmb_risk_budget_unknown_reason_code():
    o = k.evaluate(calibration_state="HEALTHY",
                   risk_budget_status="RISK_BUDGET_UNKNOWN")
    assert o["risk_budget"]["risk_budget_status"] == "RISK_BUDGET_UNKNOWN"
    assert "WORK_ITEM_RISK_BUDGET_UNKNOWN" in o["reason_codes"]


def test_rmb_risk_budget_near_limit_does_not_defer():
    o = k.evaluate(snapshot={"tenant_id": "t1",
                             "flow_state": {"risk_spent": 85}},
                   calibration_state="HEALTHY")
    assert o["risk_budget"]["risk_budget_status"] == "RISK_BUDGET_NEAR_LIMIT"
    assert o["disposition"] == "ADMIT_READY"


# --- kernel layer: admission memory (section 24) ---------------------------
def test_rmb_admission_memory_exact_retry_no_charge():
    snap = {"tenant_id": "t1", "existing_by_key": {
        ("t1", "idem-1"): {"work_item_id": "wi-1",
                           "canonical_request_hash": "H"}}}
    o = k.evaluate(snapshot=snap, canonical_request_hash="H")
    assert o["admission_memory"]["admission_memory_state"] == \
        "UNCHANGED_EXACT_RETRY"
    assert o["admission_memory"]["defers"] is False
    assert o["charge_allowed"] is False
    assert o["disposition"] == "ADMIT_READY"


def test_rmb_admission_memory_over_capacity_defers():
    o = k.evaluate(snapshot={"tenant_id": "t1", "flow_state": {"memory": 99}})
    assert o["admission_memory"]["defers"] is True
    assert o["admission_memory"]["admission_memory_state"] == "DEFERRED"
    assert o["disposition"] == "DEFERRED_MEMORY"
    assert o["resulting_state"] == "DEFERRED_MEMORY"
    assert "DEFERRED_MEMORY" in o["reason_codes"]


def test_rmb_admission_memory_over_capacity_exceeds_capacity():
    mem = k.evaluate(snapshot={"tenant_id": "t1",
                               "flow_state": {"memory": 99}})["admission_memory"]
    assert mem["memory_after"] > mem["memory_capacity"]


def test_rmb_admission_memory_under_capacity_admits():
    o = k.evaluate(snapshot={"tenant_id": "t1", "flow_state": {"memory": 50}})
    assert o["admission_memory"]["defers"] is False
    assert o["disposition"] == "ADMIT_READY"


def test_rmb_admission_memory_shared_base_allowance():
    assert k.clean()["admission_memory"]["shared_base_allowance"] is True


# --- kernel layer: virtual backlog (section 25) ----------------------------
def test_rmb_virtual_backlog_admission_side_proxy():
    vb = k.clean()["virtual_backlog"]
    assert vb["admission_side_proxy"] is True


def test_rmb_backlog_stable_default():
    vb = k.clean()["virtual_backlog"]
    assert vb["backlog_state"] == "BACKLOG_STABLE"
    assert k.clean()["disposition"] == "ADMIT_READY"


def test_rmb_backlog_persistently_unstable_defers():
    o = k.evaluate(backlog_state="BACKLOG_PERSISTENTLY_UNSTABLE")
    assert o["disposition"] == "DEFERRED_CAPACITY"
    assert o["resulting_state"] == "DEFERRED_CAPACITY"
    assert "WORK_ITEM_BACKLOG_PERSISTENTLY_UNSTABLE" in o["reason_codes"]
    # Sustained instability defers even though one snapshot looks sufficient.
    assert o["virtual_backlog"]["defers_capacity"] is True
    assert o["virtual_backlog"]["admission_side_proxy"] is True


def test_rmb_backlog_growing_reason_code():
    o = k.evaluate(backlog_state="BACKLOG_GROWING")
    assert o["virtual_backlog"]["reason_code"] == "WORK_ITEM_BACKLOG_GROWING"
    assert "WORK_ITEM_BACKLOG_GROWING" in o["reason_codes"]
    assert o["disposition"] == "ADMIT_READY"


def test_rmb_backlog_capacity_unknown_reason_code():
    o = k.evaluate(backlog_state="BACKLOG_CAPACITY_UNKNOWN")
    assert o["virtual_backlog"]["reason_code"] == \
        "WORK_ITEM_BACKLOG_CAPACITY_UNKNOWN"
    assert "WORK_ITEM_BACKLOG_CAPACITY_UNKNOWN" in o["reason_codes"]


def test_rmb_backlog_every_state_maps_its_reason_code():
    for state in wi.BACKLOG_STATES:
        o = k.evaluate(backlog_state=state)
        assert o["virtual_backlog"]["backlog_state"] == state
        assert o["virtual_backlog"]["reason_code"] == _BACKLOG_CODE[state]
        assert _BACKLOG_CODE[state] in o["reason_codes"]


def test_rmb_backlog_proxy_true_across_states():
    for state in wi.BACKLOG_STATES:
        assert k.evaluate(backlog_state=state)["virtual_backlog"][
            "admission_side_proxy"] is True


# --- API layer -------------------------------------------------------------
def test_rmb_api_risk_endpoint(gate):
    from tests.conftest import OWNER
    r = gate.c.get("/ai-employee/work-inbox/risk", headers=gate.h(OWNER))
    assert r.status_code == 200
    j = r.json()
    assert j["risk_budget_states"] == wi.RISK_BUDGET_STATES
    assert j["calibration_enabled"] is False
    assert j["alpha_total_not_increasable"] is True


def test_rmb_api_flow_state_endpoint(gate):
    from tests.conftest import OWNER
    r = gate.c.get("/ai-employee/work-inbox/flow-state", headers=gate.h(OWNER))
    assert r.status_code == 200
    assert isinstance(r.json()["flows"], list)


def test_rmb_api_flow_state_honesty_labels(gate):
    from tests.conftest import OWNER
    j = gate.c.get("/ai-employee/work-inbox/flow-state",
                   headers=gate.h(OWNER)).json()
    labels = j["honesty_labels"]
    assert "VIRTUAL_BACKLOG_IS_ADMISSION_SIDE_PROXY" in labels
    assert "ESTIMATED_DEMAND_NOT_ACTUAL_USAGE" in labels

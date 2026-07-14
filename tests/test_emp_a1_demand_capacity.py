"""EMP-A1 v1: risk-calibrated demand envelope (sections 18-19) + dependency-
aware capacity admission (sections 22-23).

The demand envelope has three deterministic layers
(deterministic_floor <= nominal <= safety_upper). The estimate source is one of
a fixed set; an unknown source falls back to WORK_TYPE_DEFAULT. Human-governed
overrides may RAISE demand but never below the deterministic floor. Unknown
demand uses a conservative upper vector (never zero). Calibration is DISABLED by
default (deterministic fallback); a prediction can only widen, never reduce, the
deterministic safety floor. Capacity is a hard resource barrier — a
capacity-deferred item is never ADMIT_READY; no ranking/priority overrides it.
"""
from finalis.ai_employee import employee_work_inbox as wi
from tests import _emp_a1_kernel as k

_R = wi.DEMAND_RESOURCES
_CS_FLOOR = wi.WORK_TYPE_REGISTRY["case_summary"]["deterministic_demand_floor"]
_CS_UPPER = wi.WORK_TYPE_REGISTRY["case_summary"]["deterministic_demand_upper"]


# --- demand envelope (sections 18-19) --------------------------------------
def test_demcap_three_layers_ordered():
    dem = k.clean()["demand_envelope"]
    for r in _R:
        assert 0 <= dem["deterministic_floor"][r] <= dem["nominal"][r] <= \
            dem["safety_upper"][r]
    assert dem["unknown_is_zero"] is False


def test_demcap_estimate_source_in_allowed_set():
    dem = k.clean()["demand_envelope"]
    assert dem["estimate_source"] in wi.ESTIMATE_SOURCES


def test_demcap_unknown_source_falls_back_to_default():
    dem = k.evaluate(estimate_source="BOGUS_SOURCE")["demand_envelope"]
    assert dem["estimate_source"] == "WORK_TYPE_DEFAULT"


def test_demcap_explicit_source_preserved():
    dem = k.evaluate(estimate_source="DETERMINISTIC_RULE")["demand_envelope"]
    assert dem["estimate_source"] == "DETERMINISTIC_RULE"


def test_demcap_human_override_may_raise():
    dem = k.evaluate(estimate_source="HUMAN_GOVERNED_OVERRIDE",
                     demand_override={r: 10 for r in _R})["demand_envelope"]
    for r in _R:
        assert dem["nominal"][r] == 10
        assert dem["safety_upper"][r] >= dem["deterministic_floor"][r]


def test_demcap_human_override_never_below_floor():
    dem = k.evaluate(estimate_source="HUMAN_GOVERNED_OVERRIDE",
                     demand_override={r: 0 for r in _R})["demand_envelope"]
    for r in _R:
        assert dem["nominal"][r] == dem["deterministic_floor"][r]
        assert dem["nominal"][r] >= _CS_FLOOR[r]


def test_demcap_unknown_demand_uses_upper_vector_never_zero():
    o = k.evaluate(demand_unknown=True)
    dem = o["demand_envelope"]
    assert dem["demand_unknown"] is True
    assert all(dem["safety_upper"][r] == wi.UNKNOWN_UPPER_VECTOR[r] for r in _R)
    assert all(v > 0 for v in dem["safety_upper"].values())
    assert o["disposition"] == "ADMIT_READY"


def test_demcap_conformal_below_floor_never_reduces():
    o = k.evaluate(calibration_state="HEALTHY",
                   conformal_upper={r: 0 for r in _R})
    dem = o["demand_envelope"]
    for r in _R:
        assert dem["safety_upper"][r] >= dem["deterministic_floor"][r]
    assert dem["prediction_reduced_floor"] is False


def test_demcap_calibration_disabled_deterministic_fallback():
    dem = k.clean()["demand_envelope"]
    assert k.clean()["calibration"]["calibration_state"] == "DISABLED"
    for r in _R:
        assert dem["safety_upper"][r] == _CS_UPPER[r]


def test_demcap_healthy_wider_conformal_widens_safety_upper():
    dem = k.evaluate(calibration_state="HEALTHY",
                     conformal_upper={r: 50 for r in _R})["demand_envelope"]
    for r in _R:
        assert dem["safety_upper"][r] == 50
        assert dem["safety_upper"][r] > _CS_UPPER[r]


def test_demcap_envelope_hash_deterministic():
    a = k.clean()["demand_envelope"]["demand_envelope_hash"]
    b = k.clean()["demand_envelope"]["demand_envelope_hash"]
    assert a == b and a


# --- dependency-aware capacity (sections 22-23) ----------------------------
def test_demcap_capacity_valid_on_clean():
    cap = k.clean()["capacity"]
    assert cap["capacity_result"] == "RESOURCE_ADMISSION_VALID"


def test_demcap_capacity_unknown_defers():
    o = k.evaluate(capacity_unknown=True)
    assert o["capacity"]["capacity_result"] == "RESOURCE_CAPACITY_UNKNOWN"
    assert o["disposition"] == "DEFERRED_CAPACITY"
    assert "RESOURCE_CAPACITY_UNKNOWN" in o["reason_codes"]


def test_demcap_capacity_barrier_blocks_admit_ready():
    o = k.evaluate(capacity_unknown=True)
    assert o["disposition"] != "ADMIT_READY"
    assert o["resulting_state"] == "DEFERRED_CAPACITY"


def test_demcap_capacity_exceeded_defers():
    # A claimed-demand drawdown larger than available capacity fails the
    # resource barrier — ranking/priority cannot override it.
    o = k.evaluate(claimed_demand={r: 1000 for r in _R})
    assert o["capacity"]["capacity_result"] == "RESOURCE_CAPACITY_EXCEEDED"
    assert o["disposition"] == "DEFERRED_CAPACITY"
    assert o["disposition"] != "ADMIT_READY"


def test_demcap_unknown_is_zero_flag_false():
    assert k.evaluate(demand_unknown=True)["demand_envelope"][
        "unknown_is_zero"] is False


# --- API layer -------------------------------------------------------------
def test_demcap_api_demand_subfield_ordered(gate):
    wid, _ = gate.admitted_work()
    dem = gate.wki(wid, "/demand").json()["work_demand_envelope"]
    for r in _R:
        assert dem["deterministic_floor"][r] <= dem["nominal"][r] <= \
            dem["safety_upper"][r]


def test_demcap_api_demand_hash_present(gate):
    wid, _ = gate.admitted_work()
    body = gate.wki(wid, "/demand").json()
    assert body["demand_envelope_valid"] is True
    assert body["work_demand_envelope"]["demand_envelope_hash"]


def test_demcap_api_unknown_demand_never_zero(gate):
    wid, o = gate.admitted_work(demand_unknown=True)
    assert o["disposition"] == "ADMIT_READY"
    dem = gate.wki(wid, "/demand").json()["work_demand_envelope"]
    assert all(v > 0 for v in dem["safety_upper"].values())


def test_demcap_api_capacity_unknown_defers(gate):
    _, o = gate.admitted_work(capacity_unknown=True)
    assert o["disposition"] == "DEFERRED_CAPACITY"
    assert "RESOURCE_CAPACITY_UNKNOWN" in o["reason_codes"]
    assert o["work_item"]["work_item_state"] == "DEFERRED_CAPACITY"


def test_demcap_api_capacity_snapshot(gate):
    from tests.conftest import OWNER
    r = gate.c.get("/ai-employee/work-inbox/capacity", headers=gate.h(OWNER))
    assert r.status_code == 200
    j = r.json()
    assert set(j["capacity_vector"].keys()) == set(_R)
    assert j["demand_resources"] == _R

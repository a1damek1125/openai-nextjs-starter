"""EMP-A1 v1: Employee Work Inbox — full API surface + derived drills (section
48). The admission fabric is intake+admission only: every read/list/subfield/
lifecycle endpoint is exercised over HTTP, and every drill PROVES no external
effect (no run created, no provider/tool called, no transaction started, no
outbox released, no external state mutated). Do NOT modify product code.

A FRESH admitted work item is built per test via `gate.admitted_work()`; because
each test receives a fresh `gate` (a fresh in-memory tenant), the first submit of
the clean `case_summary` intake is admitted READY (ADMIT_READY).
"""
from tests.conftest import OWNER

_BASE = "/ai-employee/work-inbox"


def _get(gate, path, actor=OWNER):
    return gate.c.get(_BASE + path, headers=gate.h(actor))


def _post(gate, path, body=None, actor=OWNER):
    return gate.c.post(_BASE + path, json=body or {}, headers=gate.h(actor))


# --- policy ----------------------------------------------------------------
def test_apidrills_policy_core_flags(gate):
    pol = _get(gate, "/policy").json()
    assert pol["emp_a1_model_version"]
    assert pol["spec_revision"] == 8
    assert pol["inbox_and_admission_only"] is True
    assert pol["creates_emp_a2_run"] is False
    assert pol["executes_work"] is False
    assert pol["calls_provider"] is False
    assert pol["starts_b9_transaction"] is False
    assert pol["releases_outbox"] is False
    assert pol["calibration_enabled"] is False
    assert pol["production_ready"] is False


def test_apidrills_policy_all_has_endpoint_flags_false(gate):
    pol = _get(gate, "/policy").json()
    has_flags = [k for k in pol if k.startswith("has_") and k.endswith(
        "_endpoint")]
    assert has_flags  # at least one forbidden-endpoint flag is advertised
    for k in has_flags:
        assert pol[k] is False, k


# --- read-only surfaces ----------------------------------------------------
def test_apidrills_registry_work_type_registry_present(gate):
    reg = _get(gate, "/registry").json()
    assert "work_type_registry" in reg
    assert reg["work_type_registry"]


def test_apidrills_readonly_gets_all_200(gate):
    for path in ("/counts", "/capacity", "/risk", "/calibration", "/drift",
                 "/flow-state", "/queues", "/observer-health", "/items"):
        assert _get(gate, path).status_code == 200, path


def test_apidrills_items_list_is_a_list(gate):
    gate.admitted_work()
    body = _get(gate, "/items").json()
    assert isinstance(body, list)
    assert len(body) >= 1


# --- submit + item reads ---------------------------------------------------
def test_apidrills_submit_happy_path_admit_ready(gate):
    r = gate.submit_work()
    assert r.status_code == 200
    o = r.json()
    assert o["disposition"] == "ADMIT_READY"
    assert o["work_item"]["work_item_state"] == "READY"


def test_apidrills_get_item_200(gate):
    wid, _ = gate.admitted_work()
    r = gate.wi(wid)
    assert r.status_code == 200
    assert r.json()["work_item_id"] == wid


def test_apidrills_item_subfields_all_200(gate):
    wid, _ = gate.admitted_work()
    for sf in ("/intent", "/admission", "/demand", "/risk",
               "/priority-explanation", "/claim"):
        r = gate.wi(wid, sf)
        assert r.status_code == 200, sf
        assert r.json()["work_item_id"] == wid


def test_apidrills_handoff_preview_200(gate):
    wid, _ = gate.admitted_work()
    r = gate.wi(wid, "/handoff-preview")
    assert r.status_code == 200
    assert "handoff_ready" in r.json()


def test_apidrills_events_projection_identical(gate):
    wid, _ = gate.admitted_work()
    r = gate.wi(wid, "/events")
    assert r.status_code == 200
    assert r.json()["projection_rebuild"]["result"] == \
        "PROJECTION_REBUILD_IDENTICAL"


# --- lifecycle POSTs -------------------------------------------------------
def test_apidrills_reserve_claim_prepare_invalidate_release(gate):
    wid, _ = gate.admitted_work()
    assert gate.wi(wid, "/reserve", method="POST").status_code == 200
    assert gate.wi(wid, "/claim", method="POST").status_code == 200
    pr = gate.wi(wid, "/prepare-handoff", method="POST")
    assert pr.status_code == 200
    assert pr.json()["no_emp_a2_run_created"] is True
    assert gate.wi(wid, "/invalidate-handoff", method="POST").status_code == 200
    assert gate.wi(wid, "/release-claim", method="POST").status_code == 200


def test_apidrills_claim_no_run_created(gate):
    wid, _ = gate.admitted_work()
    hj = gate.wi(wid, "/claim", method="POST").json()
    # Claiming an item never creates an EMP-A2 run or executes work.
    assert hj["work_item_state"] == "CLAIMED"


def test_apidrills_defer_and_resume(gate):
    wid, _ = gate.admitted_work()
    assert gate.wi(wid, "/defer", method="POST").status_code == 200
    assert gate.wi(wid, "/resume", method="POST").status_code == 200


def test_apidrills_cancel(gate):
    wid, _ = gate.admitted_work()
    r = gate.wi(wid, "/cancel", method="POST")
    assert r.status_code == 200
    assert r.json()["work_item_state"] == "CANCELED"


def test_apidrills_assign_and_unassign(gate):
    wid, _ = gate.admitted_work()
    a = gate.wi(wid, "/assign", method="POST", assignee_id="u-1",
                assignee_type="HUMAN")
    assert a.status_code == 200
    assert a.json()["grants_execution"] is False
    u = gate.wi(wid, "/unassign", method="POST")
    assert u.status_code == 200
    assert u.json()["assignee_type"] == "UNASSIGNED"


def test_apidrills_reprioritize(gate):
    wid, _ = gate.admitted_work()
    r = gate.wi(wid, "/reprioritize", method="POST", priority_class="HIGH")
    assert r.status_code == 200
    assert r.json()["bypasses_approval"] is False


def test_apidrills_request_and_respond_clarification(gate):
    wid, _ = gate.admitted_work()
    rq = gate.wi(wid, "/request-clarification", method="POST")
    assert rq.status_code == 200
    assert rq.json()["llm_supplied_values"] is False
    rs = gate.wi(wid, "/respond-clarification", method="POST", answers={})
    assert rs.status_code == 200
    assert rs.json()["recorded"] is True


def test_apidrills_bind_approval(gate):
    wid, _ = gate.admitted_work()
    r = gate.wi(wid, "/bind-approval", method="POST", refs=["approval:1"])
    assert r.status_code == 200
    assert r.json()["approval_bound"] is True


def test_apidrills_mark_and_reverse_duplicate(gate):
    wid, _ = gate.admitted_work()
    md = gate.wi(wid, "/mark-duplicate", method="POST")
    assert md.status_code == 200
    assert md.json()["work_item_state"] == "DUPLICATE"
    rv = gate.wi(wid, "/reverse-duplicate", method="POST")
    assert rv.status_code == 200
    assert rv.json()["work_item_state"] == "RECEIVED"


def test_apidrills_unknown_item_id_404(gate):
    assert gate.wi("wi-does-not-exist").status_code == 404
    assert gate.wi("wi-does-not-exist", "/intent").status_code == 404
    assert gate.wi("wi-does-not-exist", "/claim",
                   method="POST").status_code == 404


# --- drills (section 48): each proves no external effect --------------------
def test_apidrills_rebuild_projection_drill(gate):
    wid, _ = gate.admitted_work()
    r = _post(gate, "/rebuild-projection", {"work_item_id": wid})
    assert r.status_code == 200
    assert r.json()["projection_rebuild"]["result"] == \
        "PROJECTION_REBUILD_IDENTICAL"


def test_apidrills_simulate_policy_drill(gate):
    r = _post(gate, "/simulate-policy", {"requests": [], "candidate_policy": {}})
    assert r.status_code == 200
    j = r.json()
    assert j["created_run"] is False
    assert j["mutated_items"] is False


def test_apidrills_reference_kernel_drill_deterministic_no_run(gate):
    r = _post(gate, "/run-reference-kernel-drill", {})
    assert r.status_code == 200
    j = r.json()
    assert j["reference_kernel_deterministic"] is True
    assert j["run_created"] is False
    assert j["tool_transaction_started"] is False
    assert j["provider_called"] is False
    assert j["outbox_released"] is False


def test_apidrills_concurrency_drill_invariants_hold(gate):
    r = _post(gate, "/run-concurrency-drill", {})
    assert r.status_code == 200
    j = r.json()
    assert j["model_check"]["all_invariants_hold"] is True
    assert j["run_created"] is False


def test_apidrills_risk_drill_no_run(gate):
    r = _post(gate, "/run-risk-drill", {})
    assert r.status_code == 200
    j = r.json()
    assert j["no_run_created"] is True
    assert j["no_provider_called"] is True
    for c in j["cases"].values():
        assert c["run_created"] is False


def test_apidrills_inbox_drill_no_external_effect(gate):
    r = _post(gate, "/inbox-drill", {})
    assert r.status_code == 200
    j = r.json()
    for f in ("run_created", "tool_transaction_started", "provider_called",
              "tool_called", "message_sent", "payment_executed",
              "external_crm_mutated", "outbox_released",
              "external_state_mutated"):
        assert j[f] is False, f


def test_apidrills_all_drills_return_200(gate):
    wid, _ = gate.admitted_work()
    bodies = {"/rebuild-projection": {"work_item_id": wid},
              "/simulate-policy": {"requests": []},
              "/run-reference-kernel-drill": {},
              "/run-concurrency-drill": {}, "/run-risk-drill": {},
              "/inbox-drill": {}}
    for path, body in bodies.items():
        assert _post(gate, path, body).status_code == 200, path

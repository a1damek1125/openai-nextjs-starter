"""EMP-A1 v1: work-item state machine (section 13), reservation/fenced claim
(section 37), and single-use EMP-A2 handoff (sections 38-39).

The fabric admits and prepares exactly ONE fenced single-use handoff capability
for EMP-A2 WITHOUT executing work: it never creates an EMP-A2 run, never enters a
forbidden execution state, and the raw claim nonce never surfaces. Transitions
fail closed; claims use compare-and-swap with monotonic fencing.
"""
from finalis.ai_employee import employee_work_inbox as wi


# --- state machine: allowed forward transitions (section 13) ---------------
def test_sch_received_to_validating_allowed():
    assert wi.is_transition_allowed("RECEIVED", "VALIDATING") is True


def test_sch_validating_to_ready_allowed():
    assert wi.is_transition_allowed("VALIDATING", "READY") is True


def test_sch_ready_to_reserved_and_claimed_allowed():
    assert wi.is_transition_allowed("READY", "RESERVED") is True
    assert wi.is_transition_allowed("READY", "CLAIMED") is True


def test_sch_reserved_to_claimed_allowed():
    assert wi.is_transition_allowed("RESERVED", "CLAIMED") is True


def test_sch_claimed_to_handoff_ready_allowed():
    assert wi.is_transition_allowed("CLAIMED", "HANDOFF_READY") is True


def test_sch_forbidden_states_membership():
    # EMP-A1 may never enter any execution state.
    assert wi.FORBIDDEN_STATES == {
        "RUNNING", "EXECUTING", "COMPLETED", "FAILED_EXECUTION", "RECOVERING",
        "ROLLED_BACK"}


def test_sch_forbidden_states_never_reachable_from_any_source():
    for dst in wi.FORBIDDEN_STATES:
        for src in wi.WORK_ITEM_STATES:
            assert wi.is_transition_allowed(src, dst) is False


def test_sch_terminal_states_have_no_outgoing_transitions():
    for terminal in ("REJECTED", "CANCELED", "SUPERSEDED", "QUARANTINED",
                     "EXPIRED"):
        assert wi.ALLOWED_TRANSITIONS[terminal] == set()
        for dst in wi.WORK_ITEM_STATES:
            assert wi.is_transition_allowed(terminal, dst) is False


def test_sch_unknown_source_state_fails_closed():
    assert wi.is_transition_allowed("NOT_A_STATE", "READY") is False


def test_sch_ready_cannot_jump_to_handoff_ready():
    # Only CLAIMED may reach HANDOFF_READY (fail closed).
    assert wi.is_transition_allowed("READY", "HANDOFF_READY") is False


# --- API: reservation + fenced claim (section 37) --------------------------
def test_sch_api_claim_sets_claimed_and_fencing_token(gate):
    wid, _ = gate.admitted_work()
    r = gate.wki(wid, "/claim", method="POST")
    assert r.status_code == 200
    j = r.json()
    assert j["work_item_state"] == "CLAIMED"
    assert j["active_fencing_token"] == 1


def test_sch_api_second_concurrent_claim_conflicts(gate):
    wid, _ = gate.admitted_work()
    r1 = gate.wki(wid, "/claim", method="POST")
    assert r1.status_code == 200
    r2 = gate.wki(wid, "/claim", method="POST")
    assert r2.status_code == 409
    detail = r2.json()["detail"]
    assert (detail.get("reason_code") == "CLAIM_CONFLICT"
            or detail.get("error") in ("claim_conflict", "not_claimable"))
    # The prior claim survives; fencing is not re-issued.
    assert gate.wki(wid).json()["work_item_state"] == "CLAIMED"


def test_sch_api_fencing_first_token_is_one(gate):
    wid, _ = gate.admitted_work()
    j = gate.wki(wid, "/claim", method="POST").json()
    assert j["active_fencing_token"] == 1


def test_sch_api_reserve_then_claim(gate):
    wid, _ = gate.admitted_work()
    rr = gate.wki(wid, "/reserve", method="POST")
    assert rr.status_code == 200
    assert rr.json()["work_item_state"] == "RESERVED"
    rc = gate.wki(wid, "/claim", method="POST")
    assert rc.status_code == 200
    assert rc.json()["work_item_state"] == "CLAIMED"
    assert rc.json()["active_fencing_token"] == 1


def test_sch_api_release_claim_returns_to_ready(gate):
    wid, _ = gate.admitted_work()
    gate.wki(wid, "/claim", method="POST")
    rel = gate.wki(wid, "/release-claim", method="POST")
    assert rel.status_code == 200
    assert rel.json()["work_item_state"] == "READY"


def test_sch_api_release_claim_invalidates_handoff(gate):
    wid, hr = gate.ready_to_handoff()
    assert hr.json()["work_item"]["work_item_state"] == "HANDOFF_READY"
    rel = gate.wki(wid, "/release-claim", method="POST")
    assert rel.status_code == 200
    # The handoff no longer holds the item; it is back to READY.
    assert gate.wki(wid).json()["work_item_state"] == "READY"


# --- API: single-use handoff (sections 38-39) ------------------------------
def test_sch_api_prepare_handoff_requires_claimed(gate):
    wid, _ = gate.admitted_work()  # READY, not CLAIMED
    r = gate.wki(wid, "/prepare-handoff", method="POST")
    assert r.status_code == 409


def test_sch_api_handoff_capability_fields(gate):
    wid, hr = gate.ready_to_handoff()
    hj = hr.json()
    assert hj["no_emp_a2_run_created"] is True
    cap = hj["handoff_capability"]
    assert cap["capability_hash"]
    assert cap["intended_consumer"] == "EMP-A2"
    assert cap["state"] == "PREPARED"
    assert cap["emp_a1_created_run"] is False
    assert cap["consumed_by_emp_a1"] is False


def test_sch_api_handoff_labels_declare_no_run_or_execution(gate):
    _, hr = gate.ready_to_handoff()
    labels = hr.json()["labels"]
    for lbl in ("NO_EMP_A2_RUN_CREATED", "NO_EXECUTION_STARTED",
                "DEADLINE_NOT_GUARANTEED"):
        assert lbl in labels


def test_sch_api_handoff_never_surfaces_raw_nonce(gate):
    _, hr = gate.ready_to_handoff()
    hj = hr.json()
    # Only hashes surface — no top-level raw nonce, none inside the capability.
    assert "nonce" not in hj
    assert "nonce" not in hj["handoff_capability"]


def test_sch_api_handoff_item_state_is_handoff_ready(gate):
    _, hr = gate.ready_to_handoff()
    assert hr.json()["work_item"]["work_item_state"] == "HANDOFF_READY"


def test_sch_api_invalidate_handoff_returns_to_claimed(gate):
    wid, _ = gate.ready_to_handoff()
    iv = gate.wki(wid, "/invalidate-handoff", method="POST")
    assert iv.status_code == 200
    assert iv.json()["handoff_invalidated"] is True
    assert gate.wki(wid).json()["work_item_state"] == "CLAIMED"


def test_sch_api_stale_claimant_cannot_prepare_handoff(gate):
    wid, _ = gate.admitted_work()
    gate.wki(wid, "/claim", method="POST")
    gate.wki(wid, "/release-claim", method="POST")  # claim released -> READY
    r = gate.wki(wid, "/prepare-handoff", method="POST")
    assert r.status_code == 409

"""TOOL-B9.2 v5: Schedule and Heartbeat Run Chain (section 8) — a scheduled
occurrence resolves to a deterministic logical run; duplicate delivery of the
same payload is the same run (safe); a changed payload, a missed occurrence or a
revoked/disabled schedule degrade; approving a schedule is not approving each run.

The run chain is derived evidence only: a schedule occurrence is not authority
and a disabled schedule cannot create a valid run.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from tests import _b92_kernel as k


def _sched(over):
    base = {"trigger_type": "SCHEDULE_OCCURRENCE", "schedule_id": "s1"}
    base.update(over)
    return k.prepare(**base)


def _sched_degrades(over, expected_signal):
    o = _sched(over)
    assert o["proof_of_work_outcome_valid"] is False
    assert o["work_run_state"] != "WORK_OUTCOME_CERTIFIED"
    assert expected_signal in o["all_signals"]
    # No external effect ever, even on a degraded schedule chain.
    assert o["produced_external_effect"] is False
    assert o["outbox_released"] is False
    return o


# --- kernel layer ----------------------------------------------------------
def test_schedule_logical_run_key_deterministic():
    a = k.prepare(schedule_id="s1", scheduled_for="2026-07-01T09:00:00",
                  work_definition_version="wd-v3")
    b = k.prepare(schedule_id="s1", scheduled_for="2026-07-01T09:00:00",
                  work_definition_version="wd-v3")
    assert a["schedule_run_chain"]["logical_run_key"] == \
        b["schedule_run_chain"]["logical_run_key"]


def test_schedule_logical_run_key_varies_with_inputs():
    base = k.prepare(schedule_id="s1", scheduled_for="T0",
                     work_definition_version="v1")["schedule_run_chain"][
                         "logical_run_key"]
    other_sid = k.prepare(schedule_id="s2", scheduled_for="T0",
                          work_definition_version="v1")["schedule_run_chain"][
                              "logical_run_key"]
    other_time = k.prepare(schedule_id="s1", scheduled_for="T1",
                           work_definition_version="v1")["schedule_run_chain"][
                               "logical_run_key"]
    other_ver = k.prepare(schedule_id="s1", scheduled_for="T0",
                          work_definition_version="v2")["schedule_run_chain"][
                              "logical_run_key"]
    assert len({base, other_sid, other_time, other_ver}) == 4


def test_schedule_duplicate_same_payload_same_logical_run():
    o = _sched({"schedule_duplicate_delivery": True})
    chain = o["schedule_run_chain"]
    assert chain["duplicate_delivery"] is True
    assert chain["same_logical_run_on_duplicate"] is True
    # Same logical run, still proven and certified.
    assert o["work_run_state"] == "WORK_OUTCOME_CERTIFIED"
    assert o["work_outcome_truth_state"] == "PROVEN"
    assert o["proof_of_work_outcome_valid"] is True


def test_schedule_duplicate_changed_payload_blocks():
    o = _sched_degrades({"schedule_duplicate_changed_payload": True},
                        "SCHEDULE_OCCURRENCE_DUPLICATE")
    assert o["work_outcome_truth_state"] == "PARTIAL"
    assert o["work_outcome_certified"] is False


def test_schedule_missed_occurrence_degrades():
    o = _sched_degrades({"schedule_missed": True}, "SCHEDULE_OCCURRENCE_MISSED")
    assert o["work_outcome_truth_state"] == "PARTIAL"


def test_schedule_revoked_rejected():
    o = _sched_degrades({"schedule_revoked": True}, "SCHEDULE_OCCURRENCE_REVOKED")
    assert o["work_run_state"] == "REJECTED"
    assert o["work_outcome_truth_state"] == "REVOKED"


def test_schedule_disabled_cannot_create_valid_run():
    # A disabled schedule cannot create a valid run.
    o = _sched_degrades({"schedule_disabled": True},
                        "SCHEDULE_OCCURRENCE_REVOKED")
    assert o["work_run_state"] == "REJECTED"
    assert o["schedule_run_chain"]["revoked"] is True


def test_schedule_is_not_approval():
    # Approving a schedule is not approving each run it spawns.
    chain = _sched({})["schedule_run_chain"]
    assert chain["schedule_is_approval"] is False


def test_schedule_non_scheduled_clean_run_chain_valid():
    chain = k.clean_outcome()["schedule_run_chain"]
    assert chain["is_scheduled"] is False
    assert chain["chain_status"] == "VALID"
    assert chain["signal"] is None


def test_schedule_marks_scheduled_run():
    chain = _sched({})["schedule_run_chain"]
    assert chain["is_scheduled"] is True
    assert chain["schedule_id"] == "s1"
    assert chain["chain_status"] == "VALID"


def test_schedule_timezone_and_calendar_rule_present():
    chain = _sched({"timezone": "America/New_York",
                    "calendar_rule": "FREQ=DAILY"})["schedule_run_chain"]
    assert chain["timezone"] == "America/New_York"
    assert chain["calendar_rule_hash"]


def test_schedule_timezone_does_not_change_logical_run_key():
    # A DST/timezone occurrence must not change the logical run key when
    # scheduled_for is unchanged.
    utc = k.prepare(schedule_id="s1", scheduled_for="2026-03-08T02:30:00",
                    work_definition_version="wd-v1")
    tz = k.prepare(schedule_id="s1", scheduled_for="2026-03-08T02:30:00",
                   work_definition_version="wd-v1",
                   timezone="America/New_York")
    assert utc["schedule_run_chain"]["logical_run_key"] == \
        tz["schedule_run_chain"]["logical_run_key"]


def test_schedule_run_chain_hash_recompute():
    chain = _sched({})["schedule_run_chain"]
    assert _core_hash(chain, "schedule_run_chain_hash", "signal") == \
        chain["schedule_run_chain_hash"]


def test_schedule_hash_changes_on_degradation():
    clean = _sched({})["schedule_run_chain"]["schedule_run_chain_hash"]
    bad = _sched({"schedule_revoked": True})["schedule_run_chain"][
        "schedule_run_chain_hash"]
    assert clean != bad


# --- API layer -------------------------------------------------------------
def test_schedule_api_subfield_endpoint(gate):
    wrid, _ = gate.observed_work()
    chain = gate.wo(wrid, "schedule-lineage").json()["schedule_run_chain"]
    assert chain["chain_status"] == "VALID"
    assert chain["schedule_is_approval"] is False


def test_schedule_api_logical_run_key_present(gate):
    wrid, _ = gate.observed_work()
    body = gate.wo(wrid, "schedule-lineage").json()
    assert body["work_run_id"] == wrid
    assert body["honesty_labels"]
    assert body["schedule_run_chain"]["logical_run_key"]

"""TOOL-B9.2 v5: Work Origin Envelope (section 6) + trigger types — a work run
is bound to how it was triggered; a trigger is not authority and a message is not
approval; missing/ambiguous origin degrades; a heartbeat suggestion cannot
execute directly.

The origin envelope is derived evidence only: it records the trigger, never
grants execution/approval authority.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from finalis.ai_employee import tool_work_observability as wo
from tests import _b92_kernel as k


def _origin_degrades(over, expected_signal):
    o = k.prepare(**over)
    assert o["proof_of_work_outcome_valid"] is False
    assert o["work_run_state"] != "WORK_OUTCOME_CERTIFIED"
    assert expected_signal in o["all_signals"]
    # No external effect ever, even on a degraded origin.
    assert o["produced_external_effect"] is False
    assert o["outbox_released"] is False
    return o


# --- kernel layer ----------------------------------------------------------
def test_origin_clean_envelope_valid():
    we = k.clean_outcome()["work_origin"]
    assert we["origin_status"] == "VALID"
    assert we["signal"] is None


def test_origin_trigger_is_not_authority():
    we = k.clean_outcome()["work_origin"]
    assert we["trigger_is_authority"] is False


def test_origin_message_is_not_approval():
    we = k.clean_outcome()["work_origin"]
    assert we["message_is_approval"] is False


def test_origin_every_trigger_type_accepted():
    for tt in wo.TRIGGER_TYPES:
        o = k.prepare(trigger_type=tt)
        we = o["work_origin"]
        assert we["trigger_type"] == tt
        assert we["origin_status"] == "VALID"
        assert o["work_run_state"] == "WORK_OUTCOME_CERTIFIED"


def test_origin_non_authoritative_triggers_marked_not_authority():
    expected = {"SCHEDULE_OCCURRENCE", "HEARTBEAT_SUGGESTION_APPROVED",
                "FUTURE_A2A_REQUEST", "FUTURE_MCP_EVENT"}
    assert wo.NON_AUTHORITATIVE_TRIGGERS == expected
    for tt in expected:
        we = k.prepare(trigger_type=tt)["work_origin"]
        assert we["authority_status"] == "NOT_AUTHORITY"


def test_origin_authoritative_triggers_marked_trigger_only():
    for tt in wo.TRIGGER_TYPES:
        if tt in wo.NON_AUTHORITATIVE_TRIGGERS:
            continue
        we = k.prepare(trigger_type=tt)["work_origin"]
        assert we["authority_status"] == "TRIGGER_ONLY"


def test_origin_unknown_trigger_type_ambiguous():
    o = _origin_degrades({"trigger_type": "MADE_UP_TRIGGER"},
                         "WORK_ORIGIN_AMBIGUOUS")
    assert o["work_outcome_truth_state"] == "PARTIAL"


def test_origin_missing_degrades():
    o = _origin_degrades({"origin_missing": True}, "WORK_ORIGIN_MISSING")
    assert o["work_origin"]["origin_status"] == "INVALID"


def test_origin_ambiguous_degrades():
    o = _origin_degrades({"origin_ambiguous": True}, "WORK_ORIGIN_AMBIGUOUS")
    assert o["work_origin"]["origin_status"] == "INVALID"


def test_origin_heartbeat_direct_execution_rejected():
    # A heartbeat suggestion is not authority — it cannot execute directly.
    o = _origin_degrades(
        {"trigger_type": "HEARTBEAT_SUGGESTION_APPROVED",
         "heartbeat_direct_execution": True},
        "HEARTBEAT_DIRECT_EXECUTION_REJECTED")
    assert o["work_origin"]["origin_status"] == "INVALID"


def test_origin_envelope_hash_recompute():
    we = k.clean_outcome()["work_origin"]
    assert _core_hash(we, "origin_envelope_hash", "signal") == \
        we["origin_envelope_hash"]


def test_origin_payload_and_intent_hashes_present():
    we = k.clean_outcome()["work_origin"]
    assert we["source_payload_hash"]
    assert we["normalized_intent_hash"]


def test_origin_never_grants_authority_flags():
    we = k.clean_outcome()["work_origin"]
    assert we["trigger_is_authority"] is False
    assert we["message_is_approval"] is False
    assert we["authority_status"] in ("TRIGGER_ONLY", "NOT_AUTHORITY")


def test_origin_hash_changes_on_degradation():
    clean = k.prepare()["work_origin"]["origin_envelope_hash"]
    bad = k.prepare(origin_ambiguous=True)["work_origin"]["origin_envelope_hash"]
    assert clean != bad


# --- API layer -------------------------------------------------------------
def test_origin_api_subfield_endpoint(gate):
    wrid, _ = gate.observed_work()
    we = gate.wo(wrid, "origin").json()["work_origin"]
    assert we["origin_status"] == "VALID"
    assert we["trigger_is_authority"] is False
    assert we["message_is_approval"] is False


def test_origin_api_authority_status_present(gate):
    wrid, _ = gate.observed_work()
    body = gate.wo(wrid, "origin").json()
    assert body["work_run_id"] == wrid
    assert body["honesty_labels"]
    assert body["work_origin"]["authority_status"] in (
        "TRIGGER_ONLY", "NOT_AUTHORITY")

"""TOOL-B5 broker safety lattice (b.build_safety_lattice).

All broker states form a dominance lattice: risk/evidence drift can only move a
request DOWNWARD (toward blocked). An unknown status blocks; an unsafe UPWARD
transition (blocked prior -> more benign current) blocks. Verified by running.
"""
from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k


def _lattice(input_statuses, prior_status=None):
    return b.build_safety_lattice(
        tenant_id="t", broker_request_id="br1",
        input_statuses=input_statuses, prior_status=prior_status)


def test_clean_positive_statuses_lattice_matched():
    lat = _lattice(["BROKER_PREPARED_FOR_FUTURE_ONLY", "NULL_ONLY_PREPARED"])
    assert lat["broker_safety_lattice_status"] == "LATTICE_MATCHED"
    assert lat["signal"] is None
    assert lat["unsafe_upward_transition_detected"] is False
    assert lat["unknown_statuses"] == []


def test_unknown_status_blocks_lattice():
    lat = _lattice(["BROKER_PREPARED_FOR_FUTURE_ONLY", "NOVEL_XYZ"])
    assert lat["broker_safety_lattice_status"] == "LATTICE_FAILED"
    assert lat["signal"] == "BROKER_SAFETY_LATTICE_FAILED"
    assert "NOVEL_XYZ" in lat["unknown_statuses"]


def test_unsafe_upward_transition_blocks():
    # Prior was hard-blocked; current computes to a more benign status with no
    # fresh evidence -> unsafe upward transition.
    lat = _lattice(["BROKER_PREPARED_FOR_FUTURE_ONLY"],
                   prior_status="TOOL_B1_BLOCKED")
    assert lat["unsafe_upward_transition_detected"] is True
    assert lat["broker_safety_lattice_status"] == \
        "UNSAFE_UPWARD_TRANSITION_DETECTED"
    assert lat["signal"] == "BROKER_SAFETY_LATTICE_FAILED"
    assert lat["lattice_transition_history"] == \
        ["TOOL_B1_BLOCKED", "BROKER_PREPARED_FOR_FUTURE_ONLY"]


def test_computed_status_is_dominant_of_inputs():
    inputs = ["TOOL_B2_BLOCKED", "BROKER_PREPARED_FOR_FUTURE_ONLY",
              "NULL_ONLY_PREPARED"]
    lat = _lattice(inputs)
    assert lat["computed_status"] == b.dominant_signal(inputs)
    assert lat["computed_status"] == "TOOL_B2_BLOCKED"


def test_missing_evidence_cannot_move_status_up():
    # A benign current status behind a blocked prior must not silently promote
    # the request: the lattice fails closed instead of matching.
    lat = _lattice(["NULL_ONLY_PREPARED"], prior_status="CROSS_TENANT")
    assert lat["broker_safety_lattice_status"] != "LATTICE_MATCHED"
    assert lat["signal"] == "BROKER_SAFETY_LATTICE_FAILED"
    assert lat["unsafe_upward_transition_detected"] is True


def test_clean_outcome_lattice_matched(gate):
    o = k.clean_outcome(gate)
    lat = o["broker_safety_lattice"]
    assert lat["broker_safety_lattice_status"] == "LATTICE_MATCHED"
    assert lat["signal"] is None


def test_lattice_hash_deterministic():
    a = _lattice(["BROKER_PREPARED_FOR_FUTURE_ONLY", "TOOL_B3_BLOCKED"])
    c = _lattice(["BROKER_PREPARED_FOR_FUTURE_ONLY", "TOOL_B3_BLOCKED"])
    assert a["broker_safety_lattice_hash"] == c["broker_safety_lattice_hash"]


def test_lattice_hash_excludes_itself():
    lat = _lattice(["BROKER_PREPARED_FOR_FUTURE_ONLY"])
    h = lat["broker_safety_lattice_hash"]
    # Recomputing with a different value in the self field yields the same hash.
    recomputed = b._core_hash(
        {**lat, "broker_safety_lattice_hash": "ZZZ"},
        "broker_safety_lattice_hash")
    assert recomputed == h

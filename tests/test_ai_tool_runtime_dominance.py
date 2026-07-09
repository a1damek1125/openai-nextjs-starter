"""TOOL-B6 read-path runtime: failure-dominance ladder + signal->status map."""
from finalis.ai_employee import tool_runtime as rt


def test_hard_fail_dominates_positive():
    assert rt.dominant_signal(
        ["READ_ONLY_RUNTIME_COMPLETED", "TAMPERED"]) == "TAMPERED"


def test_unknown_signal_ranks_maximally_dominant():
    # Unknown signals fall to rank -1 (most dominant) so they always win.
    assert rt.dominant_signal(
        ["READ_ONLY_RUNTIME_COMPLETED", "ZZZ_MADE_UP"]) == "ZZZ_MADE_UP"


def test_empty_signals_is_positive():
    assert rt.dominant_signal([]) == "READ_ONLY_RUNTIME_COMPLETED"


def test_failure_dominance_strict_total_order():
    dom = rt.FAILURE_DOMINANCE
    assert len(dom) == len(set(dom))
    assert rt._DOMINANCE_RANK == {s: i for i, s in enumerate(dom)}
    assert len(rt._DOMINANCE_RANK) == len(dom)


def test_every_signal_maps_to_a_valid_status():
    for sig in rt.FAILURE_DOMINANCE:
        assert rt._status_for_signal(sig) in rt.RUNTIME_STATUSES


def test_positive_statuses_exact():
    assert rt.POSITIVE_STATUSES == {"RUNTIME_READ_ONLY_COMPLETED",
                                    "RUNTIME_READ_ONLY_PREPARED"}


def test_reason_codes_cover_all_signals():
    for sig in rt.FAILURE_DOMINANCE:
        assert sig in rt.REASON_CODES
    assert "READ_ONLY_RUNTIME_COMPLETED" in rt.REASON_CODES


def test_positive_cannot_override_hard_fail_and_quarantine_stale():
    assert rt.status_for_signals(
        ["READ_ONLY_RUNTIME_COMPLETED", "TOOL_B5_BLOCKED"]) == "RUNTIME_BLOCKED"
    assert rt.status_for_signals(["CANARY_LEAK_DETECTED"]) == \
        "RUNTIME_QUARANTINED"
    assert rt.status_for_signals(["SNAPSHOT_MUTABLE"]) == "RUNTIME_STALE"

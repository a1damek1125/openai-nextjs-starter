"""TOOL-B5 dominance ladder: b.dominant_signal / b.status_for_signals against
the strict-total-order failure lattice. No positive status can override a hard
fail."""
from finalis.ai_employee import tool_broker as b


def test_dominant_signal_picks_worst():
    assert b.dominant_signal(
        ["BROKER_PREPARED_FOR_FUTURE_ONLY", "TAMPERED"]) == "TAMPERED"
    # TAMPERED tops the whole ladder.
    assert b.FAILURE_DOMINANCE[0] == "TAMPERED"


def test_unknown_signal_ranks_maximally_dominant():
    # Unknown signal -> rank -1 -> more dominant than any known signal.
    assert b.dominant_signal(
        ["BROKER_PREPARED_FOR_FUTURE_ONLY", "ZZZ"]) == "ZZZ"
    assert b.dominant_signal(["TAMPERED", "ZZZ"]) == "ZZZ"


def test_empty_signals_default_to_prepared():
    assert b.dominant_signal([]) == "BROKER_PREPARED_FOR_FUTURE_ONLY"


def test_failure_dominance_is_strict_total_order():
    fd = b.FAILURE_DOMINANCE
    # No duplicates -> strict order.
    assert len(set(fd)) == len(fd)
    # Rank map is a bijection over the ladder.
    assert len(b._DOMINANCE_RANK) == len(fd)
    assert all(b._DOMINANCE_RANK[s] == i for i, s in enumerate(fd))


def test_every_signal_maps_to_valid_status():
    for sig in b.FAILURE_DOMINANCE:
        assert sig in b._SIGNAL_TO_STATUS, sig
        assert b._SIGNAL_TO_STATUS[sig] in b.BROKER_STATUSES, sig


def test_positive_statuses_are_exactly_two():
    assert b.POSITIVE_STATUSES == {
        "BROKER_PREPARED_FOR_FUTURE_ONLY", "NULL_ONLY_PREPARED"}
    assert b.POSITIVE_STATUSES <= b.BROKER_STATUSES


def test_reason_codes_cover_all_signals():
    for sig in b.FAILURE_DOMINANCE:
        assert sig in b.REASON_CODES, sig
        assert b.REASON_CODES[sig]


def test_positive_status_cannot_override_hard_fail():
    # A prepared signal mixed with a hard block resolves to the block.
    assert b.status_for_signals(
        ["BROKER_PREPARED_FOR_FUTURE_ONLY", "TOOL_B1_BLOCKED"]) == "BLOCKED"
    # The TAMPERED signal is the dominant one, and its mapped status is BLOCKED.
    assert b.dominant_signal(
        ["BROKER_PREPARED_FOR_FUTURE_ONLY", "TAMPERED"]) == "TAMPERED"
    assert b.status_for_signals(
        ["BROKER_PREPARED_FOR_FUTURE_ONLY", "TAMPERED"]) == "BLOCKED"
    # Clean-only -> positive status.
    assert b.status_for_signals(
        ["BROKER_PREPARED_FOR_FUTURE_ONLY"]) == "BROKER_PREPARED_FOR_FUTURE_ONLY"

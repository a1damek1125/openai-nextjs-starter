"""TOOL-B4 pre-action reference monitor: dominance-ladder unit tests.

Verifies the single fail-closed ordering that resolves which adverse signal
dictates a decision. Pure unit tests over g.dominant_failure /
g.status_for_signals / g._DOMINANCE_RANK / g._SIGNAL_TO_STATUS. Executes nothing.
"""
from finalis.ai_employee import tool_guardrails as g


def test_higher_rank_signal_dominates_benign():
    # TAMPERED is the highest-precedence adverse signal; it wins over an allow.
    assert g.dominant_failure(
        ["ALLOWED_FOR_FUTURE_BROKER_ONLY", "TAMPERED"]) == "TAMPERED"


def test_approval_dominates_consent():
    # APPROVAL_MISSING outranks CONSENT_MISSING on the ladder.
    assert g.dominant_failure(
        ["CONSENT_MISSING", "APPROVAL_MISSING"]) == "APPROVAL_MISSING"


def test_order_independent():
    # Resolution is set-like: input order never changes the dominant signal.
    assert g.dominant_failure(
        ["APPROVAL_MISSING", "CONSENT_MISSING"]) == "APPROVAL_MISSING"


def test_unknown_signal_is_maximally_dominant():
    # A novel signal not on the ladder is treated as worst-case (fail-closed),
    # so it can never be silently outranked by a benign known signal.
    assert g.dominant_failure(
        ["NOVEL_SIGNAL", "ALLOWED_FOR_FUTURE_BROKER_ONLY"]) == "NOVEL_SIGNAL"


def test_two_unknown_signals_pick_first():
    # min() with equal (-1) rank is stable, keeping resolution deterministic.
    got = g.dominant_failure(["NOVEL_A", "NOVEL_B"])
    assert got in ("NOVEL_A", "NOVEL_B")
    assert got == "NOVEL_A"


def test_empty_signals_is_the_permissive_base():
    assert g.dominant_failure([]) == "ALLOWED_FOR_FUTURE_BROKER_ONLY"
    # And that base maps to the single most-permissive decision status.
    assert g.status_for_signals([]) == \
        "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"


def test_dominance_rank_strictly_monotone():
    # FAILURE_DOMINANCE is a strict total order: ranks are 0..n-1, unique and
    # increasing in list position, with no duplicate signals.
    ladder = g.FAILURE_DOMINANCE
    assert len(ladder) == len(set(ladder))
    ranks = [g._DOMINANCE_RANK[s] for s in ladder]
    assert ranks == list(range(len(ladder)))
    assert all(a < b for a, b in zip(ranks, ranks[1:]))


def test_every_ladder_signal_maps_to_a_status():
    # Every adverse signal in the ladder resolves to exactly one decision status
    # and that status is a member of the declared decision-status universe.
    for sig in g.FAILURE_DOMINANCE:
        assert sig in g._SIGNAL_TO_STATUS, sig
        assert g._SIGNAL_TO_STATUS[sig] in g.DECISION_STATUSES, sig
    # The ladder and the status map cover exactly the same signal set.
    assert set(g.FAILURE_DOMINANCE) == set(g._SIGNAL_TO_STATUS)

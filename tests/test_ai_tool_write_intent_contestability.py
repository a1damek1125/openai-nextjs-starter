"""TOOL-B7 v3: Contestability Window — unresolved objections must be resolved
before any future commit; they block future-commit readiness."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_clean_window_is_clear(gate):
    r = k.clean_outcome(gate)["contestability_window"]
    assert r["contestability_status"] == "CLEAR"
    assert r["unresolved_objections"] == []
    assert r["signal"] is None


def test_contestability_required_before_future_commit(gate):
    r = k.clean_outcome(gate)["contestability_window"]
    assert r["contestability_required_before_future_commit"] is True


def test_unresolved_objection_blocks(gate):
    o = k.clean_outcome(gate, objections=[{"objection_id": "x",
                                           "resolved": False}])
    r = o["contestability_window"]
    assert r["contestability_status"] == "UNRESOLVED"
    assert r["signal"] == "CONTESTATION_UNRESOLVED"
    assert any(u["objection_id"] == "x" for u in r["unresolved_objections"])
    assert o["dominant_signal"] == "CONTESTATION_UNRESOLVED"
    assert o["write_intent_status"] == \
        "WRITE_INTENT_NEEDS_CONTESTABILITY_REVIEW"


def test_resolved_objection_clears(gate):
    o = k.clean_outcome(gate, objections=[{"objection_id": "x",
                                          "resolved": True}])
    r = o["contestability_window"]
    assert r["contestability_status"] == "CLEAR"
    assert r["unresolved_objections"] == []
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_unresolved_blocks_future_readiness(gate):
    o = k.clean_outcome(gate, objections=[{"objection_id": "x",
                                          "resolved": False}])
    assert o["ready_for_future_commit_only"] is False
    assert o["commit_executable_now"] is False


def test_unresolved_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    blocked = k.prepare(gate, b6, objections=[{"objection_id": "x",
                                              "resolved": False}])
    assert clean["write_intent_decision_hash"] != \
        blocked["write_intent_decision_hash"]


def test_hash_recomputes_and_excludes_signal_clean(gate):
    r = k.clean_outcome(gate)["contestability_window"]
    assert _core_hash(r, "contestability_window_hash", "signal") == \
        r["contestability_window_hash"]


def test_hash_recomputes_when_unresolved(gate):
    r = k.clean_outcome(gate, objections=[{"objection_id": "x",
                                          "resolved": False}])[
        "contestability_window"]
    assert _core_hash(r, "contestability_window_hash", "signal") == \
        r["contestability_window_hash"]


def test_endpoint_returns_window(gate):
    wid, _ = gate.prepared_write_intent()
    r = gate.wi(wid, "/contestability").json()["contestability_window"]
    assert r["contestability_status"] == "CLEAR"
    assert r["contestability_required_before_future_commit"] is True

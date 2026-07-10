"""TOOL-B7 v3: Obligation Containment — every draft obligation must be proven
contained before a future commit; an uncontained obligation blocks."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_clean_with_no_obligations_is_contained(gate):
    r = k.clean_outcome(gate)["obligation_containment"]
    assert r["containment_status"] == "CONTAINED"
    assert r["all_contained"] is True
    assert r["obligation_ids"] == []
    assert r["signal"] is None


def test_containment_required_flag(gate):
    r = k.clean_outcome(gate)["obligation_containment"]
    assert r["obligation_containment_required"] is True


def test_obligation_without_state_fails(gate):
    o = k.clean_outcome(gate, obligations=["ob1"])
    r = o["obligation_containment"]
    assert r["containment_status"] == "UNCONTAINED"
    assert r["uncontained_obligation_ids"] == ["ob1"]
    assert r["all_contained"] is False
    assert r["signal"] == "OBLIGATION_CONTAINMENT_FAILED"
    assert o["dominant_signal"] == "OBLIGATION_CONTAINMENT_FAILED"
    assert o["write_intent_status"] == "WRITE_INTENT_NEEDS_OBLIGATION_REVIEW"


def test_contained_obligation_clears(gate):
    o = k.clean_outcome(gate, obligations=["ob1"],
                        obligation_states=[{"obligation_id": "ob1",
                                            "contained": True}])
    r = o["obligation_containment"]
    assert r["containment_status"] == "CONTAINED"
    assert r["all_contained"] is True
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_uncontained_blocks_future_readiness(gate):
    o = k.clean_outcome(gate, obligations=["ob1"])
    assert o["ready_for_future_commit_only"] is False
    assert o["commit_executable_now"] is False


def test_uncontained_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    blocked = k.prepare(gate, b6, obligations=["ob1"])
    assert clean["write_intent_decision_hash"] != \
        blocked["write_intent_decision_hash"]


def test_hash_recomputes_clean(gate):
    r = k.clean_outcome(gate)["obligation_containment"]
    assert _core_hash(r, "obligation_containment_hash", "signal") == \
        r["obligation_containment_hash"]


def test_hash_recomputes_when_uncontained(gate):
    r = k.clean_outcome(gate, obligations=["ob1"])["obligation_containment"]
    assert _core_hash(r, "obligation_containment_hash", "signal") == \
        r["obligation_containment_hash"]


def test_endpoint_returns_containment(gate):
    wid, _ = gate.prepared_write_intent()
    r = gate.wi(wid, "/obligation-containment").json()[
        "obligation_containment"]
    assert r["containment_status"] == "CONTAINED"
    assert r["obligation_containment_required"] is True

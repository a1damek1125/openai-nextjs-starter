"""TOOL-B7 v3: Transaction Invariants — atomic-boundary / no-partial-effect /
deterministic-delta / scope-contained invariants must all hold."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_clean_invariants_all_hold(gate):
    r = k.clean_outcome(gate)["transaction_invariants"]
    assert r["all_invariants_hold"] is True
    assert r["invariant_violation_count"] == 0
    assert r["signal"] is None


def test_invariant_checks_non_empty(gate):
    r = k.clean_outcome(gate)["transaction_invariants"]
    assert r["invariant_checks"]
    assert "ATOMIC_BOUNDARY" in r["invariant_checks"]


def test_violation_fails(gate):
    o = k.clean_outcome(gate, invariant_violations=1)
    r = o["transaction_invariants"]
    assert r["all_invariants_hold"] is False
    assert r["invariant_violation_count"] == 1
    assert r["signal"] == "TRANSACTION_INVARIANT_FAILED"
    assert o["dominant_signal"] == "TRANSACTION_INVARIANT_FAILED"
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_violation_blocks_future_readiness(gate):
    o = k.clean_outcome(gate, invariant_violations=2)
    assert o["transaction_invariants"]["invariant_violation_count"] == 2
    assert o["ready_for_future_commit_only"] is False
    assert o["commit_executable_now"] is False


def test_violation_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    blocked = k.prepare(gate, b6, invariant_violations=1)
    assert clean["write_intent_decision_hash"] != \
        blocked["write_intent_decision_hash"]


def test_hash_recomputes_clean(gate):
    r = k.clean_outcome(gate)["transaction_invariants"]
    assert _core_hash(r, "transaction_invariants_hash", "signal") == \
        r["transaction_invariants_hash"]


def test_hash_recomputes_when_violated(gate):
    r = k.clean_outcome(gate, invariant_violations=1)[
        "transaction_invariants"]
    assert _core_hash(r, "transaction_invariants_hash", "signal") == \
        r["transaction_invariants_hash"]


def test_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["transaction_invariants"]["transaction_invariants_hash"] == \
        o2["transaction_invariants"]["transaction_invariants_hash"]


def test_endpoint_returns_invariants(gate):
    wid, _ = gate.prepared_write_intent()
    r = gate.wi(wid, "/transaction-invariants").json()[
        "transaction_invariants"]
    assert r["all_invariants_hold"] is True
    assert r["invariant_checks"]

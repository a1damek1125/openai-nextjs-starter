"""TOOL-B8 v1-v3 base: metamorphic oracle — a set of metamorphic relations (order
invariance, idempotent dry-run, no effect on abort, rollback restores shadow) must
all hold, else the oracle reports a violation and blocks."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_clean_holds(gate):
    r = k.clean_outcome(gate)["metamorphic_oracle"]
    assert r["oracle_status"] == "HOLDS"
    assert r["all_relations_hold"] is True
    assert r["signal"] is None


def test_relations_non_empty(gate):
    r = k.clean_outcome(gate)["metamorphic_oracle"]
    assert r["metamorphic_relations"]
    assert "ORDER_INVARIANCE" in r["metamorphic_relations"]


def test_violation_blocks(gate):
    o = k.clean_outcome(gate, metamorphic_holds=False)
    assert o["dominant_signal"] == "METAMORPHIC_ORACLE_VIOLATION"
    r = o["metamorphic_oracle"]
    assert r["oracle_status"] == "VIOLATED"
    assert r["all_relations_hold"] is False
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_violation_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    violated = k.prepare(gate, b7, metamorphic_holds=False)[
        "commit_simulation_decision_hash"]
    assert clean != violated


def test_metamorphic_oracle_hash_recomputes(gate):
    r = k.clean_outcome(gate)["metamorphic_oracle"]
    assert _core_hash(r, "metamorphic_oracle_hash", "signal") == \
        r["metamorphic_oracle_hash"]


def test_violation_hash_recomputes(gate):
    r = k.clean_outcome(gate, metamorphic_holds=False)["metamorphic_oracle"]
    assert _core_hash(r, "metamorphic_oracle_hash", "signal") == \
        r["metamorphic_oracle_hash"]


def test_clean_signal_none_and_violation_set(gate):
    assert k.clean_outcome(gate)["metamorphic_oracle"]["signal"] is None
    v = k.clean_outcome(gate, metamorphic_holds=False)["metamorphic_oracle"]
    assert v["signal"] == "METAMORPHIC_ORACLE_VIOLATION"


def test_metamorphic_oracle_endpoint(gate):
    sid, _ = gate.prepared_commit_simulation()
    r = gate.cs(sid, "/metamorphic-oracle").json()["metamorphic_oracle"]
    assert r["oracle_status"] == "HOLDS"
    assert r["all_relations_hold"] is True

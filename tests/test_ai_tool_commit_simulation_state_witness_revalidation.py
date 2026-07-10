"""TOOL-B8 v1-v3 base: state-witness revalidation — every witness recomputed
fresh against the current policy epoch; stale witnesses hard-block as B8_V5_STALE.
"""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_clean_revalidated(gate):
    r = k.clean_outcome(gate)["state_witness_revalidation"]
    assert r["revalidation_status"] == "REVALIDATED"
    assert r["recomputed_fresh"] is True
    assert r["stale_witness_classes"] == []
    assert r["signal"] is None


def test_stale_witness_fails(gate):
    o = k.clean_outcome(
        gate, fresh_witnesses=[{"witness_class": "STATE_WITNESS", "epoch": 1}],
        policy_epoch=9)
    assert o["dominant_signal"] == "STATE_WITNESS_REVALIDATION_FAILED"
    r = o["state_witness_revalidation"]
    assert r["revalidation_status"] == "STALE"
    assert r["stale_witness_classes"]
    assert "STATE_WITNESS" in r["stale_witness_classes"]


def test_stale_witness_status_is_stale(gate):
    o = k.clean_outcome(
        gate, fresh_witnesses=[{"witness_class": "STATE_WITNESS", "epoch": 1}],
        policy_epoch=9)
    assert o["commit_simulation_status"] == "B8_V5_STALE"


def test_revalidation_not_ok_fails(gate):
    o = k.clean_outcome(gate, revalidation_ok=False)
    assert o["dominant_signal"] == "STATE_WITNESS_REVALIDATION_FAILED"
    assert o["state_witness_revalidation"]["recomputed_fresh"] is False


def test_failure_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    broken = k.prepare(gate, b7, revalidation_ok=False)[
        "commit_simulation_decision_hash"]
    assert clean != broken


def test_stale_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    stale = k.prepare(
        gate, b7,
        fresh_witnesses=[{"witness_class": "STATE_WITNESS", "epoch": 1}],
        policy_epoch=9)["commit_simulation_decision_hash"]
    assert clean != stale


def test_revalidation_hash_recomputes(gate):
    r = k.clean_outcome(gate)["state_witness_revalidation"]
    assert _core_hash(r, "state_witness_revalidation_hash", "signal") == \
        r["state_witness_revalidation_hash"]


def test_stale_revalidation_hash_recomputes(gate):
    r = k.clean_outcome(
        gate, fresh_witnesses=[{"witness_class": "STATE_WITNESS", "epoch": 1}],
        policy_epoch=9)["state_witness_revalidation"]
    assert _core_hash(r, "state_witness_revalidation_hash", "signal") == \
        r["state_witness_revalidation_hash"]


def test_revalidation_endpoint(gate):
    sid, _ = gate.prepared_commit_simulation()
    r = gate.cs(sid, "/state-witness-revalidation").json()[
        "state_witness_revalidation"]
    assert r["revalidation_status"] == "REVALIDATED"
    assert r["recomputed_fresh"] is True

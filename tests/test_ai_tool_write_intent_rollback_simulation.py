"""TOOL-B7: rollback simulation — simulated-only, never executed; one undo step
per delta; an infeasible rollback blocks and changes the decision hash."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k

_TWO = [{"field_path": "status", "from_value": "open", "to_value": "closed",
         "data_class": "INTERNAL"},
        {"field_path": "note", "from_value": "a", "to_value": "b",
         "data_class": "PUBLIC"}]


def test_clean_all_reversible(gate):
    rs = k.clean_outcome(gate)["rollback_simulation"]
    assert rs["all_reversible"] is True


def test_clean_simulated_only_not_executed(gate):
    rs = k.clean_outcome(gate)["rollback_simulation"]
    assert rs["simulated_only"] is True
    assert rs["executed"] is False
    assert rs["signal"] is None


def test_undo_step_per_delta_single(gate):
    o = k.clean_outcome(gate)
    assert len(o["rollback_simulation"]["undo_steps"]) == \
        len(o["write_intent_draft"]["proposed_deltas"]) == 1


def test_undo_step_per_delta_multiple(gate):
    o = k.prepare(gate, k.b6_outcome(gate), proposed_deltas=_TWO)
    rs = o["rollback_simulation"]
    assert len(rs["undo_steps"]) == 2
    fields = {d["field_path"] for d in o["write_intent_draft"]["proposed_deltas"]}
    for step in rs["undo_steps"]:
        assert step["reversible"] is True
        assert step["undo_field"] in fields


def test_infeasible_rollback_signal(gate):
    o = k.prepare(gate, k.b6_outcome(gate), rollback_feasible=False)
    assert o["rollback_simulation"]["signal"] == "ROLLBACK_SIMULATION_FAILED"
    assert o["rollback_simulation"]["all_reversible"] is False
    assert o["dominant_signal"] == "ROLLBACK_SIMULATION_FAILED"


def test_infeasible_rollback_blocks_positive_terminal(gate):
    o = k.prepare(gate, k.b6_outcome(gate), rollback_feasible=False)
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_infeasible_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    failed = k.prepare(gate, b6, rollback_feasible=False)
    assert clean["write_intent_decision_hash"] != \
        failed["write_intent_decision_hash"]


def test_rollback_simulation_hash_recomputes(gate):
    rs = k.clean_outcome(gate)["rollback_simulation"]
    assert _core_hash(rs, "rollback_simulation_hash", "signal") == \
        rs["rollback_simulation_hash"]


def test_failed_rollback_hash_recomputes(gate):
    rs = k.prepare(gate, k.b6_outcome(gate),
                   rollback_feasible=False)["rollback_simulation"]
    assert _core_hash(rs, "rollback_simulation_hash", "signal") == \
        rs["rollback_simulation_hash"]


def test_rollback_simulation_endpoint(gate):
    wid, _ = gate.prepared_write_intent()
    rs = gate.wi(wid, "/rollback-simulation").json()["rollback_simulation"]
    assert rs["simulated_only"] is True and rs["executed"] is False

"""TOOL-B7: compensation plan — plan-only, never executed; one compensating
action per delta; a compensation gap blocks and changes the decision hash."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k

_TWO = [{"field_path": "status", "from_value": "open", "to_value": "closed",
         "data_class": "INTERNAL"},
        {"field_path": "note", "from_value": "a", "to_value": "b",
         "data_class": "PUBLIC"}]


def test_clean_plan_only(gate):
    cp = k.clean_outcome(gate)["compensation_plan"]
    assert cp["plan_only"] is True
    assert cp["executed"] is False


def test_clean_no_gap(gate):
    cp = k.clean_outcome(gate)["compensation_plan"]
    assert cp["compensation_gap_count"] == 0
    assert cp["signal"] is None


def test_compensating_action_per_delta_single(gate):
    o = k.clean_outcome(gate)
    cp = o["compensation_plan"]
    assert len(cp["compensating_actions"]) == \
        len(o["write_intent_draft"]["proposed_deltas"]) == 1


def test_compensating_action_per_delta_multiple(gate):
    o = k.prepare(gate, k.b6_outcome(gate), proposed_deltas=_TWO)
    cp = o["compensation_plan"]
    assert len(cp["compensating_actions"]) == 2
    fields = {d["field_path"] for d in o["write_intent_draft"]["proposed_deltas"]}
    for a in cp["compensating_actions"]:
        assert a["planned_only"] is True
        assert a["compensating_action"].startswith("REVERSE_")
        assert a["compensating_action"][len("REVERSE_"):] in fields


def test_gap_detected_signal(gate):
    o = k.prepare(gate, k.b6_outcome(gate), compensation_gaps=1)
    assert o["compensation_plan"]["signal"] == "COMPENSATION_GAP_DETECTED"
    assert o["dominant_signal"] == "COMPENSATION_GAP_DETECTED"
    assert o["compensation_plan"]["compensation_gap_count"] == 1


def test_gap_blocks_positive_terminal(gate):
    o = k.prepare(gate, k.b6_outcome(gate), compensation_gaps=1)
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_gap_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    gap = k.prepare(gate, b6, compensation_gaps=1)
    assert clean["write_intent_decision_hash"] != \
        gap["write_intent_decision_hash"]


def test_compensation_plan_hash_recomputes(gate):
    cp = k.clean_outcome(gate)["compensation_plan"]
    assert _core_hash(cp, "compensation_plan_hash", "signal") == \
        cp["compensation_plan_hash"]


def test_gap_plan_hash_recomputes(gate):
    cp = k.prepare(gate, k.b6_outcome(gate),
                   compensation_gaps=1)["compensation_plan"]
    assert _core_hash(cp, "compensation_plan_hash", "signal") == \
        cp["compensation_plan_hash"]


def test_compensation_plan_endpoint(gate):
    wid, _ = gate.prepared_write_intent()
    cp = gate.wi(wid, "/compensation-plan").json()["compensation_plan"]
    assert cp["plan_only"] is True and cp["executed"] is False

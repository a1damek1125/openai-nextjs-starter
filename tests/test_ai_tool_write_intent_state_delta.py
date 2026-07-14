"""TOOL-B7: write-intent state delta — deterministic, draft-only, mirrors the
proposed deltas, binds the shadow-state delta graph, never touches production."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k

_TWO = [{"field_path": "status", "from_value": "open", "to_value": "closed",
         "data_class": "INTERNAL"},
        {"field_path": "note", "from_value": "a", "to_value": "b",
         "data_class": "PUBLIC"}]


def test_state_delta_not_applied_to_production(gate):
    sd = k.clean_outcome(gate)["state_delta"]
    assert sd["applied_to_production"] is False


def test_state_delta_deterministic_flag(gate):
    sd = k.clean_outcome(gate)["state_delta"]
    assert sd["deterministic"] is True


def test_delta_count_matches_single(gate):
    o = k.clean_outcome(gate)
    sd = o["state_delta"]
    assert sd["delta_count"] == 1
    assert sd["delta_count"] == len(o["write_intent_draft"]["proposed_deltas"])


def test_delta_count_matches_multiple(gate):
    o = k.prepare(gate, k.b6_outcome(gate), proposed_deltas=_TWO)
    sd = o["state_delta"]
    assert sd["delta_count"] == 2
    assert sd["delta_count"] == len(o["write_intent_draft"]["proposed_deltas"])


def test_delta_entries_mirror_draft_deltas(gate):
    o = k.prepare(gate, k.b6_outcome(gate), proposed_deltas=_TWO)
    assert o["state_delta"]["delta_entries"] == \
        o["write_intent_draft"]["proposed_deltas"]


def test_delta_entries_are_hashed_not_raw_values(gate):
    o = k.clean_outcome(gate)
    entry = o["state_delta"]["delta_entries"][0]
    assert set(entry.keys()) == {"field_path", "from_value_hash",
                                 "to_value_hash", "data_class"}
    assert "from_value" not in entry and "to_value" not in entry


def test_binds_shadow_state_delta_graph_hash(gate):
    o = k.clean_outcome(gate)
    assert o["state_delta"]["shadow_state_delta_graph_hash"] == \
        o["shadow_state_delta_graph"]["shadow_state_delta_graph_hash"]


def test_state_delta_hash_recomputes(gate):
    sd = k.clean_outcome(gate)["state_delta"]
    assert _core_hash(sd, "state_delta_hash") == sd["state_delta_hash"]


def test_state_delta_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["state_delta"]["state_delta_hash"] == \
        o2["state_delta"]["state_delta_hash"]


def test_state_delta_no_signal_on_clean(gate):
    sd = k.clean_outcome(gate)["state_delta"]
    # State delta itself never emits a fail-closed signal.
    assert "signal" not in sd or sd.get("signal") is None


def test_state_delta_endpoint(gate):
    wid, _ = gate.prepared_write_intent()
    sd = gate.wi(wid, "/state-delta").json()["state_delta"]
    assert sd["applied_to_production"] is False
    assert sd["deterministic"] is True

"""TOOL-B7 v3: Shadow-State Delta Graph + State Delta — deltas exist only in a
local shadow graph; production state is NEVER touched and NEVER applied."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_graph_is_shadow_only(gate):
    g = k.clean_outcome(gate)["shadow_state_delta_graph"]
    assert g["shadow_only"] is True
    assert g["touches_production_state"] is False


def test_one_shadow_node_per_delta(gate):
    o = k.clean_outcome(gate, proposed_deltas=[
        {"field_path": "priority", "from_value": "low", "to_value": "high",
         "data_class": "INTERNAL"},
        {"field_path": "status", "from_value": "open", "to_value": "closed",
         "data_class": "INTERNAL"}])
    g = o["shadow_state_delta_graph"]
    assert g["node_count"] == 2
    assert {n["field_path"] for n in g["nodes"]} == {"priority", "status"}
    for n in g["nodes"]:
        assert n["shadow_only"] is True
        assert n["node_id"] == "shadow:" + n["field_path"]


def test_blast_radius_present(gate):
    g = k.clean_outcome(gate)["shadow_state_delta_graph"]
    assert g["blast_radius_size"] == len(g["blast_radius_entities"])
    assert g["blast_radius_size"] >= 1
    assert "E-1" in g["blast_radius_entities"]


def test_state_delta_not_applied_to_production(gate):
    d = k.clean_outcome(gate)["state_delta"]
    assert d["applied_to_production"] is False
    assert d["deterministic"] is True


def test_state_delta_count_matches(gate):
    o = k.clean_outcome(gate, proposed_deltas=[
        {"field_path": "priority", "from_value": "low", "to_value": "high",
         "data_class": "INTERNAL"},
        {"field_path": "status", "from_value": "open", "to_value": "closed",
         "data_class": "INTERNAL"}])
    assert o["state_delta"]["delta_count"] == 2


def test_state_delta_binds_shadow_graph_hash(gate):
    o = k.clean_outcome(gate)
    assert o["state_delta"]["shadow_state_delta_graph_hash"] == \
        o["shadow_state_delta_graph"]["shadow_state_delta_graph_hash"]


def test_shadow_hash_recomputes_and_excludes_signal(gate):
    g = k.clean_outcome(gate)["shadow_state_delta_graph"]
    assert _core_hash(g, "shadow_state_delta_graph_hash", "signal") == \
        g["shadow_state_delta_graph_hash"]


def test_state_delta_hash_recomputes(gate):
    d = k.clean_outcome(gate)["state_delta"]
    assert _core_hash(d, "state_delta_hash") == d["state_delta_hash"]


def test_shadow_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["shadow_state_delta_graph"]["shadow_state_delta_graph_hash"] == \
        o2["shadow_state_delta_graph"]["shadow_state_delta_graph_hash"]


def test_endpoint_returns_shadow_graph(gate):
    wid, _ = gate.prepared_write_intent()
    g = gate.wi(wid, "/shadow-state-delta-graph").json()[
        "shadow_state_delta_graph"]
    assert g["shadow_only"] is True
    assert g["touches_production_state"] is False


def test_endpoint_returns_state_delta(gate):
    wid, _ = gate.prepared_write_intent()
    d = gate.wi(wid, "/state-delta").json()["state_delta"]
    assert d["applied_to_production"] is False
    assert d["delta_count"] == 1

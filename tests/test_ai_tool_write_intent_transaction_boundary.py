"""TOOL-B7 v3: Transaction Boundary — a deterministic, non-leaking envelope
mirroring exactly the draft's field paths, obligations and evidence refs."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_boundary_is_deterministic_and_contained(gate):
    b = k.clean_outcome(gate)["transaction_boundary"]
    assert b["deterministic_boundary"] is True
    assert b["boundary_leaks_out_of_scope"] is False


def test_included_field_paths_match_default_delta(gate):
    b = k.clean_outcome(gate)["transaction_boundary"]
    assert b["included_field_paths"] == ["status"]


def test_included_field_paths_mirror_proposed_deltas(gate):
    o = k.clean_outcome(gate, proposed_deltas=[
        {"field_path": "priority", "from_value": "low", "to_value": "high",
         "data_class": "INTERNAL"},
        {"field_path": "status", "from_value": "open", "to_value": "closed",
         "data_class": "INTERNAL"}])
    b = o["transaction_boundary"]
    assert b["included_field_paths"] == ["priority", "status"]


def test_included_obligations_mirror_draft(gate):
    o = k.clean_outcome(gate, obligations=["ob1"],
                        obligation_states=[{"obligation_id": "ob1",
                                            "contained": True}])
    assert o["transaction_boundary"]["included_obligation_ids"] == ["ob1"]
    assert o["obligation_containment"]["all_contained"] is True
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_included_evidence_refs_mirror_draft(gate):
    o = k.clean_outcome(gate, evidence_refs=["ev-2", "ev-1"])
    assert o["transaction_boundary"]["included_evidence_refs"] == \
        ["ev-1", "ev-2"]


def test_empty_obligations_and_evidence_by_default(gate):
    b = k.clean_outcome(gate)["transaction_boundary"]
    assert b["included_obligation_ids"] == []
    assert b["included_evidence_refs"] == []


def test_boundary_binds_semantic_transaction_id(gate):
    o = k.clean_outcome(gate)
    assert o["transaction_boundary"]["semantic_transaction_id"] == \
        o["semantic_transaction"]["semantic_transaction_id"]


def test_hash_recomputes(gate):
    b = k.clean_outcome(gate)["transaction_boundary"]
    assert _core_hash(b, "transaction_boundary_hash") == \
        b["transaction_boundary_hash"]


def test_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["transaction_boundary"]["transaction_boundary_hash"] == \
        o2["transaction_boundary"]["transaction_boundary_hash"]


def test_endpoint_returns_boundary(gate):
    wid, _ = gate.prepared_write_intent()
    b = gate.wi(wid, "/transaction-boundary").json()["transaction_boundary"]
    assert b["deterministic_boundary"] is True
    assert b["boundary_leaks_out_of_scope"] is False
    assert b["included_field_paths"] == ["status"]

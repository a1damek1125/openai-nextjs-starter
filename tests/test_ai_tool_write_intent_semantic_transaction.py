"""TOOL-B7 v3: Semantic Transaction — the write-intent is modelled as an
atomic, all-or-nothing, draft-only semantic transaction that NEVER executes."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_clean_semantic_transaction_is_draft_only_non_executing(gate):
    stx = k.clean_outcome(gate)["semantic_transaction"]
    assert stx["draft_only"] is True
    assert stx["is_execution"] is False
    assert stx["atomic_all_or_nothing_draft"] is True
    assert stx["semantic_transaction_valid"] is True
    assert stx["signal"] is None


def test_valid_task_scope_marks_transaction_valid(gate):
    o = k.clean_outcome(gate, task_scope="case")
    assert o["semantic_transaction"]["task_scope"] == "case"
    assert o["semantic_transaction"]["semantic_transaction_valid"] is True
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_empty_task_scope_is_invalid(gate):
    o = k.clean_outcome(gate, task_scope="")
    stx = o["semantic_transaction"]
    assert stx["semantic_transaction_valid"] is False
    assert stx["signal"] == "SEMANTIC_TRANSACTION_INVALID"
    assert o["dominant_signal"] == "SEMANTIC_TRANSACTION_INVALID"
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["ready_for_future_commit_only"] is False


def test_invalid_scope_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    invalid = k.prepare(gate, b6, task_scope="")
    assert clean["write_intent_decision_hash"] != \
        invalid["write_intent_decision_hash"]


def test_semantic_transaction_id_stable_for_same_deltas(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["semantic_transaction"]["semantic_transaction_id"] == \
        o2["semantic_transaction"]["semantic_transaction_id"]
    assert o1["semantic_transaction"]["semantic_transaction_id"].startswith(
        "stx-")


def test_semantic_transaction_id_reflects_deltas(gate):
    b6 = k.b6_outcome(gate)
    base = k.prepare(gate, b6)
    other = k.prepare(gate, b6, proposed_deltas=[
        {"field_path": "priority", "from_value": "low", "to_value": "high",
         "data_class": "INTERNAL"}])
    assert base["semantic_transaction"]["semantic_transaction_id"] != \
        other["semantic_transaction"]["semantic_transaction_id"]


def test_boundary_operations_recorded(gate):
    o = k.clean_outcome(gate, boundary_operations=["STAGE_DELTA", "VALIDATE"])
    stx = o["semantic_transaction"]
    assert stx["boundary_operations"] == ["STAGE_DELTA", "VALIDATE"]
    assert stx["operation_count"] == 2


def test_default_boundary_operation_present(gate):
    stx = k.clean_outcome(gate)["semantic_transaction"]
    assert stx["boundary_operations"] == ["STAGE_DELTA"]
    assert stx["operation_count"] == 1


def test_hash_recomputes_and_excludes_signal(gate):
    stx = k.clean_outcome(gate)["semantic_transaction"]
    assert _core_hash(stx, "semantic_transaction_hash", "signal") == \
        stx["semantic_transaction_hash"]


def test_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["semantic_transaction"]["semantic_transaction_hash"] == \
        o2["semantic_transaction"]["semantic_transaction_hash"]


def test_endpoint_returns_semantic_transaction(gate):
    wid, _ = gate.prepared_write_intent()
    stx = gate.wi(wid, "/semantic-transaction").json()["semantic_transaction"]
    assert stx["draft_only"] is True and stx["is_execution"] is False
    assert stx["atomic_all_or_nothing_draft"] is True
    assert stx["semantic_transaction_valid"] is True

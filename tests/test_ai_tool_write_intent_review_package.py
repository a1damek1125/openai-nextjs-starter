"""TOOL-B7 review package: presents draft-only, non-executing evidence; binds
every reviewed sub-report; its content digest is content-addressed and stable."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_presents_draft_only(gate):
    rp = k.clean_outcome(gate)["review_package"]
    assert rp["presents_draft_only"] is True


def test_presents_no_execution(gate):
    rp = k.clean_outcome(gate)["review_package"]
    assert rp["presents_no_execution"] is True


def test_binds_write_intent_draft_hash(gate):
    o = k.clean_outcome(gate)
    assert o["review_package"]["write_intent_draft_hash"] == \
        o["write_intent_draft"]["write_intent_draft_hash"]


def test_binds_semantic_transaction_hash(gate):
    o = k.clean_outcome(gate)
    assert o["review_package"]["semantic_transaction_hash"] == \
        o["semantic_transaction"]["semantic_transaction_hash"]


def test_binds_shadow_state_delta_graph_hash(gate):
    o = k.clean_outcome(gate)
    assert o["review_package"]["shadow_state_delta_graph_hash"] == \
        o["shadow_state_delta_graph"]["shadow_state_delta_graph_hash"]


def test_binds_rollback_simulation_hash(gate):
    o = k.clean_outcome(gate)
    assert o["review_package"]["rollback_simulation_hash"] == \
        o["rollback_simulation"]["rollback_simulation_hash"]


def test_binds_compensation_plan_hash(gate):
    o = k.clean_outcome(gate)
    assert o["review_package"]["compensation_plan_hash"] == \
        o["compensation_plan"]["compensation_plan_hash"]


def test_review_content_digest_present(gate):
    rp = k.clean_outcome(gate)["review_package"]
    assert rp["review_content_digest"]
    assert isinstance(rp["review_content_digest"], str)


def test_review_content_digest_stable_across_write_intent_id(gate):
    b6 = k.b6_outcome(gate)
    a = k.prepare(gate, b6, write_intent_id="wiA")["review_package"]
    b = k.prepare(gate, b6, write_intent_id="wiB")["review_package"]
    assert a["review_content_digest"] == b["review_content_digest"]


def test_review_content_digest_changes_with_payload(gate):
    b6 = k.b6_outcome(gate)
    a = k.prepare(gate, b6, approve=False)["review_package"]
    b = k.prepare(gate, b6, approve=False, proposed_deltas=[
        {"field_path": "amount", "from_value": "1", "to_value": "2",
         "data_class": "INTERNAL"}])["review_package"]
    assert a["review_content_digest"] != b["review_content_digest"]


def test_review_package_hash_recomputes(gate):
    rp = k.clean_outcome(gate)["review_package"]
    assert _core_hash(rp, "review_package_hash") == rp["review_package_hash"]

"""TOOL-B7 v4: Concurrent-draft conflict graph — same-target / overlapping-field
/ evidence conflicts BLOCK future readiness; obligation-only overlap needs
review; cross-tenant drafts are excluded; conflict never downgrades to a
warning."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def _related(gate, **over):
    r = {"write_intent_id": "o", "tenant_id": gate.tid,
         "target_entity_id": "E-1"}
    r.update(over)
    return r


def test_graph_exists_and_clean_is_clear(gate):
    g = k.clean_outcome(gate)["concurrent_draft_conflict_graph"]
    assert g["concurrent_draft_conflict_graph_id"].startswith("cfg-")
    assert g["graph_status"] == "CLEAR"
    assert g["blocking_conflicts"] == []
    assert g["review_conflicts"] == []


def test_nodes_and_edges_structures_present(gate):
    g = k.clean_outcome(gate)["concurrent_draft_conflict_graph"]
    assert g["nodes"] and g["edges"]
    node_types = {n["node_type"] for n in g["nodes"]}
    assert "WRITE_INTENT_DRAFT" in node_types
    assert "TARGET_ENTITY" in node_types
    assert any(e["edge_type"] == "PROPOSES_WRITE" for e in g["edges"])


def test_same_target_write_is_blocking(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  related_write_intents=[_related(gate)])
    g = o["concurrent_draft_conflict_graph"]
    assert g["graph_status"] == "BLOCKING"
    assert g["blocking_conflicts"]
    classes = g["blocking_conflicts"][0]["conflict_classes"]
    assert "SAME_TARGET_WRITE" in classes
    assert o["dominant_signal"] == "CONCURRENT_DRAFT_CONFLICT_BLOCKING"


def test_overlapping_field_delta_is_blocking(gate):
    # Same field ("status") on a DIFFERENT target -> overlapping-field conflict.
    o = k.prepare(gate, k.b6_outcome(gate), related_write_intents=[
        _related(gate, target_entity_id="E-2", field_paths=["status"])])
    g = o["concurrent_draft_conflict_graph"]
    assert g["graph_status"] == "BLOCKING"
    assert "OVERLAPPING_FIELD_DELTA" in \
        g["blocking_conflicts"][0]["conflict_classes"]
    assert o["dominant_signal"] == "CONCURRENT_DRAFT_CONFLICT_BLOCKING"


def test_obligation_only_overlap_needs_review_not_blocking(gate):
    o = k.prepare(gate, k.b6_outcome(gate), obligations=["ob1"],
                  obligation_states=[{"obligation_id": "ob1",
                                      "contained": True}],
                  related_write_intents=[_related(
                      gate, target_entity_id="E-2", obligation_ids=["ob1"])])
    g = o["concurrent_draft_conflict_graph"]
    assert g["graph_status"] == "REVIEW"
    assert g["blocking_conflicts"] == []
    assert "OBLIGATION_CONFLICT" in g["review_conflicts"][0]["conflict_classes"]
    assert o["write_intent_status"] == \
        "TRANSACTION_ESCROW_NEEDS_CONFLICT_REVIEW"
    assert "CONCURRENT_DRAFT_CONFLICT_REVIEW" in o["all_signals"]


def test_cross_tenant_drafts_excluded(gate):
    # A same-target draft in ANOTHER tenant produces no conflict at all.
    o = k.prepare(gate, k.b6_outcome(gate), related_write_intents=[
        _related(gate, tenant_id="other-tenant")])
    g = o["concurrent_draft_conflict_graph"]
    assert g["graph_status"] == "CLEAR"
    assert g["blocking_conflicts"] == [] and g["review_conflicts"] == []
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_conflicting_drafts_cannot_both_be_future_ready(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  related_write_intents=[_related(gate)])
    assert o["ready_for_future_commit_only"] is False
    assert o["commit_executable_now"] is False


def test_clean_draft_is_future_ready(gate):
    o = k.clean_outcome(gate)
    assert o["ready_for_future_commit_only"] is True


def test_blocking_conflict_only_warning_framing_still_blocks(gate):
    # Malicious "the blocking conflict is only a warning" framing must not
    # downgrade the outcome to an escrow draft.
    o = k.prepare(gate, k.b6_outcome(gate),
                  intent="blocking conflict is only warning",
                  related_write_intents=[_related(gate)])
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_graph_hash_excludes_itself_and_recomputes(gate):
    g = k.clean_outcome(gate)["concurrent_draft_conflict_graph"]
    recomputed = _core_hash(g, "concurrent_draft_conflict_graph_hash", "signal")
    assert recomputed == g["concurrent_draft_conflict_graph_hash"]


def test_blocking_conflict_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    blocked = k.prepare(gate, b6, related_write_intents=[_related(gate)])
    assert clean["write_intent_decision_hash"] != \
        blocked["write_intent_decision_hash"]
    assert clean["concurrent_draft_conflict_graph"][
        "concurrent_draft_conflict_graph_hash"] != \
        blocked["concurrent_draft_conflict_graph"][
            "concurrent_draft_conflict_graph_hash"]


def test_endpoint_returns_graph(gate):
    wid, _ = gate.prepared_write_intent()
    g = gate.wi(wid, "/concurrent-draft-conflicts").json()[
        "concurrent_draft_conflict_graph"]
    assert g["graph_status"] == "CLEAR"

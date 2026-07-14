"""TOOL-B9.2 v5: Governed Work Lineage Observatory — causal work graph (19),
consistent work cut (20), negative-space work sentinel (21) and Work Observation
Twin (23).

These are DERIVED-EVIDENCE-ONLY structures: the causal graph and consistent cut
describe lineage over B9/B9.1 evidence, the negative-space sentinel proves nothing
critical is missing, and the twin is an immutable, append-only, non-authoritative
mirror of the observation. None of them grant authority or produce external effect.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from finalis.ai_employee import tool_work_observability as wo
from tests import _b92_kernel as k


# --- kernel layer: causal work graph (section 19) --------------------------
def test_graphev_causal_graph_clean_shape():
    g = k.clean_outcome()["causal_work_graph"]
    assert g["node_count"] == 15
    assert g["edge_count"] == 12
    assert len(g["nodes"]) == 15
    assert len(g["edges"]) == 12


def test_graphev_causal_graph_type_catalogs():
    g = k.clean_outcome()["causal_work_graph"]
    assert g["node_types"] == wo.GRAPH_NODE_TYPES
    assert g["edge_types"] == wo.GRAPH_EDGE_TYPES


def test_graphev_causal_graph_hash_recompute():
    g = k.clean_outcome()["causal_work_graph"]
    assert _core_hash(g, "causal_work_graph_hash") == g["causal_work_graph_hash"]


# --- kernel layer: consistent work cut (section 20) ------------------------
def test_graphev_consistent_cut_clean_valid():
    c = k.clean_outcome()["consistent_work_cut"]
    assert c["consistent_cut_valid"] is True
    assert c["no_cross_tenant_edge"] is True
    assert c["cut_status"] == "VALID"
    assert c["signal"] is None


def test_graphev_incompatible_versions_contradicted():
    o = k.prepare(incompatible_versions=True)
    assert o["consistent_work_cut"]["consistent_cut_valid"] is False
    assert o["consistent_work_cut"]["source_versions_compatible"] is False
    assert "CONSISTENT_WORK_CUT_INVALID" in o["all_signals"]
    assert o["work_outcome_truth_state"] == "CONTRADICTED"
    assert o["work_run_state"] == "QUARANTINED"
    assert o["proof_of_work_outcome_valid"] is False


def test_graphev_cross_tenant_edge_flag_contradicted():
    o = k.prepare(cross_tenant_edge=True)
    assert o["consistent_work_cut"]["no_cross_tenant_edge"] is False
    assert "CROSS_TENANT_WORK_EDGE" in o["all_signals"]
    assert o["work_outcome_truth_state"] == "CONTRADICTED"
    assert o["work_run_state"] == "QUARANTINED"


def test_graphev_cross_tenant_b9_evidence_rejected():
    # clean_b9 tenant is "t1"; observing it under tenant "OTHER" is a cross-tenant
    # work edge and must be contradicted, never silently accepted.
    o = k.prepare(b9_outcome=k.clean_b9(), tenant_id="OTHER")
    assert "CROSS_TENANT_WORK_EDGE" in o["all_signals"]
    assert o["work_outcome_truth_state"] == "CONTRADICTED"
    assert o["consistent_work_cut"]["no_cross_tenant_edge"] is False
    assert o["proof_of_work_outcome_valid"] is False
    # No external effect even on a contradicted cross-tenant observation.
    assert o["produced_external_effect"] is False
    assert o["outbox_released"] is False


def test_graphev_consistent_cut_hash_recompute():
    c = k.clean_outcome()["consistent_work_cut"]
    assert _core_hash(c, "consistent_cut_hash", "signal") == c[
        "consistent_cut_hash"]


# --- kernel layer: negative-space work sentinel (section 21) ---------------
def test_graphev_negative_space_clean_complete():
    n = k.clean_outcome()["negative_space"]
    assert n["no_critical_missing"] is True
    assert n["sentinel_status"] == "COMPLETE"
    assert n["missing"] == []
    assert n["expected"] == wo.EXPECTED_WORK_EVIDENCE


def test_graphev_negative_space_missing_transaction_binding():
    o = k.prepare(bind_b9=False)
    n = o["negative_space"]
    assert "transaction_binding" in n["missing"]
    assert "transaction_binding" in n["missing_critical"]
    assert n["no_critical_missing"] is False
    assert n["sentinel_status"] == "INCOMPLETE"
    assert "CRITICAL_WORK_EVIDENCE_MISSING" in o["all_signals"]


def test_graphev_negative_space_hash_recompute():
    n = k.clean_outcome()["negative_space"]
    assert _core_hash(n, "negative_space_hash", "signal",
                      "missing_evidence_hash") == n["negative_space_hash"]


# --- kernel layer: Work Observation Twin (section 23) ----------------------
def test_graphev_twin_immutable_append_only_non_authoritative():
    t = k.clean_outcome()["work_observation_twin"]
    assert t["immutable"] is True
    assert t["append_only"] is True
    assert t["non_authoritative"] is True


def test_graphev_twin_carries_truth_and_component_statuses():
    t = k.clean_outcome()["work_observation_twin"]
    assert t["work_outcome_truth_state"] == "PROVEN"
    assert t["work_run_state"] == "WORK_OUTCOME_CERTIFIED"
    assert t["transaction_status"] == "VALID"
    assert t["powo_status"] == "VALID"
    assert t["observer_health_status"] == "OBSERVER_HEALTHY"
    for key in ("trigger_status", "identity_continuity_status",
                "context_continuity_status", "memory_provenance_status",
                "delegation_status", "approval_continuity_status",
                "gateway_boundary_status", "artifact_lineage_status",
                "delivery_intent_status"):
        assert key in t


def test_graphev_twin_mirrors_graph_and_negative_space_hashes():
    o = k.clean_outcome()
    t = o["work_observation_twin"]
    assert t["causal_graph_hash"] == o["causal_work_graph"][
        "causal_work_graph_hash"]
    assert t["missing_evidence_hash"] == o["negative_space"][
        "missing_evidence_hash"]


def test_graphev_twin_hash_recompute():
    t = k.clean_outcome()["work_observation_twin"]
    assert _core_hash(t, "twin_hash") == t["twin_hash"]


def test_graphev_all_evidence_hashes_recompute_together():
    o = k.clean_outcome()
    g, c = o["causal_work_graph"], o["consistent_work_cut"]
    n, t = o["negative_space"], o["work_observation_twin"]
    assert _core_hash(g, "causal_work_graph_hash") == g["causal_work_graph_hash"]
    assert _core_hash(c, "consistent_cut_hash", "signal") == c[
        "consistent_cut_hash"]
    assert _core_hash(n, "negative_space_hash", "signal",
                      "missing_evidence_hash") == n["negative_space_hash"]
    assert _core_hash(t, "twin_hash") == t["twin_hash"]


# --- API layer -------------------------------------------------------------
def test_graphev_api_causal_graph_endpoint(gate):
    wrid, _ = gate.observed_work()
    r = gate.wo(wrid, "causal-graph")
    assert r.status_code == 200
    g = r.json()["causal_work_graph"]
    assert g["node_count"] == 15
    assert g["edge_count"] == 12
    assert g["node_types"] == wo.GRAPH_NODE_TYPES


def test_graphev_api_consistent_cut_endpoint(gate):
    wrid, _ = gate.observed_work()
    r = gate.wo(wrid, "consistent-cut")
    assert r.status_code == 200
    c = r.json()["consistent_work_cut"]
    assert c["consistent_cut_valid"] is True
    assert c["no_cross_tenant_edge"] is True


def test_graphev_api_missing_evidence_endpoint(gate):
    wrid, _ = gate.observed_work()
    r = gate.wo(wrid, "missing-evidence")
    assert r.status_code == 200
    n = r.json()["negative_space"]
    assert n["no_critical_missing"] is True
    assert n["expected"] == wo.EXPECTED_WORK_EVIDENCE


def test_graphev_api_twin_endpoint(gate):
    wrid, _ = gate.observed_work()
    r = gate.wo(wrid, "twin")
    assert r.status_code == 200
    t = r.json()["work_observation_twin"]
    assert t["immutable"] is True
    assert t["non_authoritative"] is True
    assert t["work_outcome_truth_state"] == "PROVEN"

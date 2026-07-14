"""Fixture builders for SP0003 program-graph tests."""
from __future__ import annotations


def node(nid, ntype="SP", status="NOT_STARTED", **kw):
    n = {"node_id": nid, "node_type": ntype, "canonical_name": nid,
         "status": status, "status_source": "DECLARED", "resource_keys": [],
         "risk_tags": []}
    n.update(kw)
    return n


def edge(head, tails, logic="ALL_OF", status="ACTIVE",
         dtype="ARCHITECTURE_PRECONDITION", threshold_k=None,
         scenario_condition=None, active_ok=True, **kw):
    e = {"dependency_id": kw.pop("dependency_id", f"d-{head}-{'_'.join(tails)}"),
         "tail_nodes": list(tails), "head_node": head, "logic": logic,
         "status": status, "dependency_type": dtype,
         "scenario_condition": scenario_condition}
    if active_ok and status == "ACTIVE":
        e.setdefault("reason", "test rationale")
        e.setdefault("failure_if_bypassed", "test failure")
        e.setdefault("evidence_refs", ["test-evidence"])
        e.setdefault("admitted_by", "ARCHITECTURE_REVIEW")
    if threshold_k is not None:
        e["threshold_k"] = threshold_k
    e.update(kw)
    return e


def complete_node(nid, ntype="SP", **kw):
    return node(nid, ntype=ntype, status="COMPLETE", status_source="EVIDENCE_DERIVED", **kw)


def sp_evidence(nid):
    return [{"node_id": nid, "kind": k, "ref": "x"} for k in
            ("final_commit", "acceptance_matrix", "test_evidence", "p0p1_status")]


def program(nodes=None, hyperedges=None, **kw):
    p = {"nodes": nodes or [], "hyperedges": hyperedges or [],
         "threshold_gates": [], "scenarios": [
             {"scenario_id": "BASELINE", "variables": {}, "status": "ACTIVE"}],
         "gates": [], "gate_bindings": [], "conflicts": [], "rework_edges": [],
         "risk_correlations": [], "completion_evidence": [],
         "temporal_constraints": [], "duration_models": [], "uncertainties": []}
    p.update(kw)
    return p

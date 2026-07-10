"""TOOL-B9 v5: proof-carrying local action certificate + semantic transaction
graph + replay context.

The certificate is a proof-carrying attestation of a LOCAL, REVERSIBLE commit:
it is NOT authority and NOT a commit lease, it forbids every external effect,
and it is replayable for audit only. The semantic graph and replay context
render the full deterministic derivation. Contaminating the authority basis
changes the decision hash. B8 is evidence only; NO external effect.
"""
from finalis.ai_employee.tool_local_transaction import _core_hash
from finalis.ai_employee import tool_local_transaction as lt
from tests import _b9_kernel as k
from tests.conftest import OWNER


# --- kernel layer ----------------------------------------------------------
def test_cert_clean_certificate_is_valid():
    cert = k.clean_outcome()["certificate"]
    assert cert["verification_status"] == "VALID"
    assert cert["is_authority"] is False
    assert cert["is_commit_lease"] is False
    assert cert["replayable_for_audit"] is True


def test_cert_forbids_every_external_effect():
    cert = k.clean_outcome()["certificate"]
    for banned in ("EXTERNAL_EFFECT", "PROVIDER_CALL", "MESSAGE_SEND",
                   "PAYMENT"):
        assert banned in cert["forbidden"]


def test_cert_hash_recomputes_with_special_excludes():
    cert = k.clean_outcome()["certificate"]
    assert _core_hash(cert, "certificate_hash", "verification_status") == \
        cert["certificate_hash"]


def test_cert_basis_reflects_inputs():
    o = k.clean_outcome(
        authority_basis={"source": "TENANT_POLICY"},
        evidence_refs=["ev-9"], policy_refs=["pol-9"],
        approval_record={"server_verified": True, "refs": ["ap-9", "ap-2"]})
    cert = o["certificate"]
    assert o["local_commit_applied"] is True
    assert cert["authority_basis"] == {"source": "TENANT_POLICY"}
    assert cert["evidence_basis"] == ["ev-9"]
    assert cert["policy_basis"] == ["pol-9"]
    assert cert["approval_basis"]["present"] is True
    assert cert["approval_basis"]["refs"] == ["ap-2", "ap-9"]


def test_cert_default_authority_basis_is_server_rbac():
    cert = k.clean_outcome()["certificate"]
    assert cert["authority_basis"] == {"source": "SERVER_RBAC"}
    assert cert["approval_basis"]["present"] is True


def test_cert_semantic_graph_has_18_nodes_16_edges():
    graph = k.clean_outcome()["semantic_graph"]
    assert graph["node_count"] == 18
    assert graph["edge_count"] == 16
    assert len(graph["nodes"]) == 18
    assert len(graph["edges"]) == 16


def test_cert_semantic_graph_is_complete():
    graph = k.clean_outcome()["semantic_graph"]
    assert graph["graph_status"] == "COMPLETE"
    assert graph["missing_nodes"] == []
    assert graph["missing_edges"] == []
    assert {n["node_type"] for n in graph["nodes"]} == set(lt.GRAPH_NODE_TYPES)


def test_cert_semantic_graph_hash_recomputes():
    graph = k.clean_outcome()["semantic_graph"]
    assert _core_hash(graph, "semantic_graph_hash", "signal") == graph[
        "semantic_graph_hash"]


def test_cert_replay_context_is_replayable():
    replay = k.clean_outcome()["replay_context"]
    assert replay["replay_status"] == "REPLAYABLE"
    assert replay["executes_production_effects"] is False
    assert replay["audit_only"] is True


def test_cert_replay_context_binds_certificate_and_stream():
    o = k.clean_outcome()
    assert o["replay_context"]["certificate_hash"] == o["certificate"][
        "certificate_hash"]
    assert o["replay_context"]["event_stream_hash"] == o["poe_stream"][
        "poe_stream_hash"]


def test_cert_replay_context_hash_recomputes():
    replay = k.clean_outcome()["replay_context"]
    assert _core_hash(replay, "replay_context_hash") == replay[
        "replay_context_hash"]


def test_cert_contaminated_authority_changes_decision_hash():
    clean = k.prepare()["b9_decision_hash"]
    contaminated = k.prepare(
        authority_basis={"source": "DOCUMENT"})["b9_decision_hash"]
    assert clean != contaminated


def test_cert_contaminated_authority_quarantines_no_certificate_commit():
    o = k.prepare(authority_basis={"source": "DOCUMENT"})
    assert o["b9_status"] == "B9_QUARANTINED"
    assert o["dominant_signal"] == "DOCUMENT_AS_COMMAND_REJECTED"
    assert o["certificate"]["is_authority"] is False
    assert o["local_commit_applied"] is False


# --- API layer -------------------------------------------------------------
def test_cert_api_certificate_endpoint(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    body = gate.lt(tid, "/certificate").json()
    cert = body["certificate"]
    assert cert["verification_status"] == "VALID"
    assert cert["is_authority"] is False
    assert cert["is_commit_lease"] is False
    assert "NO_EXTERNAL_EFFECT" in body["honesty_labels"]


def test_cert_api_graph_endpoint(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    body = gate.lt(tid, "/graph").json()
    graph = body["semantic_graph"]
    assert graph["node_count"] == 18
    assert graph["edge_count"] == 16
    assert graph["graph_status"] == "COMPLETE"
    assert "NO_EXTERNAL_EFFECT" in body["honesty_labels"]


def test_cert_api_replay_context_endpoint(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    body = gate.lt(tid, "/replay-context").json()
    replay = body["replay_context"]
    assert replay["replay_status"] == "REPLAYABLE"
    assert replay["executes_production_effects"] is False
    assert replay["audit_only"] is True
    assert "NO_EXTERNAL_EFFECT" in body["honesty_labels"]


def test_cert_api_certificate_hash_recomputes_from_endpoint(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    cert = gate.lt(tid, "/certificate").json()["certificate"]
    assert _core_hash(cert, "certificate_hash", "verification_status") == \
        cert["certificate_hash"]

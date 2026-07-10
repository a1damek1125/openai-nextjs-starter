"""TOOL-B8 v5: Evidence closure net — every proof node/edge is structurally
present and every claim is closed; a structural gap or an unclosed claim blocks
with EVIDENCE_CLOSURE_NET_FAILED. Evidence only; never authority."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_net_exists_and_clean_closed(gate):
    net = k.clean_outcome(gate)["evidence_closure_net"]
    assert net["evidence_closure_net_id"].startswith("ecn-")
    assert net["closure_status"] == "CLOSED"
    assert net["missing_required_nodes"] == []
    assert net["missing_required_edges"] == []
    assert net["unclosed_claims"] == []


def test_clean_nodes_and_edges_present(gate):
    net = k.clean_outcome(gate)["evidence_closure_net"]
    assert net["nodes"] and net["edges"]
    node_types = {n["node_type"] for n in net["nodes"]}
    assert "B9_FIREWALL" in node_types and "ASSURANCE_ENVELOPE" in node_types
    assert all(n["present"] is True for n in net["nodes"])


def test_unclosed_claim_blocks(gate):
    o = k.clean_outcome(gate, force_unclosed_claims=["NO_COMMIT_THEOREM"])
    net = o["evidence_closure_net"]
    assert net["closure_status"] == "OPEN"
    assert "NO_COMMIT_THEOREM" in net["unclosed_claims"]
    assert net["signal"] == "EVIDENCE_CLOSURE_NET_FAILED"
    assert o["dominant_signal"] == "EVIDENCE_CLOSURE_NET_FAILED"
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_missing_required_edge_blocks(gate):
    o = k.clean_outcome(
        gate, force_missing_edges=["B9_FIREWALL->ASSURANCE_ENVELOPE"])
    net = o["evidence_closure_net"]
    assert "B9_FIREWALL->ASSURANCE_ENVELOPE" in net["missing_required_edges"]
    assert net["signal"] == "EVIDENCE_CLOSURE_NET_FAILED"
    assert o["dominant_signal"] == "EVIDENCE_CLOSURE_NET_FAILED"


def test_missing_required_node_blocks(gate):
    o = k.clean_outcome(gate, force_missing_nodes=["B9_FIREWALL"])
    net = o["evidence_closure_net"]
    assert "B9_FIREWALL" in net["missing_required_nodes"]
    assert net["closure_status"] == "OPEN"
    assert o["dominant_signal"] == "EVIDENCE_CLOSURE_NET_FAILED"
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_closure_failure_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    broken = k.prepare(gate, b7, force_unclosed_claims=["NO_COMMIT_THEOREM"])[
        "commit_simulation_decision_hash"]
    assert clean != broken


def test_missing_node_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    broken = k.prepare(gate, b7, force_missing_nodes=["B9_FIREWALL"])[
        "commit_simulation_decision_hash"]
    assert clean != broken


def test_hash_recomputes(gate):
    net = k.clean_outcome(gate)["evidence_closure_net"]
    recomputed = _core_hash(net, "evidence_closure_net_hash", "signal")
    assert recomputed == net["evidence_closure_net_hash"]


def test_never_authority(gate):
    o = k.clean_outcome(gate)
    assert o["artifacts_are_authority"] is False
    assert o["b9_revalidation_required"] is True
    assert o["commit_executable_now"] is False


def test_api_endpoint_returns_closed_net(gate):
    sid, _ = gate.prepared_commit_simulation()
    r = gate.cs(sid, "/evidence-closure-net")
    assert r.status_code == 200
    net = r.json()["evidence_closure_net"]
    assert net["closure_status"] == "CLOSED"
    assert net["missing_required_nodes"] == []
    assert net["missing_required_edges"] == []


def test_api_verify_valid_on_clean(gate):
    sid, _ = gate.prepared_commit_simulation()
    v = gate.cs(sid, "/verify", method="POST").json()
    assert v["verification_status"] == "VALID"

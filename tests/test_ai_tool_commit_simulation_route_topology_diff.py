"""TOOL-B8 v5: Route topology diff guard — no commit/execute/release/activate/
provider-call route may be inserted into the surface. Any forbidden POST-action
route blocks with ROUTE_TOPOLOGY_DIFF_FORBIDDEN; GET evidence routes are never
forbidden."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_guard_exists_and_clean(gate):
    d = k.clean_outcome(gate)["route_topology_diff"]
    assert d["route_topology_diff_id"].startswith("rtd-")
    assert d["diff_status"] == "CLEAN"
    assert d["forbidden_semantic_routes"] == []
    assert d["signal"] is None


def test_inserted_commit_route_blocks(gate):
    o = k.clean_outcome(
        gate, added_routes=[{"path": "/x/commit", "method": "POST"}])
    d = o["route_topology_diff"]
    assert d["diff_status"] == "FORBIDDEN"
    assert any(f["semantic"] == "COMMIT" for f in d["forbidden_semantic_routes"])
    assert d["signal"] == "ROUTE_TOPOLOGY_DIFF_FORBIDDEN"
    assert o["dominant_signal"] == "ROUTE_TOPOLOGY_DIFF_FORBIDDEN"
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_release_effects_route_blocks(gate):
    o = k.clean_outcome(
        gate, added_routes=[{"path": "/x/release-effects", "method": "POST"}])
    d = o["route_topology_diff"]
    assert any(f["semantic"] == "RELEASE_EFFECTS"
               for f in d["forbidden_semantic_routes"])
    assert o["dominant_signal"] == "ROUTE_TOPOLOGY_DIFF_FORBIDDEN"


def test_activate_b9_route_blocks(gate):
    o = k.clean_outcome(
        gate, added_routes=[{"path": "/x/activate-b9", "method": "POST"}])
    d = o["route_topology_diff"]
    assert any(f["semantic"] == "ACTIVATE_B9"
               for f in d["forbidden_semantic_routes"])
    assert o["dominant_signal"] == "ROUTE_TOPOLOGY_DIFF_FORBIDDEN"


def test_provider_mcp_llm_call_routes_block(gate):
    b7 = k.b7_outcome(gate)
    for path, sem in [("/provider/call", "PROVIDER_CALL"),
                      ("/mcp/call", "MCP_CALL"), ("/llm/call", "LLM_CALL")]:
        o = k.prepare(
            gate, b7, added_routes=[{"path": path, "method": "POST"}])
        d = o["route_topology_diff"]
        assert any(f["semantic"] == sem
                   for f in d["forbidden_semantic_routes"]), path
        assert o["dominant_signal"] == "ROUTE_TOPOLOGY_DIFF_FORBIDDEN", path


def test_get_method_route_not_forbidden(gate):
    o = k.clean_outcome(
        gate, added_routes=[{"path": "/x/commit", "method": "GET"}])
    d = o["route_topology_diff"]
    assert d["diff_status"] == "CLEAN"
    assert d["forbidden_semantic_routes"] == []
    assert o["commit_simulation_status"] == "B8_V5_ACCEPTED"


def test_fingerprints_present(gate):
    d = k.clean_outcome(gate)["route_topology_diff"]
    assert d["baseline_route_fingerprint"]
    assert d["final_route_fingerprint"]


def test_forbidden_route_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    forbidden = k.prepare(
        gate, b7, added_routes=[{"path": "/x/commit", "method": "POST"}])[
        "commit_simulation_decision_hash"]
    assert clean != forbidden


def test_hash_recomputes(gate):
    d = k.clean_outcome(gate)["route_topology_diff"]
    recomputed = _core_hash(d, "route_topology_diff_hash", "signal")
    assert recomputed == d["route_topology_diff_hash"]


def test_never_authority(gate):
    o = k.clean_outcome(gate)
    assert o["commit_executable_now"] is False
    assert o["released_effect"] is False
    assert o["activated_b9"] is False


def test_api_endpoint_returns_clean_diff(gate):
    sid, _ = gate.prepared_commit_simulation()
    r = gate.cs(sid, "/route-topology-diff")
    assert r.status_code == 200
    d = r.json()["route_topology_diff"]
    assert d["diff_status"] == "CLEAN"
    assert d["forbidden_semantic_routes"] == []

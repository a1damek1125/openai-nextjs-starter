"""TOOL-B3 runtime capability deny graph tests.

The contract denies every runtime capability by construction: the deny graph
lists all 18 RUNTIME_CAPABILITIES, contains a CONTRACT node plus one node per
capability, and a DENIES edge from the contract to each capability. It always
reports MATCHED (there is no runtime to allow). These assert the graph via the
kernel and the GET /runtime-deny-graph endpoint.
"""
from finalis.ai_employee import tool_contracts as tc


class TestDeniedCapabilities:
    def test_denied_equals_full_runtime_set(self, gate):
        tid, c = gate.contracted_tool()
        dg = c["runtime_capability_deny_graph"]
        assert dg["denied_capabilities"] == list(tc.RUNTIME_CAPABILITIES)

    def test_exactly_eighteen_denied(self, gate):
        tid, c = gate.contracted_tool()
        dg = c["runtime_capability_deny_graph"]
        assert len(dg["denied_capabilities"]) == 18
        assert len(set(dg["denied_capabilities"])) == 18

    def test_key_runtime_capabilities_denied(self, gate):
        tid, c = gate.contracted_tool()
        denied = set(c["runtime_capability_deny_graph"]["denied_capabilities"])
        for cap in ("MCP_SAMPLING", "MCP_ELICITATION", "OAUTH_TOKEN_ISSUANCE",
                    "LLM_CALL", "TOOL_BROKER_CALL", "PROVIDER_CALL",
                    "MCP_RESOURCE_SERVING", "MCP_PROMPT_SERVING",
                    "PAYMENT_EXECUTION", "SECRET_ACCESS",
                    "NETWORK_SIDE_EFFECT"):
            assert cap in denied, cap

    def test_status_matched(self, gate):
        tid, c = gate.contracted_tool()
        assert c["runtime_capability_deny_graph"][
            "deny_graph_status"] == "MATCHED"


class TestGraphStructure:
    def test_contract_node_plus_capability_nodes(self, gate):
        tid, c = gate.contracted_tool()
        dg = c["runtime_capability_deny_graph"]
        assert len(dg["nodes"]) == len(tc.RUNTIME_CAPABILITIES) + 1
        kinds = [n["node"] for n in dg["nodes"]]
        assert kinds.count("CONTRACT") == 1
        assert kinds.count("RUNTIME_CAPABILITY") == len(tc.RUNTIME_CAPABILITIES)

    def test_every_capability_has_deny_edge(self, gate):
        tid, c = gate.contracted_tool()
        dg = c["runtime_capability_deny_graph"]
        cid = c["contract_id"]
        assert len(dg["edges"]) == len(tc.RUNTIME_CAPABILITIES)
        for e in dg["edges"]:
            assert e["type"] == "DENIES"
            assert e["from"] == cid
        edge_targets = {e["to"] for e in dg["edges"]}
        assert edge_targets == set(tc.RUNTIME_CAPABILITIES)

    def test_no_allow_edges(self, gate):
        tid, c = gate.contracted_tool()
        dg = c["runtime_capability_deny_graph"]
        assert all(e["type"] == "DENIES" for e in dg["edges"])

    def test_capability_node_ids_cover_all(self, gate):
        tid, c = gate.contracted_tool()
        dg = c["runtime_capability_deny_graph"]
        cap_nodes = {n["id"] for n in dg["nodes"]
                     if n["node"] == "RUNTIME_CAPABILITY"}
        assert cap_nodes == set(tc.RUNTIME_CAPABILITIES)


class TestDenyGraphIsUnconditional:
    def test_runtime_requested_still_denies_all(self, gate):
        # Even a (rejected) runtime-requesting contract denies the full set.
        tid = gate.contract_tool()
        c = gate.create_contract(tid, runtime_requested=True).json()
        dg = c["runtime_capability_deny_graph"]
        assert dg["denied_capabilities"] == list(tc.RUNTIME_CAPABILITIES)
        assert dg["deny_graph_status"] == "MATCHED"


class TestHashAndEndpoint:
    def test_deny_graph_hash_deterministic(self, gate):
        g1 = tc.build_deny_graph(tenant_id="t", contract_id="c", tool_id="x")
        g2 = tc.build_deny_graph(tenant_id="t", contract_id="c", tool_id="x")
        assert g1["deny_graph_hash"] == g2["deny_graph_hash"]
        assert tc._core_hash(g1, "deny_graph_hash") == g1["deny_graph_hash"]

    def test_get_runtime_deny_graph_endpoint(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/runtime-deny-graph")
        assert r.status_code == 200
        dg = r.json()["runtime_capability_deny_graph"]
        assert set(dg["denied_capabilities"]) == set(tc.RUNTIME_CAPABILITIES)
        assert dg["deny_graph_status"] == "MATCHED"
        assert dg == c["runtime_capability_deny_graph"]

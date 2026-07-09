"""TOOL-B3 — ViktorAI Formal Protocol Contract Proof Kernel: HTTP surface.

Every contract read endpoint exists and returns 200 for the owner on a clean
contracted tool; the create endpoint yields a PROJECTABLE_FOR_FUTURE contract;
projection-derived reads work off the default projection built at create time.
Nothing here executes a tool.
"""
from conftest import OWNER, OTHER_OWNER

# Read endpoints that read directly off the stored contract payload.
CONTRACT_READS = [
    "/safe", "/versions", "/normal-form", "/abi", "/effect-trace",
    "/method-firewall", "/runtime-deny-graph", "/separation", "/scope", "/auth",
    "/traceability", "/protocol", "/boundaries",
]
# Read endpoints that read off the default projection built at create time.
PROJECTION_READS = [
    "/obligations", "/proof-bundle", "/broker-readiness", "/proof-obligations",
    "/non-interference", "/provenance",
]
# Read endpoints that build a fresh validation-only projection on demand.
SHAPE_READS = ["/mcp-like", "/apps-sdk-like", "/openapi-like", "/compatibility",
               "/revocation-ledger"]


def _labels_ok(payload):
    hl = payload.get("honesty_labels")
    return isinstance(hl, list) and len(hl) > 0


class TestCreate:
    def test_clean_admitted_tool_is_projectable_for_future(self, gate):
        tid = gate.contract_tool()
        c = gate.create_contract(tid).json()
        assert c["contract_status"] == "PROJECTABLE_FOR_FUTURE"

    def test_create_carries_honesty_labels(self, gate):
        tid, c = gate.contracted_tool()
        assert _labels_ok(c)

    def test_create_stores_source_identity(self, gate):
        tid, c = gate.contracted_tool()
        assert c["tenant_id"]
        assert c["tool_id"] == tid
        assert c["tool_version_id"]
        assert c["contract_target"] == "INTERNAL_TOOL_BROKER_CONTRACT"
        assert c["requires_future_tool_broker"] is True

    def test_create_never_permits_execution_now(self, gate):
        tid, c = gate.contracted_tool()
        # A contract is future-broker metadata; it does not execute.
        assert c["contract_non_execution_proof"]["proof_status"] == "MATCHED"
        assert c["contract_non_execution_proof"]["failed_items"] == []


class TestReadEndpoints:
    def test_get_contract_returns_payload(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"])
        assert r.status_code == 200
        assert r.json()["contract_id"] == c["contract_id"]

    def test_unknown_contract_404(self, gate):
        tid = gate.contract_tool()
        assert gate.ct(tid, "does-not-exist").status_code == 404

    def test_all_contract_reads_200_for_owner(self, gate):
        tid, c = gate.contracted_tool()
        cid = c["contract_id"]
        for path in CONTRACT_READS:
            r = gate.ct(tid, cid, path=path)
            assert r.status_code == 200, (path, r.status_code)
            assert _labels_ok(r.json()), path

    def test_projection_derived_reads_work_off_default_projection(self, gate):
        # create builds a default INTERNAL_TOOL_BROKER_CONTRACT projection, so
        # these reads resolve without an explicit /project call.
        tid, c = gate.contracted_tool()
        cid = c["contract_id"]
        for path in PROJECTION_READS:
            r = gate.ct(tid, cid, path=path)
            assert r.status_code == 200, (path, r.status_code)
            assert r.json()["projection_id"]
            assert _labels_ok(r.json()), path

    def test_shape_and_aggregate_reads_200_for_owner(self, gate):
        tid, c = gate.contracted_tool()
        cid = c["contract_id"]
        for path in SHAPE_READS:
            r = gate.ct(tid, cid, path=path)
            assert r.status_code == 200, (path, r.status_code)
            assert _labels_ok(r.json()), path

    def test_mcp_like_shape_is_marked_non_runtime(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], path="/mcp-like").json()
        assert r["projectable"] is True
        assert "future Tool Broker required" in r["projection_note"]
        assert "_protocol_note" in r["shape"]

    def test_boundaries_endpoint_exposes_three_boundaries(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], path="/boundaries").json()
        assert "data_boundary" in r
        assert "effect_boundary" in r
        assert "prompt_context_boundary" in r


class TestListAndRegistry:
    def test_list_contracts_contains_created(self, gate):
        tid, c = gate.contracted_tool()
        listed = gate.c.get(f"/ai-tools/{tid}/contracts",
                            headers=gate.h(OWNER)).json()
        assert c["contract_id"] in [x["contract_id"] for x in listed]

    def test_registry_summary_counts_contract(self, gate):
        tid, c = gate.contracted_tool()
        reg = gate.c.get("/ai-tools/registry/contracts",
                        headers=gate.h(OWNER)).json()
        assert reg["contract_count"] >= 1
        assert reg["contracts_by_status"].get("PROJECTABLE_FOR_FUTURE", 0) >= 1
        assert c["contract_id"] in [s["contract_id"] for s in reg["summaries"]]
        assert _labels_ok(reg)

    def test_registry_policy_denies_runtime(self, gate):
        pol = gate.c.get("/ai-tools/registry/contracts/policy",
                        headers=gate.h(OWNER)).json()
        assert pol["executes_tools"] is False
        assert pol["is_mcp_server"] is False
        assert pol["calls_tool_broker"] is False
        assert pol["certificate_can_override_blockers"] is False
        assert len(pol["runtime_capabilities_denied"]) == 18
        assert _labels_ok(pol)

    def test_registry_endpoints_are_tenant_scoped(self, gate):
        gate.contracted_tool()
        reg = gate.c.get("/ai-tools/registry/contracts",
                        headers=gate.h(OTHER_OWNER)).json()
        assert reg["contract_count"] == 0

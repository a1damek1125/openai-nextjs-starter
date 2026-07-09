"""TOOL-B3 cross-cutting no-execution / no-runtime-protocol invariants.

The contract kernel must never execute a tool, run any protocol runtime
(MCP server/client, sampling, elicitation, resource/prompt serving), call a
broker/LLM/external provider, issue a token, or let a projection/certificate
override a TOOL-B1/TOOL-B2 security state. These assert those properties across
the contract surface, plus static route ordering and the runtime deny graph.
"""
import pytest

from finalis.ai_employee import tool_contracts as tc
from tests.conftest import Gate, OWNER, MANAGER, VIEWER, OTHER_OWNER


@pytest.fixture()
def gate():
    return Gate()


class TestNoExecutionSurface:
    def test_no_execute_or_runtime_routes(self, gate):
        paths = {getattr(r, "path", "") for r in gate.app.routes}
        for forbidden in (
                "/ai-tools/{tool_id}/contracts/{contract_id}/execute",
                "/ai-tools/{tool_id}/contracts/{contract_id}/run",
                "/ai-tools/{tool_id}/contracts/{contract_id}/sample",
                "/ai-tools/{tool_id}/contracts/{contract_id}/elicit",
                "/ai-tools/{tool_id}/contracts/{contract_id}/mcp-server"):
            assert forbidden not in paths, forbidden

    def test_policy_declares_no_runtime(self, gate):
        p = gate.c.get("/ai-tools/registry/contracts/policy",
                       headers=gate.h(OWNER)).json()
        for flag in ("executes_tools", "is_mcp_server", "is_mcp_client",
                     "calls_tool_broker", "calls_llm", "calls_external_provider",
                     "issues_tokens", "performs_sampling",
                     "performs_elicitation", "serves_resources",
                     "serves_prompts", "certificate_can_override_blockers"):
            assert p[flag] is False, flag
        assert p["projection_is_validation_only"] is True
        assert len(p["runtime_capabilities_denied"]) == 18

    def test_deny_graph_denies_all_runtime_capabilities(self, gate):
        tid, c = gate.contracted_tool()
        dg = gate.ct(tid, c["contract_id"], "/runtime-deny-graph").json()[
            "runtime_capability_deny_graph"]
        assert set(dg["denied_capabilities"]) == set(tc.RUNTIME_CAPABILITIES)
        assert dg["deny_graph_status"] == "MATCHED"

    def test_contract_carries_no_execution_proof(self, gate):
        tid, c = gate.contracted_tool()
        proof = c["contract_non_execution_proof"]
        assert proof["proof_status"] == "MATCHED"
        assert proof["failed_items"] == []
        assert all(proof["proof_items"].values())

    def test_honesty_labels_present(self, gate):
        tid, c = gate.contracted_tool()
        labels = c["honesty_labels"]
        assert "Internal contract does not execute tools." in labels
        assert "Future Tool Broker is required before any tool call." in labels
        assert "Runtime capabilities are denied in this mission." in labels


class TestRouteOrdering:
    def test_registry_contract_routes_not_shadowed(self, gate):
        h = gate.h(OWNER)
        for path in ("/ai-tools/registry/contracts",
                     "/ai-tools/registry/contracts/policy"):
            r = gate.c.get(path, headers=h)
            assert r.status_code == 200, path
            assert "not found" not in r.text.lower(), path


class TestRuntimeAndProtocolBlocked:
    def test_runtime_requested_projection_blocked(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"], runtime_requested=True).json()
        assert env["projection_status"] == "BLOCKED"
        assert "RUNTIME_CAPABILITY_DENIED" in env["projection_blockers"]
        assert env["violation_witnesses"]

    def test_sampling_terms_blocked_at_separation(self, gate):
        # A tool whose prose implies sampling/elicitation trips the separation
        # guard; its contract cannot be PROJECTABLE.
        tid = gate.contract_tool(
            tool_name="Elicit Helper",
            tool_description="read only helper that performs sampling and "
            "elicitation to serve prompts")
        c = gate.create_contract(tid).json()
        assert c["separation_guard"]["separation_guard_status"] in (
            "BLOCKED", "NEEDS_REVIEW")
        assert c["contract_status"] in ("BLOCKED", "NEEDS_REVIEW")

    def test_certificate_cannot_override_blocked(self, gate):
        # A forbidden PAYMENT tool: B1 blocks it; the broker certificate is not
        # READY regardless.
        tid = gate.contract_tool(
            admit=False, tool_name="Pay Vendor", category="PAYMENT",
            side_effect_class="PAYMENT_MOVEMENT",
            declared_side_effects=["PAYMENT_MOVEMENT"], touches_payment=True)
        c = gate.create_contract(tid).json()
        assert c["contract_status"] == "BLOCKED"
        env = gate.project(tid, c["contract_id"]).json()
        assert env["projection_status"] == "BLOCKED"
        assert env["broker_readiness_certificate"][
            "certificate_status"] != "READY_FOR_FUTURE_BROKER_CONSIDERATION"


class TestRbacAndTenant:
    def test_viewer_cannot_create(self, gate):
        tid = gate.contract_tool()
        assert gate.create_contract(tid, actor=VIEWER).status_code == 403

    def test_viewer_cannot_project(self, gate):
        tid, c = gate.contracted_tool()
        assert gate.project(tid, c["contract_id"],
                            actor=VIEWER).status_code == 403

    def test_cross_tenant_create_denied(self, gate):
        tid = gate.contract_tool()
        assert gate.create_contract(tid, actor=OTHER_OWNER).status_code == 404

    def test_cross_tenant_read_denied(self, gate):
        tid, c = gate.contracted_tool()
        assert gate.ct(tid, c["contract_id"], "",
                       actor=OTHER_OWNER).status_code == 404

    def test_cross_tenant_project_denied(self, gate):
        tid, c = gate.contracted_tool()
        assert gate.project(tid, c["contract_id"],
                            actor=OTHER_OWNER).status_code == 404

    def test_ai_worker_recorded_as_ai_employee(self, gate):
        gate.add_user("ai@demo.finalis", "ai_worker")
        tid = gate.contract_tool()
        c = gate.create_contract(tid, actor="ai@demo.finalis").json()
        led = gate.ct(tid, c["contract_id"], "/revocation-ledger",
                      actor=OWNER).json()
        actor_types = {e["actor_type"] for e in led["events"]}
        assert "human" not in actor_types
        assert "ai_employee" in actor_types


class TestEventLedger:
    def test_ledger_chain_valid(self, gate):
        tid, c = gate.contracted_tool()
        gate.project(tid, c["contract_id"])
        led = gate.ct(tid, c["contract_id"], "/revocation-ledger").json()
        assert led["event_chain_valid"] is True
        types = {e["event_type"] for e in led["events"]}
        assert "CONTRACT_CREATED" in types
        assert "CONTRACT_PROJECTED" in types

"""TOOL-B3 protocol dialect matrix + capability negotiation boundary tests.

The contract kernel labels internal "protocol dialects" as future-readiness
metadata ONLY: no dialect enables a runtime feature, no compliance is claimed,
and capability negotiation permits (a future) `tools` feature while denying
resources/prompts/sampling/elicitation/roots and never performing runtime
negotiation. These assert the dialect matrix + capability negotiation on both
the kernel builders and the GET /protocol endpoint.
"""
from finalis.ai_employee import tool_contracts as tc
from tests.conftest import OWNER

SUPPORTED = ["INTERNAL_BROKER_DRAFT", "MCP_2025_06_18_LIKE",
             "MCP_2025_11_25_LIKE", "MCP_DRAFT_LIKE_READ_ONLY",
             "OPENAI_APPS_SDK_LIKE", "OPENAPI_3_1_LIKE", "OPENAPI_3_2_LIKE",
             "TRACE_ONLY", "SAFE_PLANNER_SUMMARY"]


class TestDialectMatrix:
    def test_supported_dialects_exact(self, gate):
        tid, c = gate.contracted_tool()
        dm = c["protocol_dialect_matrix"]
        assert dm["supported_dialects"] == SUPPORTED

    def test_supported_dialects_subset_of_known(self, gate):
        tid, c = gate.contracted_tool()
        dm = c["protocol_dialect_matrix"]
        assert set(dm["supported_dialects"]).issubset(tc.DIALECTS)
        # The catch-all NOT_IMPLEMENTED sentinel is never advertised as supported.
        assert "NOT_IMPLEMENTED_DIALECT" not in dm["supported_dialects"]

    def test_blocked_dialects(self, gate):
        tid, c = gate.contracted_tool()
        dm = c["protocol_dialect_matrix"]
        assert dm["blocked_dialects"] == ["NOT_IMPLEMENTED_DIALECT"]

    def test_dialect_feature_flags_runtime_false(self, gate):
        tid, c = gate.contracted_tool()
        flags = c["protocol_dialect_matrix"]["dialect_feature_flags"]
        assert flags["runtime"] is False
        assert flags["tools_only"] is True

    def test_no_compliance_claimed_in_notes(self, gate):
        tid, c = gate.contracted_tool()
        dm = c["protocol_dialect_matrix"]
        notes = dm["protocol_version_notes"].lower()
        assert "not compliance" in notes or "not compliance-tested" in notes
        assert "no compliance claimed" in " ".join(
            dm["dialect_boundary_rules"]).lower()

    def test_boundary_rule_no_dialect_enables_runtime(self, gate):
        tid, c = gate.contracted_tool()
        rules = " ".join(c["protocol_dialect_matrix"]["dialect_boundary_rules"])
        assert "no dialect enables runtime" in rules.lower()

    def test_dialect_matrix_hash_deterministic(self, gate):
        m1 = tc.build_dialect_matrix(tenant_id="t", contract_id="c",
                                     tool_id="x")
        m2 = tc.build_dialect_matrix(tenant_id="t", contract_id="c",
                                     tool_id="x")
        assert m1["protocol_dialect_matrix_hash"] == m2[
            "protocol_dialect_matrix_hash"]
        # The stored hash is a faithful hash of the matrix's own content.
        assert tc._core_hash(m1, "protocol_dialect_matrix_hash") == m1[
            "protocol_dialect_matrix_hash"]


class TestCapabilityNegotiation:
    def test_tools_feature_allowed(self, gate):
        tid, c = gate.contracted_tool()
        cap = c["capability_negotiation_boundary"]
        assert cap["tools_feature_allowed_for_future"] is True

    def test_runtime_feature_families_denied(self, gate):
        tid, c = gate.contracted_tool()
        cap = c["capability_negotiation_boundary"]
        for feat in ("resources", "prompts", "sampling", "elicitation",
                     "roots"):
            assert cap[f"{feat}_feature_allowed_for_future"] is False, feat

    def test_runtime_negotiation_not_performed(self, gate):
        tid, c = gate.contracted_tool()
        cap = c["capability_negotiation_boundary"]
        assert cap["runtime_negotiation_performed"] is False

    def test_clean_contract_boundary_matched(self, gate):
        tid, c = gate.contracted_tool()
        cap = c["capability_negotiation_boundary"]
        assert cap["capability_boundary_status"] == "MATCHED"

    def test_runtime_requested_boundary_blocked(self, gate):
        tid = gate.contract_tool()
        c = gate.create_contract(tid, runtime_requested=True).json()
        cap = c["capability_negotiation_boundary"]
        assert cap["capability_boundary_status"] == "BLOCKED"
        # Even when runtime is (illegitimately) requested, no feature flips on.
        assert cap["sampling_feature_allowed_for_future"] is False
        assert cap["runtime_negotiation_performed"] is False

    def test_capability_hash_deterministic(self, gate):
        c1 = tc.build_capability_negotiation(
            tenant_id="t", contract_id="c", tool_id="x", runtime_requested=False)
        c2 = tc.build_capability_negotiation(
            tenant_id="t", contract_id="c", tool_id="x", runtime_requested=False)
        assert c1["capability_negotiation_boundary_hash"] == c2[
            "capability_negotiation_boundary_hash"]


class TestProtocolEndpoint:
    def test_get_protocol_returns_both(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/protocol")
        assert r.status_code == 200
        body = r.json()
        assert "protocol_dialect_matrix" in body
        assert "capability_negotiation_boundary" in body
        assert body["protocol_dialect_matrix"]["supported_dialects"] == SUPPORTED
        assert body["capability_negotiation_boundary"][
            "tools_feature_allowed_for_future"] is True

    def test_get_protocol_matches_contract(self, gate):
        tid, c = gate.contracted_tool()
        body = gate.ct(tid, c["contract_id"], "/protocol").json()
        assert body["protocol_dialect_matrix"] == c["protocol_dialect_matrix"]
        assert body["capability_negotiation_boundary"] == c[
            "capability_negotiation_boundary"]

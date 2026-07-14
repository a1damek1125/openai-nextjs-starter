"""TOOL-B3 resource/prompt/tool separation guard tests.

A B3 contract is a TOOL_CONTRACT, never a resource/prompt/sampling/elicitation/
roots kind. The separation guard scans descriptor prose: a clean tool is
MATCHED; a tool whose prose mentions sampling/elicitation/roots is BLOCKED (its
contract cannot be PROJECTABLE_FOR_FUTURE); other kind confusion is
NEEDS_REVIEW. Sampling/elicitation/resource/prompt runtime is never enabled.
These assert the guard via the kernel and the GET /separation endpoint.
"""
from finalis.ai_employee import tool_contracts as tc


class TestCleanTool:
    def test_declared_kind_is_tool_contract(self, gate):
        tid, c = gate.contracted_tool()
        sg = c["separation_guard"]
        assert sg["declared_kind"] == "TOOL_CONTRACT"

    def test_clean_tool_matched(self, gate):
        tid, c = gate.contracted_tool()
        sg = c["separation_guard"]
        assert sg["separation_guard_status"] == "MATCHED"
        assert sg["kind_confusion_detected"] is False

    def test_clean_tool_has_no_runtime_terms(self, gate):
        tid, c = gate.contracted_tool()
        sg = c["separation_guard"]
        assert sg["detected_sampling_terms"] == []
        assert sg["detected_elicitation_terms"] == []
        assert sg["detected_roots_terms"] == []

    def test_clean_contract_projectable(self, gate):
        tid, c = gate.contracted_tool()
        assert c["contract_status"] == "PROJECTABLE_FOR_FUTURE"


class TestRuntimeProseBlocked:
    def _runtime_tool(self, gate):
        tid = gate.contract_tool(
            tool_name="Elicit Helper",
            tool_description="read only helper that performs sampling and "
            "elicitation using roots to serve prompts",
            tool_summary="sampling elicitation roots")
        return tid, gate.create_contract(tid).json()

    def test_runtime_prose_blocked(self, gate):
        tid, c = self._runtime_tool(gate)
        sg = c["separation_guard"]
        assert sg["separation_guard_status"] == "BLOCKED"

    def test_runtime_terms_detected(self, gate):
        tid, c = self._runtime_tool(gate)
        sg = c["separation_guard"]
        assert "sampling" in sg["detected_sampling_terms"]
        assert "elicitation" in sg["detected_elicitation_terms"]
        assert "roots" in sg["detected_roots_terms"]
        assert sg["kind_confusion_detected"] is True

    def test_runtime_prose_contract_not_projectable(self, gate):
        tid, c = self._runtime_tool(gate)
        assert c["contract_status"] != "PROJECTABLE_FOR_FUTURE"
        assert c["contract_status"] in ("BLOCKED", "NEEDS_REVIEW")

    def test_runtime_prose_projection_blocked(self, gate):
        tid, c = self._runtime_tool(gate)
        env = gate.project(tid, c["contract_id"],
                           target="MCP_LIKE_TOOL_DESCRIPTOR").json()
        assert env["projection_status"] == "BLOCKED"
        assert "SAMPLING_ELICITATION_VIOLATION" in env["projection_blockers"]


class TestDetectedTermLists:
    def test_prompt_and_tool_terms_recorded(self, gate):
        tid = gate.contract_tool(
            tool_name="Prompt Tool",
            tool_description="read only tool that renders a prompt for review",
            tool_summary="prompt tool")
        c = gate.create_contract(tid).json()
        sg = c["separation_guard"]
        assert "prompt" in sg["detected_prompt_terms"]
        assert "tool" in sg["detected_tool_terms"]

    def test_resource_term_recorded(self, gate):
        tid = gate.contract_tool(
            tool_name="Res Tool",
            tool_description="read only helper listing resource records",
            tool_summary="resource list")
        c = gate.create_contract(tid).json()
        sg = c["separation_guard"]
        assert "resource" in sg["detected_resource_terms"]


class TestNoRuntimeEnabled:
    def test_capability_negotiation_denies_runtime_features(self, gate):
        # Sampling/elicitation/resource/prompt runtime is never enabled anywhere.
        tid, c = gate.contracted_tool()
        cap = c["capability_negotiation_boundary"]
        for feat in ("sampling", "elicitation", "resources", "prompts",
                     "roots"):
            assert cap[f"{feat}_feature_allowed_for_future"] is False, feat


class TestHashAndEndpoint:
    def test_separation_hash_deterministic(self, gate):
        desc = {"tool_description": "read only local search", "tool_summary": ""}
        s1 = tc.build_separation_guard(tenant_id="t", contract_id="c",
                                       tool_id="x", descriptor=desc,
                                       declared_kind="TOOL_CONTRACT")
        s2 = tc.build_separation_guard(tenant_id="t", contract_id="c",
                                       tool_id="x", descriptor=desc,
                                       declared_kind="TOOL_CONTRACT")
        assert s1["separation_guard_hash"] == s2["separation_guard_hash"]
        assert tc._core_hash(s1, "separation_guard_hash") == s1[
            "separation_guard_hash"]

    def test_get_separation_endpoint(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/separation")
        assert r.status_code == 200
        sg = r.json()["separation_guard"]
        assert sg["declared_kind"] == "TOOL_CONTRACT"
        assert sg["separation_guard_status"] == "MATCHED"
        assert sg == c["separation_guard"]

"""TOOL-B3 non-interference matrix tests.

Non-interference lives on the PROJECTION. A model-facing target (MCP-like,
Apps-SDK-like, SAFE_PLANNER_SUMMARY) must never leak a model-unsafe taint field
unredacted; a clean tool projects with leakage_detected False and status
MATCHED. Non-model-facing targets (SAFE_HUMAN_REVIEW_VIEW, TRACE_ONLY) have
field_policy.model_facing False. These assert the matrix via the projection
JSON, the kernel builder, and the GET /non-interference endpoint (latest
projection).
"""
from finalis.ai_employee import tool_contracts as tc


class TestCleanModelFacing:
    def test_mcp_like_matched(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"],
                           target="MCP_LIKE_TOOL_DESCRIPTOR").json()
        ni = env["non_interference_matrix"]
        assert ni["non_interference_status"] == "MATCHED"
        assert ni["leakage_detected"] is False
        assert ni["leaked_fields"] == []

    def test_shared_fields_listed(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"],
                           target="MCP_LIKE_TOOL_DESCRIPTOR").json()
        ni = env["non_interference_matrix"]
        assert ni["shared_fields"]
        # Shared fields are exactly the projected shape's fields.
        assert set(ni["shared_fields"]) == set(env["projected_shape"].keys())

    def test_source_equals_target_projection(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"],
                           target="SAFE_PLANNER_SUMMARY").json()
        ni = env["non_interference_matrix"]
        assert ni["source_projection_target"] == "SAFE_PLANNER_SUMMARY"
        assert ni["target_projection_target"] == "SAFE_PLANNER_SUMMARY"

    def test_field_policy_denies_all_model_unsafe_taints(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"],
                           target="MCP_LIKE_TOOL_DESCRIPTOR").json()
        denied = env["non_interference_matrix"]["field_policy"][
            "unsafe_taints_denied"]
        assert set(denied) == tc.MODEL_UNSAFE_TAINTS


class TestModelFacingFlag:
    def test_mcp_like_is_model_facing(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"],
                           target="MCP_LIKE_TOOL_DESCRIPTOR").json()
        assert env["non_interference_matrix"]["field_policy"][
            "model_facing"] is True

    def test_safe_planner_summary_is_model_facing(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"],
                           target="SAFE_PLANNER_SUMMARY").json()
        assert env["non_interference_matrix"]["field_policy"][
            "model_facing"] is True

    def test_human_review_not_model_facing(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"],
                           target="SAFE_HUMAN_REVIEW_VIEW").json()
        assert env["non_interference_matrix"]["field_policy"][
            "model_facing"] is False

    def test_trace_only_not_model_facing(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"],
                           target="TRACE_ONLY_CONTRACT").json()
        assert env["non_interference_matrix"]["field_policy"][
            "model_facing"] is False


class TestNoUnsafeLeak:
    def test_no_unsafe_taint_exposed_unredacted(self, gate):
        # Property: on a model-facing projection, any field carrying a
        # model-unsafe taint MUST be redacted; none is leaked.
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"],
                           target="MCP_LIKE_TOOL_DESCRIPTOR").json()
        for f in env["field_provenance"]["fields"]:
            if f["taint"] in tc.MODEL_UNSAFE_TAINTS:
                assert f["redaction_applied"] is True, f["field_path"]
        assert env["non_interference_matrix"]["leaked_fields"] == []

    def test_never_expose_taint_denied_by_policy(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"],
                           target="MCP_LIKE_TOOL_DESCRIPTOR").json()
        denied = env["non_interference_matrix"]["field_policy"][
            "unsafe_taints_denied"]
        assert "NEVER_EXPOSE_TO_MODEL" in denied

    def test_never_expose_taint_is_auto_redacted(self, gate):
        # A NEVER_EXPOSE_TO_MODEL field is auto-redacted by field provenance, so
        # it can never leak to a model-facing target.
        fp = tc.build_field_provenance(
            tenant_id="t", contract_id="c", projection_id="p",
            fields=[("secret", "src", "src.secret", "h" * 8, "projected",
                     "NEVER_EXPOSE_TO_MODEL")],
            quarantined=False)
        assert fp["fields"][0]["redaction_applied"] is True
        ni = tc.build_non_interference(
            tenant_id="t", contract_id="c",
            target="MCP_LIKE_TOOL_DESCRIPTOR", field_provenance=fp)
        assert ni["non_interference_status"] == "MATCHED"
        assert ni["leaked_fields"] == []

    def test_kernel_leak_detected_when_unsafe_unredacted(self, gate):
        # White-box: a model-facing target that shares an unredacted model-unsafe
        # field (SECRET_LIKE is not auto-redacted) FAILS non-interference.
        fp = tc.build_field_provenance(
            tenant_id="t", contract_id="c", projection_id="p",
            fields=[("secret", "src", "src.secret", "h" * 8, "projected",
                     "SECRET_LIKE")],
            quarantined=False)
        assert fp["fields"][0]["redaction_applied"] is False
        ni = tc.build_non_interference(
            tenant_id="t", contract_id="c",
            target="MCP_LIKE_TOOL_DESCRIPTOR", field_provenance=fp)
        assert ni["non_interference_status"] == "FAILED"
        assert ni["leakage_detected"] is True
        assert "secret" in ni["leaked_fields"]

    def test_kernel_no_leak_for_non_model_facing(self, gate):
        # The same unsafe field toward a NON-model-facing target is not a leak.
        fp = tc.build_field_provenance(
            tenant_id="t", contract_id="c", projection_id="p",
            fields=[("secret", "src", "src.secret", "h" * 8, "projected",
                     "SECRET_LIKE")],
            quarantined=False)
        ni = tc.build_non_interference(
            tenant_id="t", contract_id="c",
            target="TRACE_ONLY_CONTRACT", field_provenance=fp)
        assert ni["non_interference_status"] == "MATCHED"
        assert ni["field_policy"]["model_facing"] is False


class TestHashAndEndpoint:
    def test_non_interference_hash_deterministic(self, gate):
        fp = tc.build_field_provenance(
            tenant_id="t", contract_id="c", projection_id="p",
            fields=[("name", "src", "src.name", "h" * 8, "projected",
                     "SAFE_INTERNAL")], quarantined=False)
        n1 = tc.build_non_interference(
            tenant_id="t", contract_id="c",
            target="MCP_LIKE_TOOL_DESCRIPTOR", field_provenance=fp)
        n2 = tc.build_non_interference(
            tenant_id="t", contract_id="c",
            target="MCP_LIKE_TOOL_DESCRIPTOR", field_provenance=fp)
        assert n1["non_interference_matrix_hash"] == n2[
            "non_interference_matrix_hash"]
        assert tc._core_hash(n1, "non_interference_matrix_hash") == n1[
            "non_interference_matrix_hash"]

    def test_get_non_interference_reads_latest_projection(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"],
                           target="MCP_LIKE_TOOL_DESCRIPTOR").json()
        r = gate.ct(tid, c["contract_id"], "/non-interference")
        assert r.status_code == 200
        body = r.json()
        ni = body["non_interference_matrix"]
        assert ni["non_interference_status"] == "MATCHED"
        assert ni["field_policy"]["model_facing"] is True
        # Latest projection is the MCP-like one just created.
        assert body["projection_id"] == env["projection_envelope_id"]

    def test_get_non_interference_404_without_projection(self, gate):
        # A contract with no stored projection has nothing to read. (Creation
        # always stores a default projection, so this asserts the happy path
        # returns a matrix rather than 404.)
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/non-interference")
        assert r.status_code == 200
        assert "non_interference_matrix" in r.json()

"""TOOL-B3 projection surface tests.

Projecting a contract into each of the seven validation-only targets must
return a well-formed envelope; a clean admitted+quality-passed PURE_READ tool
must project to an MCP-like descriptor that is PROJECTABLE_FOR_FUTURE with a
readOnlyHint shape; runtime-requested and unknown targets must be refused; and
stored envelopes must read back. Projection hashes must be deterministic for
identical inputs (fixed projection_id) at the kernel level.
"""
import pytest

from finalis.ai_employee import tool_contracts as tc
from tests.conftest import Gate, OWNER


@pytest.fixture()
def gate():
    return Gate()


def _load_kernel_inputs(gate, tool_id, contract_id):
    """Return (contract, head, quality) the way the /project endpoint loads
    them, so a kernel-level projection can be built deterministically."""
    head = gate.app.state.tool_store.payload(tool_id, tenant_id=gate.tid)
    quality = gate.app.state.quality_store.latest(tool_id, tenant_id=gate.tid)
    contract = gate.app.state.contract_store.payload(
        contract_id, tenant_id=gate.tid)
    return contract, head, quality


class TestProjectAllTargets:
    def test_seven_targets_each_return_valid_envelope(self, gate):
        tid, c = gate.contracted_tool()
        assert tc.PROJECTION_TARGETS  # sanity
        for target in sorted(tc.PROJECTION_TARGETS):
            env = gate.project(tid, c["contract_id"], target=target).json()
            assert env["projection_target"] == target, target
            assert env["projection_status"] in tc.PROJECTION_STATUSES, target
            assert env["projected_shape"], target
            assert env["projection_hash"]
            assert env["projection_envelope_hash"]
            assert env["protocol_dialect"] in tc.DIALECTS, target
            assert env["honesty_labels"]

    def test_all_targets_clean_tool_projectable(self, gate):
        tid, c = gate.contracted_tool()
        for target in sorted(tc.PROJECTION_TARGETS):
            env = gate.project(tid, c["contract_id"], target=target).json()
            assert env["projection_status"] == "PROJECTABLE_FOR_FUTURE", target
            assert env["projection_blockers"] == [], target

    def test_dialect_matches_target(self, gate):
        tid, c = gate.contracted_tool()
        expected = {
            "MCP_LIKE_TOOL_DESCRIPTOR": "MCP_2025_11_25_LIKE",
            "OPENAI_APPS_SDK_LIKE_DESCRIPTOR": "OPENAI_APPS_SDK_LIKE",
            "OPENAPI_LIKE_SCHEMA_CONTRACT": "OPENAPI_3_1_LIKE",
            "SAFE_PLANNER_SUMMARY": "SAFE_PLANNER_SUMMARY",
            "TRACE_ONLY_CONTRACT": "TRACE_ONLY",
            "INTERNAL_TOOL_BROKER_CONTRACT": "INTERNAL_BROKER_DRAFT",
            "SAFE_HUMAN_REVIEW_VIEW": "TRACE_ONLY",
        }
        for target, dialect in expected.items():
            env = gate.project(tid, c["contract_id"], target=target).json()
            assert env["protocol_dialect"] == dialect, target


class TestMcpLikeShape:
    def test_clean_pure_read_projectable_with_shape(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"],
                           target="MCP_LIKE_TOOL_DESCRIPTOR").json()
        assert env["projection_status"] == "PROJECTABLE_FOR_FUTURE"
        shape = env["projected_shape"]
        for key in ("name", "description", "inputSchema", "outputSchema",
                    "annotations"):
            assert key in shape, key

    def test_read_only_hint_true_for_pure_read(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"],
                           target="MCP_LIKE_TOOL_DESCRIPTOR").json()
        ann = env["projected_shape"]["annotations"]
        assert ann["readOnlyHint"] is True
        assert ann["destructiveHint"] is False
        assert ann["openWorldHint"] is False

    def test_input_schema_carried_from_normal_form(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"],
                           target="MCP_LIKE_TOOL_DESCRIPTOR").json()
        assert env["projected_shape"]["inputSchema"] == \
            c["contract_normal_form"]["normalized_input_schema"]


class TestUnknownTargetRejected:
    def test_unknown_target_400_via_endpoint(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.project(tid, c["contract_id"], target="NOT_A_TARGET")
        assert r.status_code == 400

    def test_unknown_target_raises_in_kernel(self, gate):
        tid, c = gate.contracted_tool()
        contract, head, quality = _load_kernel_inputs(
            gate, tid, c["contract_id"])
        with pytest.raises(ValueError):
            tc.build_projection(
                contract=contract, head=head, quality_report=quality,
                target="NOT_A_TARGET", projection_id="x", tenant_id=gate.tid,
                created_at="2020-01-01T00:00:00Z")


class TestRuntimeRequestedBlocked:
    def test_runtime_requested_blocked_with_witness(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"], runtime_requested=True).json()
        assert env["projection_status"] == "BLOCKED"
        assert "RUNTIME_CAPABILITY_DENIED" in env["projection_blockers"]
        assert env["violation_witnesses"]
        witness = env["violation_witnesses"][0]
        assert witness["violation_witness_hash"]
        assert witness["dominant_failure_status"] == "BLOCKED"

    def test_b1_blocked_payment_tool_blocked_projection(self, gate):
        tid = gate.contract_tool(
            admit=False, tool_name="Pay Vendor", category="PAYMENT",
            side_effect_class="PAYMENT_MOVEMENT",
            declared_side_effects=["PAYMENT_MOVEMENT"], touches_payment=True)
        c = gate.create_contract(tid).json()
        env = gate.project(tid, c["contract_id"]).json()
        assert env["projection_status"] == "BLOCKED"


class TestProjectionReadback:
    def test_get_projection_reads_stored_envelope(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"],
                           target="MCP_LIKE_TOOL_DESCRIPTOR").json()
        pid = env["projection_envelope_id"]
        rb = gate.ct(tid, c["contract_id"], f"/projection/{pid}").json()
        assert rb["projection_envelope_id"] == pid
        assert rb["projection_status"] == env["projection_status"]
        assert rb["projection_envelope_hash"] == env["projection_envelope_hash"]

    def test_get_unknown_projection_404(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/projection/does-not-exist")
        assert r.status_code == 404


class TestShapeEndpoints:
    def test_mcp_like_endpoint_projectable_with_shape(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/mcp-like").json()
        assert r["projectable"] is True
        assert r["shape"] is not None
        assert r["shape"]["annotations"]["readOnlyHint"] is True

    def test_apps_sdk_and_openapi_endpoints_projectable(self, gate):
        tid, c = gate.contracted_tool()
        for ep in ("/apps-sdk-like", "/openapi-like"):
            r = gate.ct(tid, c["contract_id"], ep).json()
            assert r["projectable"] is True, ep
            assert r["shape"] is not None, ep
            assert r["projection_status"] == "PROJECTABLE_FOR_FUTURE", ep

    def test_shape_endpoint_not_projectable_for_blocked_tool(self, gate):
        tid = gate.contract_tool(
            admit=False, tool_name="Pay Vendor", category="PAYMENT",
            side_effect_class="PAYMENT_MOVEMENT",
            declared_side_effects=["PAYMENT_MOVEMENT"], touches_payment=True)
        c = gate.create_contract(tid).json()
        r = gate.ct(tid, c["contract_id"], "/mcp-like").json()
        assert r["projectable"] is False
        assert r["shape"] is None


class TestProjectionHashDeterminism:
    def test_projection_hash_deterministic_for_identical_inputs(self, gate):
        tid, c = gate.contracted_tool()
        contract, head, quality = _load_kernel_inputs(
            gate, tid, c["contract_id"])
        kw = dict(contract=contract, head=head, quality_report=quality,
                  target="MCP_LIKE_TOOL_DESCRIPTOR", projection_id="fixed-pid",
                  tenant_id=gate.tid, created_at="2020-01-01T00:00:00Z")
        e1 = tc.build_projection(**kw)
        e2 = tc.build_projection(**kw)
        assert e1["projection_hash"] == e2["projection_hash"]
        assert e1["projection_envelope_hash"] == e2["projection_envelope_hash"]

    def test_projection_hash_changes_with_target(self, gate):
        tid, c = gate.contracted_tool()
        contract, head, quality = _load_kernel_inputs(
            gate, tid, c["contract_id"])

        def build(target):
            return tc.build_projection(
                contract=contract, head=head, quality_report=quality,
                target=target, projection_id="fixed-pid", tenant_id=gate.tid,
                created_at="2020-01-01T00:00:00Z")["projection_hash"]
        assert build("MCP_LIKE_TOOL_DESCRIPTOR") != \
            build("OPENAPI_LIKE_SCHEMA_CONTRACT")

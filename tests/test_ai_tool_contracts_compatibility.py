"""TOOL-B3 compatibility report (GET /compatibility, build_compatibility_report).

The report scores each protocol-like target (0/2/5), never claims runtime
protocol compliance, and — crucially — the compatibility SCORE can never
override a projection blocker: a fully-blocked tool is BLOCKED, not compatible.
"""
import pytest

from finalis.ai_employee import tool_contracts as tc
from tests.conftest import OWNER


def report(gate, tid, cid):
    return gate.ct(tid, cid, "/compatibility").json()["compatibility_report"]


class TestCompatibilityClean:
    def test_clean_tool_compatible_internal_only(self, gate):
        tid, c = gate.contracted_tool()
        rep = report(gate, tid, c["contract_id"])
        assert rep["compatibility_status"] == "COMPATIBLE_INTERNAL_ONLY"
        assert rep["compatibility_blockers"] == []

    def test_per_target_scores_are_full(self, gate):
        tid, c = gate.contracted_tool()
        rep = report(gate, tid, c["contract_id"])
        vec = rep["compatibility_score_vector"]
        for tgt in ("MCP_LIKE_TOOL_DESCRIPTOR",
                    "OPENAI_APPS_SDK_LIKE_DESCRIPTOR",
                    "OPENAPI_LIKE_SCHEMA_CONTRACT",
                    "INTERNAL_TOOL_BROKER_CONTRACT"):
            assert vec[tgt] == 5

    def test_per_target_status_fields(self, gate):
        tid, c = gate.contracted_tool()
        rep = report(gate, tid, c["contract_id"])
        assert rep["mcp_like_compatibility"] == "PROJECTABLE_FOR_FUTURE"
        assert rep["apps_sdk_like_compatibility"] == "PROJECTABLE_FOR_FUTURE"
        assert rep["openapi_like_compatibility"] == "PROJECTABLE_FOR_FUTURE"

    def test_protocol_version_notes_claim_no_compliance(self, gate):
        tid, c = gate.contracted_tool()
        rep = report(gate, tid, c["contract_id"])
        assert "no compliance" in rep["protocol_version_notes"].lower()

    def test_report_hash_matches_recompute(self, gate):
        tid, c = gate.contracted_tool()
        rep = report(gate, tid, c["contract_id"])
        assert rep["compatibility_report_hash"] == tc._core_hash(
            rep, "compatibility_report_hash")


class TestCompatibilityBlocked:
    def _payment(self, gate):
        tid = gate.contract_tool(
            admit=False, tool_name="Pay Vendor", category="PAYMENT",
            side_effect_class="PAYMENT_MOVEMENT",
            declared_side_effects=["PAYMENT_MOVEMENT"], touches_payment=True)
        c = gate.create_contract(tid).json()
        return tid, c

    def test_blocked_tool_status_is_blocked(self, gate):
        tid, c = self._payment(gate)
        rep = report(gate, tid, c["contract_id"])
        assert rep["compatibility_status"] == "BLOCKED"

    def test_blocked_tool_scores_zero(self, gate):
        tid, c = self._payment(gate)
        rep = report(gate, tid, c["contract_id"])
        assert all(v == 0 for v in
                   rep["compatibility_score_vector"].values())

    def test_blocked_tool_lists_blockers(self, gate):
        tid, c = self._payment(gate)
        rep = report(gate, tid, c["contract_id"])
        assert "TOOL_B1_BLOCKED" in rep["compatibility_blockers"]

    def test_score_cannot_override_blockers(self, gate):
        # A forbidden PAYMENT tool: every score is 0 and the status is BLOCKED —
        # the score vector can never lift a blocked tool to COMPATIBLE.
        tid, c = self._payment(gate)
        rep = report(gate, tid, c["contract_id"])
        assert rep["compatibility_status"] != "COMPATIBLE_INTERNAL_ONLY"
        assert rep["compatibility_blockers"]


class TestCompatibilityReportBuilder:
    def _env(self, status, blockers=None):
        return {"projection_status": status,
                "projection_blockers": blockers or []}

    def test_needs_review_scores_two(self):
        rep = tc.build_compatibility_report(
            tenant_id="t", contract_id="c", tool_id="x", tool_version_id="v",
            projections=[("MCP_LIKE_TOOL_DESCRIPTOR",
                          self._env("NEEDS_REVIEW"))])
        assert rep["compatibility_score_vector"][
            "MCP_LIKE_TOOL_DESCRIPTOR"] == 2
        assert rep["compatibility_status"] == "NEEDS_REVIEW"

    def test_all_blocked_report_is_blocked(self):
        rep = tc.build_compatibility_report(
            tenant_id="t", contract_id="c", tool_id="x", tool_version_id="v",
            projections=[("MCP_LIKE_TOOL_DESCRIPTOR",
                          self._env("BLOCKED", ["TOOL_B1_BLOCKED"])),
                         ("OPENAPI_LIKE_SCHEMA_CONTRACT",
                          self._env("BLOCKED", ["TOOL_B2_BLOCKED"]))])
        assert rep["compatibility_status"] == "BLOCKED"
        assert set(rep["compatibility_blockers"]) == {
            "TOOL_B1_BLOCKED", "TOOL_B2_BLOCKED"}

    def test_projectable_scores_five(self):
        rep = tc.build_compatibility_report(
            tenant_id="t", contract_id="c", tool_id="x", tool_version_id="v",
            projections=[("MCP_LIKE_TOOL_DESCRIPTOR",
                          self._env("PROJECTABLE_FOR_FUTURE"))])
        assert rep["compatibility_score_vector"][
            "MCP_LIKE_TOOL_DESCRIPTOR"] == 5
        assert rep["compatibility_status"] == "COMPATIBLE_INTERNAL_ONLY"

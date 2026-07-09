"""TOOL-B3 data / effect / prompt-context boundary tests.

The three contract boundaries must hold: the data boundary forbids secret,
cross-tenant and export egress; the effect boundary detects a read-only-mislabel
on a write tool and clears an honest read tool, and always requires a future
broker; the prompt-context boundary reflects the TOOL-B2 selection status
(MINIMAL for a clean tool). All three carry a hash and GET /boundaries surfaces
them.
"""
import pytest

from finalis.ai_employee import tool_contracts as tc
from tests.conftest import Gate, OWNER


@pytest.fixture()
def gate():
    return Gate()


def _mislabeled_write_contract(gate):
    tid = gate.contract_tool(
        admit=False, category="INTERNAL_WRITE",
        side_effect_class="INTERNAL_WRITE",
        declared_side_effects=["INTERNAL_WRITE"],
        tool_description="read only tool that writes and updates local records",
        writes_data_classes=["INTERNAL"])
    return tid, gate.create_contract(tid).json()


class TestDataBoundary:
    def test_secret_cross_tenant_export_all_false(self, gate):
        tid, c = gate.contracted_tool()
        db = c["contract_data_boundary"]
        assert db["secret_data_allowed"] is False
        assert db["cross_tenant_data_allowed"] is False
        assert db["data_export_allowed"] is False

    def test_forbidden_data_scopes_equal_egress_forbidden(self, gate):
        tid, c = gate.contracted_tool()
        db = c["contract_data_boundary"]
        assert set(db["forbidden_data_scopes"]) == \
            set(tc._tr.EGRESS_FORBIDDEN_DATA)

    def test_input_classes_reflect_reads(self, gate):
        tid, c = gate.contracted_tool()
        assert c["contract_data_boundary"]["input_data_classes"] == ["INTERNAL"]

    def test_data_boundary_hash_deterministic(self, gate):
        df = {"reads_data_classes": ["INTERNAL"], "writes_data_classes": []}
        a = tc.build_data_boundary(tenant_id="t1", tool_id="tool1",
                                   contract_id="c1", data_flow=df)
        b = tc.build_data_boundary(tenant_id="t1", tool_id="tool1",
                                   contract_id="c1", data_flow=df)
        assert a["data_boundary_hash"] == b["data_boundary_hash"]


class TestEffectBoundaryMislabel:
    def test_honest_read_tool_not_mislabeled(self, gate):
        tid, c = gate.contracted_tool()
        eb = c["contract_effect_boundary"]
        assert eb["read_only_mislabel_detected"] is False
        assert eb["side_effect_class"] == "PURE_READ"

    def test_mislabeled_write_tool_detected(self, gate):
        tid, c = _mislabeled_write_contract(gate)
        eb = c["contract_effect_boundary"]
        assert eb["read_only_mislabel_detected"] is True
        assert eb["read_only_claimed"] is True
        assert eb["writes_local_state"] is True

    def test_mislabel_blocks_contract(self, gate):
        tid, c = _mislabeled_write_contract(gate)
        assert c["contract_status"] == "BLOCKED"
        assert "READONLY_MISLABEL" in c["contract_blockers"]

    def test_future_tool_broker_required(self, gate):
        tid, c = gate.contracted_tool()
        assert c["contract_effect_boundary"][
            "future_tool_broker_required"] is True

    def test_effect_boundary_hash_deterministic(self, gate):
        ec = {"side_effect_class": "PURE_READ"}
        desc = {"tool_description": "read only search"}
        a = tc.build_effect_boundary(tenant_id="t1", tool_id="tool1",
                                     contract_id="c1", effect_contract=ec,
                                     descriptor=desc)
        b = tc.build_effect_boundary(tenant_id="t1", tool_id="tool1",
                                     contract_id="c1", effect_contract=ec,
                                     descriptor=desc)
        assert a["effect_boundary_hash"] == b["effect_boundary_hash"]


class TestPromptContextBoundary:
    def test_clean_tool_exposure_minimal(self, gate):
        tid, c = gate.contracted_tool()
        pcb = c["contract_prompt_context_boundary"]
        assert pcb["prompt_context_exposure_status"] == "MINIMAL"
        assert pcb["safe_planner_summary"] is True

    def test_never_expose_fields_present_key(self, gate):
        tid, c = gate.contracted_tool()
        pcb = c["contract_prompt_context_boundary"]
        assert "never_expose_fields" in pcb
        assert "allowed_fields_for_future_model" in pcb


class TestAllHashesPresent:
    def test_three_boundary_hashes_present(self, gate):
        tid, c = gate.contracted_tool()
        assert c["contract_data_boundary"]["data_boundary_hash"]
        assert c["contract_effect_boundary"]["effect_boundary_hash"]
        assert c["contract_prompt_context_boundary"][
            "prompt_context_boundary_hash"]


class TestBoundariesEndpoint:
    def test_get_boundaries_returns_three_boundaries(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/boundaries")
        assert r.status_code == 200
        body = r.json()
        assert body["data_boundary"]["secret_data_allowed"] is False
        assert body["effect_boundary"]["future_tool_broker_required"] is True
        assert body["prompt_context_boundary"][
            "prompt_context_exposure_status"] == "MINIMAL"

    def test_boundaries_endpoint_hashes_match_contract(self, gate):
        tid, c = gate.contracted_tool()
        body = gate.ct(tid, c["contract_id"], "/boundaries").json()
        assert body["data_boundary"]["data_boundary_hash"] == \
            c["contract_data_boundary"]["data_boundary_hash"]
        assert body["effect_boundary"]["effect_boundary_hash"] == \
            c["contract_effect_boundary"]["effect_boundary_hash"]

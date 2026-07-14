"""TOOL-B3 scope binding tests.

The contract scope binding must be MATCHED with projected == source (no
expansion), forbidden data scopes equal to the egress-forbidden set, a future
Tool Broker required, cross-tenant disallowed, and approval scope reflecting
risk. Its hash must be deterministic for identical inputs, and GET /scope must
surface it.
"""
import pytest

from finalis.ai_employee import tool_contracts as tc
from tests.conftest import Gate, OWNER


@pytest.fixture()
def gate():
    return Gate()


def _high_risk_contract(gate):
    """An EXTERNAL_WRITE tool classifies HIGH risk -> approval required."""
    tid = gate.contract_tool(
        admit=False, tool_name="Ext Writer", category="EXTERNAL_API_WRITE",
        side_effect_class="EXTERNAL_WRITE",
        declared_side_effects=["EXTERNAL_WRITE"])
    return tid, gate.create_contract(tid).json()


class TestScopeBindingPresent:
    def test_scope_binding_present_and_matched(self, gate):
        tid, c = gate.contracted_tool()
        sb = c["contract_scope_binding"]
        assert sb["scope_binding_status"] == "MATCHED"
        assert sb["scope_binding_version"] == tc.SCOPE_BINDING_VERSION

    def test_projected_equals_source(self, gate):
        tid, c = gate.contracted_tool()
        sb = c["contract_scope_binding"]
        assert sb["projected_scope_set"] == sb["source_scope_set"]
        assert sb["scope_expansion_detected"] is False

    def test_requires_future_tool_broker(self, gate):
        tid, c = gate.contracted_tool()
        assert c["contract_scope_binding"]["requires_future_tool_broker"] is True

    def test_cross_tenant_disallowed(self, gate):
        tid, c = gate.contracted_tool()
        assert c["contract_scope_binding"]["cross_tenant_allowed"] is False


class TestForbiddenDataScopes:
    def test_forbidden_scopes_equal_egress_forbidden(self, gate):
        tid, c = gate.contracted_tool()
        sb = c["contract_scope_binding"]
        assert set(sb["forbidden_data_scopes"]) == \
            set(tc._tr.EGRESS_FORBIDDEN_DATA)

    def test_required_data_scopes_reflect_reads(self, gate):
        tid, c = gate.contracted_tool()
        sb = c["contract_scope_binding"]
        assert sb["required_data_scopes"] == ["INTERNAL"]


class TestApprovalScopeReflectsRisk:
    def test_clean_low_risk_no_approval_scope(self, gate):
        tid, c = gate.contracted_tool()
        assert c["contract_risk_class"] == "TRIVIAL"
        assert c["contract_scope_binding"]["required_approval_scope"] is False

    def test_high_risk_requires_approval_scope(self, gate):
        tid, c = _high_risk_contract(gate)
        assert c["contract_risk_class"] == "HIGH"
        sb = c["contract_scope_binding"]
        assert sb["required_approval_scope"] is True
        assert sb["requires_human_review"] is True


class TestScopeBindingHashDeterministic:
    def test_hash_deterministic_for_identical_inputs(self, gate):
        head = {"category": "DATA_SEARCH", "side_effect_class": "PURE_READ",
                "risk_class": "HIGH"}
        data_flow = {"reads_data_classes": ["INTERNAL"],
                     "writes_data_classes": []}
        kw = dict(tenant_id="t1", tool_id="tool1", tool_version_id="v1",
                  contract_id="c1", head=head, data_flow=data_flow,
                  requires_approval=True, requires_consent=False)
        a = tc.build_scope_binding(**kw)
        b = tc.build_scope_binding(**kw)
        assert a["scope_binding_hash"] == b["scope_binding_hash"]

    def test_hash_changes_with_scope_inputs(self, gate):
        head = {"category": "DATA_SEARCH", "side_effect_class": "PURE_READ",
                "risk_class": "LOW"}
        base = dict(tenant_id="t1", tool_id="tool1", tool_version_id="v1",
                    contract_id="c1", head=head, requires_approval=False,
                    requires_consent=False)
        a = tc.build_scope_binding(
            data_flow={"reads_data_classes": ["INTERNAL"],
                       "writes_data_classes": []}, **base)
        b = tc.build_scope_binding(
            data_flow={"reads_data_classes": ["PII"],
                       "writes_data_classes": []}, **base)
        assert a["scope_binding_hash"] != b["scope_binding_hash"]


class TestScopeEndpoint:
    def test_get_scope_returns_binding(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/scope")
        assert r.status_code == 200
        body = r.json()
        sb = body["contract_scope_binding"]
        assert sb["scope_binding_status"] == "MATCHED"
        assert sb["scope_binding_hash"] == \
            c["contract_scope_binding"]["scope_binding_hash"]

    def test_scope_endpoint_hash_stable_across_reads(self, gate):
        tid, c = gate.contracted_tool()
        h1 = gate.ct(tid, c["contract_id"], "/scope").json()[
            "contract_scope_binding"]["scope_binding_hash"]
        h2 = gate.ct(tid, c["contract_id"], "/scope").json()[
            "contract_scope_binding"]["scope_binding_hash"]
        assert h1 == h2

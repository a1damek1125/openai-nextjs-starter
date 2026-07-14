"""TOOL-B3 auth context envelope tests.

The auth envelope prepares a FUTURE Tool Broker: it must never allow token
passthrough or ambient authority, must mark OAuth/MCP/Apps-SDK authorization as
NOT_IMPLEMENTED, must require caller/principal binding before any future
execution, must list confused-deputy prechecks, and must reflect approval
requirements by risk. Its hash must be deterministic and GET /auth must surface
it.
"""
import pytest

from finalis.ai_employee import tool_contracts as tc
from tests.conftest import Gate, OWNER


@pytest.fixture()
def gate():
    return Gate()


def _high_risk_contract(gate):
    tid = gate.contract_tool(
        admit=False, tool_name="Ext Writer", category="EXTERNAL_API_WRITE",
        side_effect_class="EXTERNAL_WRITE",
        declared_side_effects=["EXTERNAL_WRITE"])
    return tid, gate.create_contract(tid).json()


class TestNoTokenOrAmbientAuthority:
    def test_token_passthrough_always_false(self, gate):
        tid, c = gate.contracted_tool()
        assert c["auth_context_envelope"]["token_passthrough_allowed"] is False

    def test_ambient_authority_always_false(self, gate):
        tid, c = gate.contracted_tool()
        assert c["auth_context_envelope"]["ambient_authority_allowed"] is False

    def test_token_and_ambient_false_even_for_high_risk(self, gate):
        tid, c = _high_risk_contract(gate)
        env = c["auth_context_envelope"]
        assert env["token_passthrough_allowed"] is False
        assert env["ambient_authority_allowed"] is False


class TestAuthFutureSlotsNotImplemented:
    def test_oauth_mcp_appssdk_slots_not_implemented(self, gate):
        tid, c = gate.contracted_tool()
        env = c["auth_context_envelope"]
        assert env["oauth_required_future_slot"] == "NOT_IMPLEMENTED"
        assert env["mcp_authorization_future_slot"] == "NOT_IMPLEMENTED"
        assert env["apps_sdk_auth_future_slot"] == "NOT_IMPLEMENTED"


class TestBindingSlotsPresent:
    def test_caller_and_principal_binding_required_before_execution(self, gate):
        tid, c = gate.contracted_tool()
        env = c["auth_context_envelope"]
        assert env["caller_binding_future_slot"] == \
            "REQUIRED_BEFORE_FUTURE_EXECUTION"
        assert env["principal_binding_future_slot"] == \
            "REQUIRED_BEFORE_FUTURE_EXECUTION"

    def test_subject_audience_resource_binding_required(self, gate):
        tid, c = gate.contracted_tool()
        env = c["auth_context_envelope"]
        assert env["required_subject_binding"] is True
        assert env["required_audience_binding"] is True
        assert env["required_resource_binding"] is True


class TestConfusedDeputyPrechecks:
    def test_prechecks_non_empty(self, gate):
        tid, c = gate.contracted_tool()
        prechecks = c["auth_context_envelope"]["confused_deputy_prechecks"]
        assert isinstance(prechecks, list)
        assert prechecks

    def test_prechecks_cover_core_bindings(self, gate):
        tid, c = gate.contracted_tool()
        prechecks = c["auth_context_envelope"]["confused_deputy_prechecks"]
        for needle in ("bind caller", "bind subject", "bind audience",
                       "bind resource", "bind tenant", "bind scope"):
            assert needle in prechecks, needle


class TestApprovalGrantReflectsRisk:
    def test_clean_tool_no_approval_grant(self, gate):
        tid, c = gate.contracted_tool()
        assert c["auth_context_envelope"]["required_approval_grant"] is False

    def test_high_risk_requires_approval_grant(self, gate):
        tid, c = _high_risk_contract(gate)
        assert c["auth_context_envelope"]["required_approval_grant"] is True


class TestAuthHashDeterministic:
    def test_hash_deterministic_for_identical_inputs(self, gate):
        kw = dict(tenant_id="t1", tool_id="tool1", contract_id="c1", head={},
                  requires_approval=True, requires_consent=False)
        a = tc.build_auth_envelope(**kw)
        b = tc.build_auth_envelope(**kw)
        assert a["auth_context_envelope_hash"] == \
            b["auth_context_envelope_hash"]

    def test_hash_changes_with_approval_requirement(self, gate):
        base = dict(tenant_id="t1", tool_id="tool1", contract_id="c1", head={},
                    requires_consent=False)
        a = tc.build_auth_envelope(requires_approval=False, **base)
        b = tc.build_auth_envelope(requires_approval=True, **base)
        assert a["auth_context_envelope_hash"] != \
            b["auth_context_envelope_hash"]


class TestAuthEndpoint:
    def test_get_auth_returns_envelope(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/auth")
        assert r.status_code == 200
        env = r.json()["auth_context_envelope"]
        assert env["token_passthrough_allowed"] is False
        assert env["ambient_authority_allowed"] is False
        assert env["auth_context_envelope_hash"] == \
            c["auth_context_envelope"]["auth_context_envelope_hash"]

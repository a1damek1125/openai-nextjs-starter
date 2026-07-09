"""TOOL-B3 scope calculus tests.

The projected scope set of an honest contract must be a subset of its source
scope set (a projection can never expand scope). These exercise the
`tc.scope_is_subset` helper and the subset relationship on a real contract's
scope binding, plus cross-tenant and hand-built-superset negatives.
"""
import pytest

from finalis.ai_employee import tool_contracts as tc
from tests.conftest import Gate, OWNER


@pytest.fixture()
def gate():
    return Gate()


class TestScopeIsSubsetHelper:
    def test_subset_returns_true(self, gate):
        assert tc.scope_is_subset(["a", "b"], ["a", "b", "c"]) is True

    def test_equal_sets_are_subset(self, gate):
        assert tc.scope_is_subset(["a", "b"], ["b", "a"]) is True

    def test_empty_projected_is_subset(self, gate):
        assert tc.scope_is_subset([], ["a"]) is True

    def test_superset_returns_false(self, gate):
        assert tc.scope_is_subset(["a", "b", "c"], ["a", "b"]) is False

    def test_disjoint_element_returns_false(self, gate):
        assert tc.scope_is_subset(["z"], ["a", "b"]) is False


class TestRealContractSubset:
    def test_projected_scope_subset_of_source(self, gate):
        tid, c = gate.contracted_tool()
        sb = c["contract_scope_binding"]
        assert tc.scope_is_subset(sb["projected_scope_set"],
                                  sb["source_scope_set"]) is True

    def test_projected_equals_source_no_expansion(self, gate):
        tid, c = gate.contracted_tool()
        sb = c["contract_scope_binding"]
        assert set(sb["projected_scope_set"]) == set(sb["source_scope_set"])

    def test_scope_expansion_not_detected_for_honest_projection(self, gate):
        tid, c = gate.contracted_tool()
        sb = c["contract_scope_binding"]
        assert sb["scope_expansion_detected"] is False

    def test_source_scope_carries_tenant_and_category(self, gate):
        tid, c = gate.contracted_tool()
        sb = c["contract_scope_binding"]
        joined = " ".join(sb["source_scope_set"])
        assert f"tenant:{gate.tid}" in sb["source_scope_set"]
        assert "category:" in joined


class TestCrossTenantDisallowed:
    def test_cross_tenant_flag_false(self, gate):
        tid, c = gate.contracted_tool()
        assert c["contract_scope_binding"]["cross_tenant_allowed"] is False

    def test_source_scope_bound_to_single_tenant(self, gate):
        tid, c = gate.contracted_tool()
        sb = c["contract_scope_binding"]
        tenant_scopes = [s for s in sb["source_scope_set"]
                         if s.startswith("tenant:")]
        assert tenant_scopes == [f"tenant:{gate.tid}"]


class TestHandBuiltSupersetNotSubset:
    def test_expanded_projection_is_not_a_subset(self, gate):
        tid, c = gate.contracted_tool()
        sb = c["contract_scope_binding"]
        # An attacker-expanded projected set adds a scope not in source.
        forged = list(sb["source_scope_set"]) + ["tenant:other.finalis"]
        assert tc.scope_is_subset(forged, sb["source_scope_set"]) is False

    def test_adding_forbidden_data_scope_breaks_subset(self, gate):
        tid, c = gate.contracted_tool()
        sb = c["contract_scope_binding"]
        forged = list(sb["projected_scope_set"]) + ["SECRET"]
        # SECRET is egress-forbidden and absent from an INTERNAL-only source.
        assert "SECRET" not in sb["source_scope_set"]
        assert tc.scope_is_subset(forged, sb["source_scope_set"]) is False

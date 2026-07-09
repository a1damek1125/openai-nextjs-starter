"""TOOL-B3 effect-trace semantics tests.

The effect-trace records the DECLARED future effect boundary of a contract. B3
observes no runtime effects; it only declares them. The dangerous runtime
effects (payment / evidence / consent / admin / secret / external-provider /
data-export / tool-broker / LLM / MCP) are ALWAYS forbidden and never appear in
allowed_effects, regardless of the tool. A read-only tool's allowed effects are
read-only.
"""
import copy

from finalis.ai_employee import tool_contracts as tc
from tests.conftest import OWNER

# Dangerous effects the task calls out explicitly.
_DANGEROUS = [
    "PAYMENT_RELATED_EFFECT", "EVIDENCE_MUTATION", "LLM_CALL_EFFECT",
    "MCP_RUNTIME_EFFECT", "EXTERNAL_PROVIDER_EFFECT", "DATA_EXPORT_EFFECT",
    "TOOL_BROKER_CALL_EFFECT",
]
_READ_ONLY_EFFECTS = {"NO_EFFECT", "READ_LOCAL_STATE", "READ_CUSTOMER_DATA",
                      "READ_EVIDENCE_DATA", "READ_ARTIFACT_DATA"}


class TestEffectTracePresence:
    def test_present_and_matched_for_normal_tool(self, gate):
        _tid, c = gate.contracted_tool()
        et = c["effect_trace_semantics"]
        assert et is not None
        assert et["effect_trace_status"] == "MATCHED"

    def test_mediated_effect_boundary_declared(self, gate):
        _tid, c = gate.contracted_tool()
        assert "future Tool Broker" in \
            c["effect_trace_semantics"]["mediated_effect_boundary"]


class TestForbiddenEffects:
    def test_forbidden_effects_are_sorted_kernel_set(self, gate):
        _tid, c = gate.contracted_tool()
        et = c["effect_trace_semantics"]
        assert et["forbidden_effects"] == sorted(tc.FORBIDDEN_EFFECTS)

    def test_forbidden_effects_count_is_ten(self, gate):
        _tid, c = gate.contracted_tool()
        assert len(c["effect_trace_semantics"]["forbidden_effects"]) == 10

    def test_forbidden_includes_all_dangerous_effects(self, gate):
        _tid, c = gate.contracted_tool()
        forbidden = c["effect_trace_semantics"]["forbidden_effects"]
        for eff in _DANGEROUS:
            assert eff in forbidden, eff


class TestAllowedEffectsAreSafe:
    def test_pure_read_allowed_effects_are_read_only(self, gate):
        _tid, c = gate.contracted_tool()
        allowed = c["effect_trace_semantics"]["allowed_effects"]
        assert allowed  # a reading tool declares at least one read effect
        assert set(allowed).issubset(_READ_ONLY_EFFECTS)
        assert "WRITE_LOCAL_STATE" not in allowed

    def test_no_dangerous_effect_allowed_clean_tool(self, gate):
        _tid, c = gate.contracted_tool()
        allowed = set(c["effect_trace_semantics"]["allowed_effects"])
        assert not (allowed & tc.FORBIDDEN_EFFECTS)

    def test_no_dangerous_effect_allowed_sensitive_read(self, gate):
        _tid, c = gate.contracted_tool(reads_data_classes=["SENSITIVE_PII"])
        allowed = set(c["effect_trace_semantics"]["allowed_effects"])
        assert not (allowed & tc.FORBIDDEN_EFFECTS)

    def test_no_dangerous_effect_allowed_external_write(self, gate):
        _tid, c = gate.contracted_tool(
            side_effect_class="EXTERNAL_WRITE",
            declared_side_effects=["EXTERNAL_WRITE"])
        allowed = set(c["effect_trace_semantics"]["allowed_effects"])
        assert not (allowed & tc.FORBIDDEN_EFFECTS)

    def test_allowed_and_forbidden_are_disjoint(self, gate):
        _tid, c = gate.contracted_tool()
        et = c["effect_trace_semantics"]
        assert not (set(et["allowed_effects"]) & set(et["forbidden_effects"]))


class TestObservableAssumption:
    def test_observable_effect_assumption_states_no_runtime_observation(
            self, gate):
        _tid, c = gate.contracted_tool()
        assumption = c["effect_trace_semantics"]["observable_effect_assumption"]
        assert "NO runtime effects" in assumption


class TestEffectTraceHash:
    def test_hash_recomputes_and_self_excludes(self, gate):
        _tid, c = gate.contracted_tool()
        et = copy.deepcopy(c["effect_trace_semantics"])
        original = et["effect_trace_semantics_hash"]
        assert tc._core_hash(et, "effect_trace_semantics_hash") == original
        et["effect_trace_semantics_hash"] = "tampered"
        assert tc._core_hash(et, "effect_trace_semantics_hash") == original


class TestEffectTraceEndpoint:
    def test_get_effect_trace_endpoint(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/effect-trace", actor=OWNER)
        assert r.status_code == 200
        body = r.json()
        assert body["contract_id"] == c["contract_id"]
        et = body["effect_trace_semantics"]
        assert et["forbidden_effects"] == sorted(tc.FORBIDDEN_EFFECTS)
        assert body["honesty_labels"] == tc.HONESTY_LABELS

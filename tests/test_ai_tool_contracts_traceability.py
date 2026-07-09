"""TOOL-B3 contract TRACEABILITY envelope tests.

The traceability envelope binds a contract to every upstream source of truth
(descriptor / admission / quality / security case / negative-capability /
policy / risk / TBOM) plus the contract's own derived hashes (contract, ABI,
effect-trace, deny-graph) and the freshness/revocation epochs. Every source
hash of a real tool must be present, and the envelope hash is deterministic and
self-excluding.
"""
import copy

from finalis.ai_employee import tool_contracts as tc
from tests.conftest import OWNER

_SOURCE_HASHES = [
    "source_descriptor_hash", "source_admission_hash",
    "source_quality_report_hash", "source_security_case_hash",
    "source_negative_capability_hash", "source_policy_hash",
    "source_risk_hash", "source_tbom_hash",
]


class TestTraceabilityPresence:
    def test_envelope_present(self, gate):
        _tid, c = gate.contracted_tool()
        tr = c["contract_traceability_envelope"]
        assert tr is not None
        assert tr["traceability_envelope_hash"]

    def test_all_source_hashes_present(self, gate):
        _tid, c = gate.contracted_tool()
        tr = c["contract_traceability_envelope"]
        for k in _SOURCE_HASHES:
            assert tr.get(k) is not None, k

    def test_freshness_and_revocation_epochs_present(self, gate):
        _tid, c = gate.contracted_tool()
        tr = c["contract_traceability_envelope"]
        assert tr["source_freshness_epoch"] is not None
        assert tr["revocation_epoch"] is not None
        assert tr["source_freshness_epoch"] == c["source_freshness_epoch"]
        assert tr["revocation_epoch"] == c["revocation_epoch"]


class TestTraceabilityBindsDerivedHashes:
    def test_binds_contract_hash(self, gate):
        _tid, c = gate.contracted_tool()
        assert c["contract_traceability_envelope"]["contract_hash"] \
            == c["contract_hash"]

    def test_binds_abi_hash(self, gate):
        _tid, c = gate.contracted_tool()
        assert c["contract_traceability_envelope"]["contract_abi_hash"] \
            == c["contract_abi"]["abi_hash"]

    def test_binds_effect_trace_hash(self, gate):
        _tid, c = gate.contracted_tool()
        assert c["contract_traceability_envelope"][
            "effect_trace_semantics_hash"] \
            == c["effect_trace_semantics"]["effect_trace_semantics_hash"]

    def test_binds_normal_form_hash(self, gate):
        _tid, c = gate.contracted_tool()
        assert c["contract_traceability_envelope"][
            "contract_normal_form_hash"] \
            == c["contract_normal_form"]["contract_normal_form_hash"]

    def test_binds_deny_graph_hash(self, gate):
        _tid, c = gate.contracted_tool()
        assert c["contract_traceability_envelope"][
            "runtime_capability_deny_graph_hash"] \
            == c["runtime_capability_deny_graph"]["deny_graph_hash"]


class TestTraceabilityActor:
    def test_created_by_actor_type_recorded(self, gate):
        _tid, c = gate.contracted_tool()
        assert c["contract_traceability_envelope"]["created_by_actor_type"] \
            == "human"

    def test_created_by_actor_id_recorded(self, gate):
        _tid, c = gate.contracted_tool()
        assert c["contract_traceability_envelope"]["created_by_actor_id"] \
            == c["created_by_actor_id"]


class TestTraceabilityHash:
    def test_hash_recomputes_deterministically(self, gate):
        _tid, c = gate.contracted_tool()
        tr = c["contract_traceability_envelope"]
        assert tc._core_hash(tr, "traceability_envelope_hash") \
            == tr["traceability_envelope_hash"]

    def test_hash_is_self_excluding(self, gate):
        _tid, c = gate.contracted_tool()
        tr = copy.deepcopy(c["contract_traceability_envelope"])
        original = tr["traceability_envelope_hash"]
        tr["traceability_envelope_hash"] = "tampered"
        assert tc._core_hash(tr, "traceability_envelope_hash") == original


class TestTraceabilityEndpoint:
    def test_get_traceability_endpoint(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/traceability", actor=OWNER)
        assert r.status_code == 200
        body = r.json()
        assert body["contract_id"] == c["contract_id"]
        tr = body["contract_traceability_envelope"]
        assert tr["traceability_envelope_hash"] \
            == c["contract_traceability_envelope"]["traceability_envelope_hash"]
        for k in _SOURCE_HASHES:
            assert tr.get(k) is not None, k
        assert body["honesty_labels"] == tc.HONESTY_LABELS

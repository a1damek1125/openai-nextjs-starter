"""TOOL-B3 contract hashing + tamper verification.

Exercises the hash-verifiable structure of a contract: every sub-model carries
its own non-empty hash, canonical JSON is key-order independent and rejects
non-finite floats, a fresh contract verifies MATCHED, and a mutated stored
sub-object verifies MISMATCHED.
"""
import json

from conftest import OWNER
from finalis.ai_employee import tool_contracts as tc


class TestHashFieldsPresent:
    def test_contract_hash_present_nonempty(self, gate):
        _, c = gate.contracted_tool()
        assert isinstance(c["contract_hash"], str) and len(c["contract_hash"])

    def test_abi_hash_present_nonempty(self, gate):
        _, c = gate.contracted_tool()
        assert c["contract_abi"]["abi_hash"]

    def test_normal_form_hash_present_nonempty(self, gate):
        _, c = gate.contracted_tool()
        assert c["contract_normal_form"]["contract_normal_form_hash"]

    def test_effect_trace_hash_present_nonempty(self, gate):
        _, c = gate.contracted_tool()
        assert c["effect_trace_semantics"]["effect_trace_semantics_hash"]

    def test_deny_graph_hash_present_nonempty(self, gate):
        _, c = gate.contracted_tool()
        assert c["runtime_capability_deny_graph"]["deny_graph_hash"]

    def test_scope_binding_hash_present_nonempty(self, gate):
        _, c = gate.contracted_tool()
        assert c["contract_scope_binding"]["scope_binding_hash"]

    def test_traceability_envelope_hash_present_nonempty(self, gate):
        _, c = gate.contracted_tool()
        assert c["contract_traceability_envelope"]["traceability_envelope_hash"]

    def test_contract_state_hash_present(self, gate):
        _, c = gate.contracted_tool()
        assert c["contract_state_hash"]


class TestHashDeterminism:
    def test_same_source_tool_shares_source_derived_hashes(self, gate):
        # The source fingerprints are deterministic on the underlying tool: two
        # contracts of the SAME tool agree on descriptor/quality/freshness.
        tid = gate.contract_tool()
        c1 = gate.create_contract(tid).json()
        c2 = gate.create_contract(tid).json()
        assert c1["source_descriptor_hash"] == c2["source_descriptor_hash"]
        assert c1["source_quality_report_hash"] == c2[
            "source_quality_report_hash"]
        assert c1["source_freshness_epoch"] == c2["source_freshness_epoch"]

    def test_same_source_tool_yields_same_contract_hash(self, gate):
        # contract_id is source-derived and creation is idempotent, so
        # re-creating over an unchanged source returns the same contract with
        # an identical contract_id and contract_hash (excludes state/created_at).
        tid = gate.contract_tool()
        c1 = gate.create_contract(tid).json()
        c2 = gate.create_contract(tid).json()
        assert c1["contract_id"] == c2["contract_id"]
        assert c1["contract_hash"] == c2["contract_hash"]

    def test_different_tool_has_different_contract_hash(self, gate):
        _, c1 = gate.contracted_tool()
        _, c2 = gate.contracted_tool(
            tool_name="Distinct Ledger Reader",
            tool_summary="read-only ledger lookups over local records",
            tool_description="Read-only lookup over local ledger rows by id; "
            "returns matching rows. No side effects, no external calls.")
        assert c1["contract_hash"] != c2["contract_hash"]


class TestCanonicalJson:
    def test_key_order_independent(self):
        assert tc.canonical_json({"a": 1, "b": 2, "c": [1, 2]}) == \
            tc.canonical_json({"c": [1, 2], "b": 2, "a": 1})

    def test_nan_rejected(self):
        import pytest
        with pytest.raises(ValueError):
            tc.canonical_json(float("nan"))

    def test_infinity_rejected(self):
        import pytest
        with pytest.raises(ValueError):
            tc.canonical_json(float("inf"))


class TestVerify:
    def test_fresh_contract_verifies_matched(self, gate):
        tid, c = gate.contracted_tool()
        v = gate.ct(tid, c["contract_id"], path="/verify", method="POST").json()
        assert v["verification_status"] == "MATCHED"
        assert v["tamper_detected"] is False
        assert v["stale"] is False

    def test_tampered_sub_object_verifies_mismatched(self, gate):
        tid, c = gate.contracted_tool()
        cid = c["contract_id"]
        row = gate.db.one(
            "SELECT payload_json FROM ai_tool_contracts WHERE id=?", cid)
        p = json.loads(row["payload_json"])
        # Mutate a nested sub-object without recomputing any hash.
        p["contract_normal_form"]["normalized_name"] = "TAMPERED NAME"
        gate.db.conn.execute(
            "UPDATE ai_tool_contracts SET payload_json=? WHERE id=?",
            (json.dumps(p), cid))
        gate.db.conn.commit()
        v = gate.ct(tid, cid, path="/verify", method="POST").json()
        assert v["verification_status"] == "MISMATCHED"
        assert v["tamper_detected"] is True
        assert v["tamper_reasons"]

    def test_verify_carries_honesty_labels(self, gate):
        tid, c = gate.contracted_tool()
        v = gate.ct(tid, c["contract_id"], path="/verify", method="POST").json()
        assert isinstance(v["honesty_labels"], list) and v["honesty_labels"]

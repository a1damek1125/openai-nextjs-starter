"""TOOL-B3 contract proof bundle (tc.build_proof_bundle).

The proof bundle aggregates proof-obligation / ledger / non-interference state
into a single MATCHED / FAILED / NEEDS_REVIEW verdict with cross-model refs and
finite violation-witness hashes. A clean projection is MATCHED; a
runtime-requested or B1-blocked projection is FAILED and blocks broker
readiness. Read via GET .../proof-bundle.
"""
from tests.conftest import OWNER


def _bundle(gate, tid, cid):
    return gate.ct(tid, cid, "/proof-bundle").json()["contract_proof_bundle"]


def _b1_blocked_contract(gate):
    """A forbidden PAYMENT tool is B1 security-blocked at the source."""
    tid = gate.contract_tool(
        admit=False, tool_name="Pay Vendor", category="PAYMENT",
        side_effect_class="PAYMENT_MOVEMENT",
        declared_side_effects=["PAYMENT_MOVEMENT"], touches_payment=True)
    c = gate.create_contract(tid).json()
    return tid, c["contract_id"]


class TestCleanProofBundle:
    def test_status_matched(self, gate):
        tid, c = gate.contracted_tool()
        assert _bundle(gate, tid, c["contract_id"])[
            "proof_bundle_status"] == "MATCHED"

    def test_no_failed_or_review_obligations(self, gate):
        tid, c = gate.contracted_tool()
        b = _bundle(gate, tid, c["contract_id"])
        assert b["failed_obligations"] == []
        assert b["review_obligations"] == []

    def test_refs_present(self, gate):
        tid, c = gate.contracted_tool()
        b = _bundle(gate, tid, c["contract_id"])
        for ref in ("effect_trace_ref", "runtime_deny_graph_ref",
                    "non_interference_ref", "scope_proof_ref",
                    "traceability_ref"):
            assert b[ref], ref

    def test_violation_witnesses_empty_list(self, gate):
        tid, c = gate.contracted_tool()
        b = _bundle(gate, tid, c["contract_id"])
        assert isinstance(b["violation_witnesses"], list)
        assert b["violation_witnesses"] == []

    def test_bundle_hash_present(self, gate):
        tid, c = gate.contracted_tool()
        b = _bundle(gate, tid, c["contract_id"])
        assert b["contract_proof_bundle_hash"]


class TestRuntimeRequestedProofBundle:
    def test_status_failed(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"], runtime_requested=True).json()
        b = env["contract_proof_bundle"]
        assert b["proof_bundle_status"] == "FAILED"

    def test_runtime_failed_obligations_recorded(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"], runtime_requested=True).json()
        b = env["contract_proof_bundle"]
        assert "runtime_capability_deny_graph_matched" in b["failed_obligations"]

    def test_runtime_bundle_has_violation_witness_hashes(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"], runtime_requested=True).json()
        b = env["contract_proof_bundle"]
        assert b["violation_witnesses"]
        assert all(isinstance(h, str) for h in b["violation_witnesses"])

    def test_runtime_bundle_blocks_broker_readiness(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"], runtime_requested=True).json()
        cert = env["broker_readiness_certificate"]
        assert cert["certificate_status"] != \
            "READY_FOR_FUTURE_BROKER_CONSIDERATION"
        assert "PROOF_BUNDLE_FAILED" in cert["certificate_blockers"]


class TestB1BlockedProofBundle:
    def test_status_failed(self, gate):
        tid, cid = _b1_blocked_contract(gate)
        assert _bundle(gate, tid, cid)["proof_bundle_status"] == "FAILED"

    def test_b1_blocked_blocks_broker_readiness(self, gate):
        tid, cid = _b1_blocked_contract(gate)
        cert = gate.ct(tid, cid, "/broker-readiness").json()[
            "broker_readiness_certificate"]
        assert cert["certificate_status"] == "BLOCKED"
        assert "PROOF_BUNDLE_FAILED" in cert["certificate_blockers"]


class TestProofBundleEndpoint:
    def test_get_proof_bundle_ok(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/proof-bundle")
        assert r.status_code == 200
        assert r.json()["contract_id"] == c["contract_id"]

    def test_hash_stable_across_reads(self, gate):
        tid, c = gate.contracted_tool()
        h1 = _bundle(gate, tid, c["contract_id"])["contract_proof_bundle_hash"]
        h2 = _bundle(gate, tid, c["contract_id"])["contract_proof_bundle_hash"]
        assert h1 == h2

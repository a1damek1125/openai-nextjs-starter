"""TOOL-B3 proof obligations (tc.build_proof_obligations).

A projection carries a list of named proof obligations, each with a status and
hash. A clean projection matches every obligation; a runtime-requested
projection fails runtime_capability_deny_graph_matched and drives the projection
to BLOCKED. Read via GET .../proof-obligations.
"""
from finalis.ai_employee import tool_contracts as tc
from tests.conftest import OWNER


def _obligations(gate, tid, cid):
    return gate.ct(tid, cid, "/proof-obligations").json()["proof_obligations"]


class TestCleanProofObligations:
    def test_list_present(self, gate):
        tid, c = gate.contracted_tool()
        obs = _obligations(gate, tid, c["contract_id"])
        assert isinstance(obs, list)
        assert obs

    def test_each_has_name_and_status(self, gate):
        tid, c = gate.contracted_tool()
        obs = _obligations(gate, tid, c["contract_id"])
        for o in obs:
            assert o["obligation_name"]
            assert o["obligation_status"] in ("MATCHED", "FAILED",
                                              "NEEDS_REVIEW")

    def test_all_matched(self, gate):
        tid, c = gate.contracted_tool()
        obs = _obligations(gate, tid, c["contract_id"])
        assert all(o["obligation_status"] == "MATCHED" for o in obs)

    def test_covers_named_obligation_set(self, gate):
        tid, c = gate.contracted_tool()
        obs = _obligations(gate, tid, c["contract_id"])
        names = {o["obligation_name"] for o in obs}
        assert set(tc.PROOF_OBLIGATION_NAMES).issubset(names)

    def test_each_has_hash(self, gate):
        tid, c = gate.contracted_tool()
        obs = _obligations(gate, tid, c["contract_id"])
        assert all(o["proof_obligation_hash"] for o in obs)

    def test_runtime_deny_graph_obligation_matched_when_clean(self, gate):
        tid, c = gate.contracted_tool()
        by = {o["obligation_name"]: o["obligation_status"]
              for o in _obligations(gate, tid, c["contract_id"])}
        assert by["runtime_capability_deny_graph_matched"] == "MATCHED"


class TestRuntimeRequestedProofObligations:
    def test_runtime_deny_graph_obligation_failed(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"], runtime_requested=True).json()
        by = {o["obligation_name"]: o["obligation_status"]
              for o in env["proof_obligations"]}
        assert by["runtime_capability_deny_graph_matched"] == "FAILED"

    def test_failed_obligation_blocks_projection(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"], runtime_requested=True).json()
        assert env["projection_status"] == "BLOCKED"

    def test_endpoint_reflects_latest_runtime_projection(self, gate):
        tid, c = gate.contracted_tool()
        gate.project(tid, c["contract_id"], runtime_requested=True)
        obs = _obligations(gate, tid, c["contract_id"])
        by = {o["obligation_name"]: o["obligation_status"] for o in obs}
        assert by["runtime_capability_deny_graph_matched"] == "FAILED"

    def test_failed_obligation_carries_witness_ref(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"], runtime_requested=True).json()
        by = {o["obligation_name"]: o for o in env["proof_obligations"]}
        # The projection recorded a runtime violation witness.
        assert env["violation_witnesses"]


class TestProofObligationsEndpoint:
    def test_get_ok(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/proof-obligations")
        assert r.status_code == 200
        body = r.json()
        assert body["contract_id"] == c["contract_id"]
        assert isinstance(body["proof_obligations"], list)

    def test_hashes_stable_across_reads(self, gate):
        tid, c = gate.contracted_tool()
        h1 = [o["proof_obligation_hash"]
              for o in _obligations(gate, tid, c["contract_id"])]
        h2 = [o["proof_obligation_hash"]
              for o in _obligations(gate, tid, c["contract_id"])]
        assert h1 == h2

    def test_direct_kernel_obligation_hash_deterministic(self):
        a = tc.build_proof_obligations(tenant_id="t", contract_id="c",
                                       projection_id="p", results={})
        b = tc.build_proof_obligations(tenant_id="t", contract_id="c",
                                       projection_id="p", results={})
        assert [o["proof_obligation_hash"] for o in a] == \
            [o["proof_obligation_hash"] for o in b]

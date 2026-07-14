"""TOOL-B3 finite violation witness (tc.build_violation_witness).

When a projection firewall check fails, the kernel emits a finite, hash-verified
witness naming the violated invariant, the offending field, the source model,
and the (secret-redacted) expected/actual values. A clean projection produces
NONE.
"""
from finalis.ai_employee import tool_contracts as tc
from tests.conftest import OWNER


class TestRuntimeRequestedWitness:
    def test_runtime_witness_present(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"], runtime_requested=True).json()
        assert env["violation_witnesses"]

    def test_runtime_witness_invariant_and_status(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"], runtime_requested=True).json()
        invs = {w["violated_invariant"] for w in env["violation_witnesses"]}
        assert "runtime_capability_deny_graph_matched" in invs
        w = next(w for w in env["violation_witnesses"]
                 if w["violated_invariant"]
                 == "runtime_capability_deny_graph_matched")
        assert w["dominant_failure_status"]

    def test_runtime_witness_has_hash_and_source(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"], runtime_requested=True).json()
        w = env["violation_witnesses"][0]
        assert w["violation_witness_hash"]
        assert w["source_model"]
        assert w["source_hash"]


class TestB1BlockedWitness:
    def _forbidden_env(self, gate):
        tid = gate.contract_tool(
            admit=False, tool_name="Pay Vendor", category="PAYMENT",
            side_effect_class="PAYMENT_MOVEMENT",
            declared_side_effects=["PAYMENT_MOVEMENT"], touches_payment=True)
        c = gate.create_contract(tid).json()
        return gate.project(tid, c["contract_id"],
                            target="INTERNAL_TOOL_BROKER_CONTRACT").json()

    def test_b1_admission_witness_present(self, gate):
        env = self._forbidden_env(gate)
        invs = {w["violated_invariant"] for w in env["violation_witnesses"]}
        assert "tool_b1_admission_matched" in invs

    def test_b1_witness_field_path(self, gate):
        env = self._forbidden_env(gate)
        w = next(w for w in env["violation_witnesses"]
                 if w["violated_invariant"] == "tool_b1_admission_matched")
        assert w["violating_field_path"] == "head.status"
        assert w["source_model"] == "tool_registry"


class TestSecretRedaction:
    def test_secret_actual_redacted(self):
        w = tc.build_violation_witness(
            tenant_id="t", contract_id="c", projection_id="p",
            violated_invariant="x", field_path="f", source_model="m",
            source_hash="h", expected="ok", actual="my api_token secret",
            dominant_status="BLOCKED", explanation="e")
        assert w["actual_value"] == "[REDACTED — secret-like value]"

    def test_password_actual_redacted(self):
        w = tc.build_violation_witness(
            tenant_id="t", contract_id="c", projection_id="p",
            violated_invariant="x", field_path="f", source_model="m",
            source_hash="h", expected="ok", actual="the password is hunter2",
            dominant_status="BLOCKED", explanation="e")
        assert w["actual_value"] == "[REDACTED — secret-like value]"

    def test_non_secret_actual_preserved(self):
        w = tc.build_violation_witness(
            tenant_id="t", contract_id="c", projection_id="p",
            violated_invariant="x", field_path="f", source_model="m",
            source_hash="h", expected="ok", actual="runtime requested",
            dominant_status="BLOCKED", explanation="e")
        assert w["actual_value"] == "runtime requested"


class TestWitnessHashDeterminism:
    def test_direct_kernel_hash_deterministic(self):
        kw = dict(tenant_id="t", contract_id="c", projection_id="p",
                  violated_invariant="x", field_path="f", source_model="m",
                  source_hash="h", expected="ok", actual="runtime requested",
                  dominant_status="BLOCKED", explanation="e")
        a = tc.build_violation_witness(**kw)
        b = tc.build_violation_witness(**kw)
        assert a["violation_witness_hash"] == b["violation_witness_hash"]

    def test_different_invariant_changes_hash(self):
        base = dict(tenant_id="t", contract_id="c", projection_id="p",
                    field_path="f", source_model="m", source_hash="h",
                    expected="ok", actual="v", dominant_status="BLOCKED",
                    explanation="e")
        a = tc.build_violation_witness(violated_invariant="x", **base)
        b = tc.build_violation_witness(violated_invariant="y", **base)
        assert a["violation_witness_hash"] != b["violation_witness_hash"]

    def test_projection_witness_hash_matches_proof_bundle_ref(self, gate):
        # The witness hash recorded on the envelope is the same hash the proof
        # bundle references for that projection.
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"], runtime_requested=True).json()
        env_hashes = {w["violation_witness_hash"]
                      for w in env["violation_witnesses"]}
        bundle_hashes = set(env["contract_proof_bundle"]["violation_witnesses"])
        assert env_hashes == bundle_hashes
        assert env_hashes


class TestCleanProjectionNoWitness:
    def test_clean_projection_has_no_witnesses(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"]).json()
        assert env["violation_witnesses"] == []

    def test_clean_default_projection_has_no_witnesses(self, gate):
        tid, c = gate.contracted_tool()
        # The default internal-broker projection created at contract creation.
        bundle = gate.ct(tid, c["contract_id"], "/proof-bundle").json()[
            "contract_proof_bundle"]
        assert bundle["violation_witnesses"] == []

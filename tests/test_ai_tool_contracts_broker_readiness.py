"""TOOL-B3 broker-readiness certificate (tc.build_broker_readiness).

The certificate reports whether a contract projection is READY for a FUTURE
Tool Broker to CONSIDER. It never executes and never overrides a blocker: any
blocker keeps it out of READY. A clean admitted+quality-passed tool is
READY_FOR_FUTURE_BROKER_CONSIDERATION; an un-admitted tool carries
TOOL_B1_NOT_ADMITTED and is NOT_READY; a forbidden PAYMENT tool is BLOCKED.
Read via GET .../broker-readiness.
"""
from tests.conftest import OWNER

READY = "READY_FOR_FUTURE_BROKER_CONSIDERATION"


def _cert(gate, tid, cid):
    return gate.ct(tid, cid, "/broker-readiness").json()[
        "broker_readiness_certificate"]


class TestReadyCertificate:
    def test_clean_tool_ready(self, gate):
        tid, c = gate.contracted_tool()
        cert = _cert(gate, tid, c["contract_id"])
        assert cert["certificate_status"] == READY

    def test_ready_has_no_blockers(self, gate):
        tid, c = gate.contracted_tool()
        cert = _cert(gate, tid, c["contract_id"])
        assert cert["certificate_blockers"] == []

    def test_ready_carries_source_hashes(self, gate):
        tid, c = gate.contracted_tool()
        cert = _cert(gate, tid, c["contract_id"])
        for h in ("source_descriptor_hash", "contract_hash", "projection_hash",
                  "proof_bundle_hash", "effect_trace_semantics_hash",
                  "scope_binding_hash", "certificate_hash"):
            assert cert[h], h


class TestNotAdmitted:
    def test_blocker_tool_b1_not_admitted(self, gate):
        tid = gate.contract_tool(admit=False)
        c = gate.create_contract(tid).json()
        cert = _cert(gate, tid, c["contract_id"])
        assert "TOOL_B1_NOT_ADMITTED" in cert["certificate_blockers"]

    def test_status_not_ready_or_blocked(self, gate):
        tid = gate.contract_tool(admit=False)
        c = gate.create_contract(tid).json()
        cert = _cert(gate, tid, c["contract_id"])
        assert cert["certificate_status"] in ("NOT_READY", "BLOCKED")
        assert cert["certificate_status"] != READY


class TestForbiddenPaymentBlocked:
    def _forbidden(self, gate):
        tid = gate.contract_tool(
            admit=False, tool_name="Pay Vendor", category="PAYMENT",
            side_effect_class="PAYMENT_MOVEMENT",
            declared_side_effects=["PAYMENT_MOVEMENT"], touches_payment=True)
        c = gate.create_contract(tid).json()
        return tid, c["contract_id"]

    def test_status_blocked(self, gate):
        tid, cid = self._forbidden(gate)
        assert _cert(gate, tid, cid)["certificate_status"] == "BLOCKED"

    def test_carries_b1_blocker(self, gate):
        tid, cid = self._forbidden(gate)
        cert = _cert(gate, tid, cid)
        assert "TOOL_B1_NOT_ADMITTED" in cert["certificate_blockers"]
        assert cert["certificate_status"] != READY


class TestCertificateCannotOverrideBlockers:
    def test_blockers_present_never_ready_admit_false(self, gate):
        tid = gate.contract_tool(admit=False)
        c = gate.create_contract(tid).json()
        cert = _cert(gate, tid, c["contract_id"])
        assert cert["certificate_blockers"]
        assert cert["certificate_status"] != READY

    def test_blockers_present_never_ready_runtime(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"], runtime_requested=True).json()
        cert = env["broker_readiness_certificate"]
        assert cert["certificate_blockers"]
        assert cert["certificate_status"] != READY

    def test_policy_declares_no_override(self, gate):
        p = gate.c.get("/ai-tools/registry/contracts/policy",
                       headers=gate.h(OWNER)).json()
        assert p["certificate_can_override_blockers"] is False


class TestCertificateHashDeterminism:
    def test_hash_stable_across_reads(self, gate):
        tid, c = gate.contracted_tool()
        h1 = _cert(gate, tid, c["contract_id"])["certificate_hash"]
        h2 = _cert(gate, tid, c["contract_id"])["certificate_hash"]
        assert h1 == h2

    def test_ready_and_blocked_hashes_differ(self, gate):
        tid, c = gate.contracted_tool()
        ready_hash = _cert(gate, tid, c["contract_id"])["certificate_hash"]
        tid2 = gate.contract_tool(admit=False)
        c2 = gate.create_contract(tid2).json()
        blocked_hash = _cert(gate, tid2, c2["contract_id"])["certificate_hash"]
        assert ready_hash != blocked_hash


class TestBrokerReadinessEndpoint:
    def test_get_ok(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/broker-readiness")
        assert r.status_code == 200
        assert r.json()["contract_id"] == c["contract_id"]

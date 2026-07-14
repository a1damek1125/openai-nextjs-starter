"""TOOL-B3 deontic obligation ledger (tc.build_deontic_ledger).

A projection carries a deontic obligation ledger: a list of REQUIRED
obligations, each MATCHED for a clean projection. A runtime-requested
projection must FAIL the deny_runtime_capability obligation. The ledger hash is
deterministic and readable via GET .../obligations.
"""
from finalis.ai_employee import tool_contracts as tc
from tests.conftest import OWNER


def _ledger(gate, tid, cid):
    return gate.ct(tid, cid, "/obligations").json()["deontic_obligation_ledger"]


class TestCleanLedger:
    def test_all_required_and_matched(self, gate):
        tid, c = gate.contracted_tool()
        led = _ledger(gate, tid, c["contract_id"])
        assert led["obligations"]
        assert all(o["deontic_class"] == "REQUIRED" for o in led["obligations"])
        assert all(o["obligation_status"] == "MATCHED"
                   for o in led["obligations"])

    def test_ledger_status_matched(self, gate):
        tid, c = gate.contracted_tool()
        led = _ledger(gate, tid, c["contract_id"])
        assert led["ledger_status"] == "MATCHED"
        assert led["failed_obligations"] == []

    def test_required_obligation_types_present(self, gate):
        tid, c = gate.contracted_tool()
        led = _ledger(gate, tid, c["contract_id"])
        types = {o["obligation_type"] for o in led["obligations"]}
        for required in ("preserve_tenant_scope",
                         "preserve_approval_requirement", "preserve_risk_class",
                         "deny_runtime_capability", "deny_token_passthrough",
                         "deny_execution", "deny_llm_calls",
                         "deny_tool_broker_calls"):
            assert required in types, required

    def test_ledger_covers_full_required_set(self, gate):
        tid, c = gate.contracted_tool()
        led = _ledger(gate, tid, c["contract_id"])
        types = [o["obligation_type"] for o in led["obligations"]]
        assert types == tc._REQUIRED_OBLIGATIONS

    def test_ledger_hash_present(self, gate):
        tid, c = gate.contracted_tool()
        led = _ledger(gate, tid, c["contract_id"])
        assert led["deontic_obligation_ledger_hash"]


class TestRuntimeRequestedLedger:
    def test_runtime_fails_deny_runtime_capability(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"], runtime_requested=True).json()
        led = env["deontic_obligation_ledger"]
        assert led["ledger_status"] == "FAILED"
        assert "deny_runtime_capability" in led["failed_obligations"]

    def test_runtime_deny_runtime_capability_obligation_failed(self, gate):
        tid, c = gate.contracted_tool()
        env = gate.project(tid, c["contract_id"], runtime_requested=True).json()
        led = env["deontic_obligation_ledger"]
        by_type = {o["obligation_type"]: o["obligation_status"]
                   for o in led["obligations"]}
        assert by_type["deny_runtime_capability"] == "FAILED"

    def test_runtime_ledger_reflected_via_endpoint(self, gate):
        # GET /obligations returns the LATEST projection's ledger.
        tid, c = gate.contracted_tool()
        gate.project(tid, c["contract_id"], runtime_requested=True)
        led = _ledger(gate, tid, c["contract_id"])
        assert led["ledger_status"] == "FAILED"
        assert "deny_runtime_capability" in led["failed_obligations"]


class TestLedgerHashDeterminism:
    def test_endpoint_hash_stable_across_reads(self, gate):
        tid, c = gate.contracted_tool()
        h1 = _ledger(gate, tid, c["contract_id"])[
            "deontic_obligation_ledger_hash"]
        h2 = _ledger(gate, tid, c["contract_id"])[
            "deontic_obligation_ledger_hash"]
        assert h1 == h2

    def test_direct_kernel_hash_deterministic(self):
        a = tc.build_deontic_ledger(tenant_id="t", contract_id="c",
                                    projection_id="p", obligation_results={})
        b = tc.build_deontic_ledger(tenant_id="t", contract_id="c",
                                    projection_id="p", obligation_results={})
        assert a["deontic_obligation_ledger_hash"] == b[
            "deontic_obligation_ledger_hash"]

    def test_direct_kernel_failure_changes_hash(self):
        clean = tc.build_deontic_ledger(tenant_id="t", contract_id="c",
                                        projection_id="p", obligation_results={})
        failed = tc.build_deontic_ledger(
            tenant_id="t", contract_id="c", projection_id="p",
            obligation_results={"deny_runtime_capability": False})
        assert failed["ledger_status"] == "FAILED"
        assert clean["deontic_obligation_ledger_hash"] != failed[
            "deontic_obligation_ledger_hash"]


class TestObligationsEndpoint:
    def test_get_obligations_ok(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/obligations")
        assert r.status_code == 200
        body = r.json()
        assert body["contract_id"] == c["contract_id"]
        assert "deontic_obligation_ledger" in body

    def test_get_obligations_readable_by_viewer(self, gate):
        from tests.conftest import VIEWER
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/obligations", actor=VIEWER)
        assert r.status_code == 200
        assert r.json()["deontic_obligation_ledger"]["ledger_status"] \
            == "MATCHED"

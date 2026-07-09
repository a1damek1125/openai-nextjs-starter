"""TOOL-B3 protocol method firewall tests.

The method firewall declares the contract to be a TOOL_DESCRIPTOR only: the sole
allowed method class is TOOL_DESCRIPTOR, and every other protocol method class
(sampling/elicitation/resource/prompt/roots/etc.) is blocked. A contract that
requests runtime is BLOCKED; prose that implies resource/prompt/sampling/... is
flagged as method confusion. These assert the firewall via the kernel and the
GET /method-firewall endpoint.
"""
from finalis.ai_employee import tool_contracts as tc


class TestAllowedAndBlockedClasses:
    def test_declared_method_class(self, gate):
        tid, c = gate.contracted_tool()
        fw = c["protocol_method_firewall"]
        assert fw["declared_method_class"] == "TOOL_DESCRIPTOR"

    def test_allowed_is_only_tool_descriptor(self, gate):
        tid, c = gate.contracted_tool()
        fw = c["protocol_method_firewall"]
        assert set(fw["allowed_method_classes"]) == {"TOOL_DESCRIPTOR"}

    def test_blocked_classes_include_runtime_methods(self, gate):
        tid, c = gate.contracted_tool()
        blocked = set(c["protocol_method_firewall"]["blocked_method_classes"])
        for cls in ("SAMPLING_REQUEST", "ELICITATION_REQUEST",
                    "RESOURCE_DESCRIPTOR", "PROMPT_DESCRIPTOR",
                    "ROOTS_DECLARATION"):
            assert cls in blocked, cls

    def test_blocked_equals_all_but_allowed(self, gate):
        tid, c = gate.contracted_tool()
        fw = c["protocol_method_firewall"]
        assert set(fw["blocked_method_classes"]) == (
            tc.METHOD_CLASSES - tc.ALLOWED_METHOD_CLASSES)
        # Allowed and blocked partition the full method-class space.
        assert set(fw["allowed_method_classes"]) & set(
            fw["blocked_method_classes"]) == set()

    def test_tool_descriptor_never_blocked(self, gate):
        tid, c = gate.contracted_tool()
        fw = c["protocol_method_firewall"]
        assert "TOOL_DESCRIPTOR" not in fw["blocked_method_classes"]


class TestNormalContract:
    def test_runtime_method_not_requested(self, gate):
        tid, c = gate.contracted_tool()
        fw = c["protocol_method_firewall"]
        assert fw["runtime_method_requested"] is False

    def test_clean_contract_matched(self, gate):
        tid, c = gate.contracted_tool()
        fw = c["protocol_method_firewall"]
        assert fw["method_firewall_status"] == "MATCHED"
        assert fw["detected_method_confusion"] == []


class TestRuntimeRequested:
    def test_runtime_requested_blocked(self, gate):
        tid = gate.contract_tool()
        c = gate.create_contract(tid, runtime_requested=True).json()
        fw = c["protocol_method_firewall"]
        assert fw["runtime_method_requested"] is True
        assert fw["method_firewall_status"] == "BLOCKED"

    def test_runtime_requested_blocks_contract(self, gate):
        tid = gate.contract_tool()
        c = gate.create_contract(tid, runtime_requested=True).json()
        assert c["contract_status"] == "BLOCKED"
        assert "PROTOCOL_METHOD_VIOLATION" in c["contract_blockers"]


class TestMethodConfusion:
    def test_prose_confusion_detected(self, gate):
        tid = gate.contract_tool(
            tool_name="Res Reader",
            tool_description="read only tool that lists resource entries and "
            "serves prompt templates",
            tool_summary="resources and prompt server")
        c = gate.create_contract(tid).json()
        fw = c["protocol_method_firewall"]
        assert "RESOURCE_DESCRIPTOR" in fw["detected_method_confusion"]
        assert "PROMPT_DESCRIPTOR" in fw["detected_method_confusion"]
        assert fw["method_firewall_status"] == "NEEDS_REVIEW"

    def test_sampling_prose_confusion(self, gate):
        tid = gate.contract_tool(
            tool_name="Sampler",
            tool_description="read only helper using sampling to draft replies",
            tool_summary="sampling helper")
        c = gate.create_contract(tid).json()
        fw = c["protocol_method_firewall"]
        assert "SAMPLING_REQUEST" in fw["detected_method_confusion"]


class TestFirewallHashAndEndpoint:
    def test_firewall_hash_deterministic(self, gate):
        desc = {"tool_description": "read only local search", "tool_summary": ""}
        f1 = tc.build_method_firewall(tenant_id="t", contract_id="c",
                                      tool_id="x", descriptor=desc,
                                      runtime_requested=False)
        f2 = tc.build_method_firewall(tenant_id="t", contract_id="c",
                                      tool_id="x", descriptor=desc,
                                      runtime_requested=False)
        assert f1["method_firewall_hash"] == f2["method_firewall_hash"]
        assert tc._core_hash(f1, "method_firewall_hash") == f1[
            "method_firewall_hash"]

    def test_get_method_firewall_endpoint(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/method-firewall")
        assert r.status_code == 200
        fw = r.json()["protocol_method_firewall"]
        assert set(fw["allowed_method_classes"]) == {"TOOL_DESCRIPTOR"}
        assert fw["method_firewall_status"] == "MATCHED"
        assert fw == c["protocol_method_firewall"]

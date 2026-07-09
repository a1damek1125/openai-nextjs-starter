"""TOOL-B3 contract ABI (application binary interface) tests.

The ABI captures the interface shape of a contract: input/output schema hashes,
effect, data-scope, auth, approval, consent, prompt-context, protocol boundary
and runtime-capability denials. The abi_hash is deterministic and excludes both
itself and the abi_breaking_change_flags. Changing the input/output schema or
the effect/scope changes the interface hashes.
"""
import copy

from finalis.ai_employee import tool_contracts as tc
from tests.conftest import OWNER

_ABI_SUBFIELDS = [
    "input_abi", "output_abi", "effect_abi", "effect_trace_abi",
    "data_scope_abi", "auth_abi", "approval_abi", "consent_abi",
    "prompt_context_abi", "protocol_boundary_abi", "runtime_capability_abi",
    "abi_breaking_change_flags", "abi_hash",
]

# Interface sub-hashes that are a pure function of the descriptor shape (they do
# NOT embed the contract/tool identity, unlike the top-level abi_hash).
_INTERFACE_SUBFIELDS = [
    "input_abi", "output_abi", "effect_abi", "data_scope_abi", "auth_abi",
    "approval_abi", "consent_abi", "prompt_context_abi",
    "protocol_boundary_abi", "runtime_capability_abi",
]


class TestAbiPresence:
    def test_abi_present_with_all_subfields(self, gate):
        _tid, c = gate.contracted_tool()
        abi = c["contract_abi"]
        for f in _ABI_SUBFIELDS:
            assert f in abi, f

    def test_abi_hash_is_hex64(self, gate):
        _tid, c = gate.contracted_tool()
        h = c["contract_abi"]["abi_hash"]
        assert len(h) == 64 and all(ch in "0123456789abcdef" for ch in h)

    def test_input_abi_is_hash_of_input_schema(self, gate):
        _tid, c = gate.contracted_tool()
        nf = c["contract_normal_form"]
        assert c["contract_abi"]["input_abi"] \
            == tc._sha(nf["normalized_input_schema"])

    def test_runtime_capability_abi_hashes_denials(self, gate):
        _tid, c = gate.contracted_tool()
        nf = c["contract_normal_form"]
        assert c["contract_abi"]["runtime_capability_abi"] \
            == tc._sha(nf["normalized_runtime_capability_denials"])


class TestAbiHashDeterminism:
    def test_abi_hash_recomputes_and_self_excludes(self, gate):
        _tid, c = gate.contracted_tool()
        abi = c["contract_abi"]
        assert tc._core_hash(abi, "abi_hash", "abi_breaking_change_flags") \
            == abi["abi_hash"]

    def test_kernel_identical_inputs_share_abi_hash(self, gate):
        _tid, c = gate.contracted_tool()
        nf, et = c["contract_normal_form"], c["effect_trace_semantics"]
        kw = dict(tenant_id="t", tool_id="x", tool_version_id="v",
                  contract_id="c", normal_form=nf, effect_trace=et)
        assert tc.build_abi(**kw)["abi_hash"] == tc.build_abi(**kw)["abi_hash"]

    def test_abi_hash_excludes_breaking_change_flags(self, gate):
        _tid, c = gate.contracted_tool()
        nf, et = c["contract_normal_form"], c["effect_trace_semantics"]
        kw = dict(tenant_id="t", tool_id="x", tool_version_id="v",
                  contract_id="c", normal_form=nf, effect_trace=et)
        base = tc.build_abi(**kw)
        # A non-matching previous hash records a breaking-change flag, but the
        # abi_hash itself must be unchanged (the flag is excluded from it).
        flagged = tc.build_abi(previous_abi_hash="deadbeef", **kw)
        assert flagged["abi_breaking_change_flags"] == ["ABI_HASH_CHANGED"]
        assert base["abi_breaking_change_flags"] == []
        assert flagged["abi_hash"] == base["abi_hash"]

    def test_matching_previous_hash_records_no_breaking_flag(self, gate):
        _tid, c = gate.contracted_tool()
        nf, et = c["contract_normal_form"], c["effect_trace_semantics"]
        kw = dict(tenant_id="t", tool_id="x", tool_version_id="v",
                  contract_id="c", normal_form=nf, effect_trace=et)
        base = tc.build_abi(**kw)
        again = tc.build_abi(previous_abi_hash=base["abi_hash"], **kw)
        assert again["abi_breaking_change_flags"] == []


class TestAbiInterfaceEquivalence:
    def test_identical_source_share_interface_subhashes(self, gate):
        # Two independently-registered but interface-identical tools share every
        # schema/effect/scope interface hash. (Distinct names avoid the registry
        # duplicate-name quarantine; names are not part of the ABI. The
        # top-level abi_hash embeds the contract identity, so it differs — see
        # the reported suspicion.)
        _t1, c1 = gate.contracted_tool(tool_name="Alpha Search")
        _t2, c2 = gate.contracted_tool(tool_name="Beta Search")
        a1, a2 = c1["contract_abi"], c2["contract_abi"]
        for f in _INTERFACE_SUBFIELDS:
            assert a1[f] == a2[f], f


class TestAbiChangeDetection:
    def test_different_input_schema_changes_input_abi(self, gate):
        _t1, c1 = gate.contracted_tool()
        _t2, c2 = gate.contracted_tool(input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"},
                           "limit": {"type": "number"}}})
        assert c1["contract_abi"]["input_abi"] \
            != c2["contract_abi"]["input_abi"]
        assert c1["contract_abi"]["abi_hash"] != c2["contract_abi"]["abi_hash"]

    def test_different_output_schema_changes_output_abi(self, gate):
        _t1, c1 = gate.contracted_tool()
        _t2, c2 = gate.contracted_tool(output_schema={
            "type": "object",
            "properties": {"rows": {"type": "array"},
                           "total": {"type": "number"}}})
        assert c1["contract_abi"]["output_abi"] \
            != c2["contract_abi"]["output_abi"]

    def test_changing_effect_changes_effect_abi(self, gate):
        _t1, c1 = gate.contracted_tool()
        _t2, c2 = gate.contracted_tool(
            side_effect_class="EXTERNAL_WRITE",
            declared_side_effects=["EXTERNAL_WRITE"])
        assert c1["contract_abi"]["effect_abi"] \
            != c2["contract_abi"]["effect_abi"]

    def test_changing_scope_changes_data_scope_abi(self, gate):
        _t1, c1 = gate.contracted_tool()
        _t2, c2 = gate.contracted_tool(reads_data_classes=["SENSITIVE_PII"])
        assert c1["contract_abi"]["data_scope_abi"] \
            != c2["contract_abi"]["data_scope_abi"]


class TestAbiEndpoint:
    def test_get_abi_endpoint(self, gate):
        tid, c = gate.contracted_tool()
        r = gate.ct(tid, c["contract_id"], "/abi", actor=OWNER)
        assert r.status_code == 200
        body = r.json()
        assert body["contract_id"] == c["contract_id"]
        assert body["contract_abi"]["abi_hash"] \
            == c["contract_abi"]["abi_hash"]
        assert body["honesty_labels"] == tc.HONESTY_LABELS

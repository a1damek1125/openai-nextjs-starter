"""TOOL-B6: read-only microkernel admission + operation ledger + path policy.

build_microkernel admits only READ_ONLY_CAPABILITIES; build_path_policy accepts
the read*->compute->project trajectory only. Any non-read-only capability or an
out-of-order compute/project fails closed.
"""
import re

from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


_HEX64 = re.compile(r"^[0-9a-f]{64}$")

_READ = {"op": "READ_SNAPSHOT_FIELD", "capability": "READ_SNAPSHOT_FIELD"}
_COMPUTE = {"op": "COMPUTE_DETERMINISTIC", "capability": "COMPUTE_DETERMINISTIC"}
_PROJECT = {"op": "PROJECT_SAFE_OUTPUT", "capability": "PROJECT_SAFE_OUTPUT"}


def test_microkernel_admits_clean_read_only_operations():
    ops = [_READ, _READ, _COMPUTE, _PROJECT]
    mk = rt.build_microkernel(tenant_id="t", runtime_request_id="r",
                              operations=ops)
    assert mk["microkernel_status"] == "MICROKERNEL_ADMITTED_READ_ONLY"
    assert mk["signal"] is None
    assert mk["rejected_operations"] == []


def test_microkernel_rejects_non_read_only_capability():
    ops = [_READ, {"op": "WRITE", "capability": "WRITE_SOURCE"}]
    mk = rt.build_microkernel(tenant_id="t", runtime_request_id="r",
                              operations=ops)
    assert mk["microkernel_status"] == "MICROKERNEL_REJECTED"
    assert mk["signal"] == "RUNTIME_OPERATION_NOT_ADMITTED"
    assert "WRITE" in mk["rejected_operations"]


def test_microkernel_none_capability_is_unknown_capability():
    ops = [_READ, {"op": "MYSTERY", "capability": None}]
    mk = rt.build_microkernel(tenant_id="t", runtime_request_id="r",
                              operations=ops)
    assert mk["microkernel_status"] == "MICROKERNEL_REJECTED"
    assert mk["signal"] == "UNKNOWN_CAPABILITY"


def test_operation_ledger_sequence_hash_deterministic():
    ops = [_READ, _COMPUTE, _PROJECT]
    a = rt.build_operation_ledger(tenant_id="t", runtime_request_id="r",
                                  operations=ops)
    b = rt.build_operation_ledger(tenant_id="t", runtime_request_id="r",
                                  operations=list(ops))
    assert a["operation_sequence_hash"] == b["operation_sequence_hash"]
    assert _HEX64.match(a["operation_sequence_hash"])
    # A different op order yields a different sequence hash.
    c = rt.build_operation_ledger(tenant_id="t", runtime_request_id="r",
                                  operations=[_COMPUTE, _READ, _PROJECT])
    assert c["operation_sequence_hash"] != a["operation_sequence_hash"]


def test_path_policy_accepts_read_compute_project_trajectory():
    ops = [_READ, _READ, _COMPUTE, _PROJECT]
    pp = rt.build_path_policy(tenant_id="t", runtime_request_id="r",
                              operations=ops)
    assert pp["path_status"] == "PATH_ACCEPTED"
    assert pp["signal"] is None


def test_path_policy_rejects_compute_after_project():
    ops = [_READ, _PROJECT, _COMPUTE]
    pp = rt.build_path_policy(tenant_id="t", runtime_request_id="r",
                              operations=ops)
    assert pp["path_status"] == "PATH_REJECTED"
    assert pp["signal"] == "RUNTIME_PATH_POLICY_REJECTED"


def test_path_policy_rejects_non_read_only_capability():
    ops = [_READ, {"op": "NET", "capability": "NETWORK_CALL"}, _COMPUTE,
           _PROJECT]
    pp = rt.build_path_policy(tenant_id="t", runtime_request_id="r",
                              operations=ops)
    assert pp["path_status"] == "PATH_REJECTED"
    assert pp["signal"] == "RUNTIME_PATH_POLICY_REJECTED"


def test_clean_outcome_microkernel_and_path_policy_are_clean(gate):
    o = k.clean_outcome(gate)
    assert o["runtime_microkernel_contract"]["microkernel_status"] == \
        "MICROKERNEL_ADMITTED_READ_ONLY"
    assert o["runtime_microkernel_contract"]["signal"] is None
    assert o["runtime_path_policy_automaton"]["path_status"] == "PATH_ACCEPTED"
    assert o["runtime_path_policy_automaton"]["signal"] is None

"""TOOL-B6: deterministic hashing of the runtime outcome.

The runtime decision hash is a pure function of evidence: it excludes the
request id, the deciding actor and the state hash, and contains no wall-clock.
Every sub-model hash excludes itself, and canonical hashing is key-order
independent.
"""
import pytest

from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


# (report_key, self_hash_key) for a representative set of sub-models.
_SUBMODELS = [
    ("runtime_microkernel_contract", "runtime_microkernel_contract_hash"),
    ("adapter_capability_firewall", "adapter_capability_firewall_hash"),
    ("runtime_operation_ledger", "runtime_operation_ledger_hash"),
    ("runtime_path_policy_automaton", "runtime_path_policy_automaton_hash"),
    ("runtime_effect_ledger", "runtime_effect_ledger_hash"),
    ("runtime_escape_sentinel", "runtime_escape_sentinel_hash"),
    ("runtime_non_escalation_proof", "runtime_non_escalation_proof_hash"),
    ("snapshot_seal_check", "snapshot_seal_check_hash"),
    ("no_effect_proofs", "no_effect_proofs_hash"),
]


def test_decision_hash_stable_across_actor_and_created_at(gate):
    b5, b5r, snap = k.setup(gate)
    o1 = k.prepare(gate, b5, b5r, snap, runtime_request_id="rtX",
                   actor_id="alice", actor_type="human", created_at="T1")
    o2 = k.prepare(gate, b5, b5r, snap, runtime_request_id="rtX",
                   actor_id="bob", actor_type="ai", created_at="T2")
    assert o1["runtime_decision_hash"] == o2["runtime_decision_hash"]


def test_decision_hash_excludes_request_actor_and_state(gate):
    o = k.clean_outcome(gate)
    recomputed = rt._core_hash(
        o, "runtime_decision_hash", "runtime_request_id",
        "decided_by_actor_id", "decided_by_actor_type", "runtime_state_hash")
    assert recomputed == o["runtime_decision_hash"]


def test_state_hash_binds_status_decision_request_and_output(gate):
    o = k.clean_outcome(gate)
    expected = rt._sha({
        "runtime_request_id": o["runtime_request_id"],
        "runtime_decision_hash": o["runtime_decision_hash"],
        "runtime_status": o["runtime_status"],
        "dominant_signal": o["dominant_signal"],
        "runtime_request_hash": o["runtime_request_hash"],
        "safe_output_hash": o["safe_output_hash"]})
    assert o["runtime_state_hash"] == expected


def test_state_hash_stable_across_created_at(gate):
    # No wall-clock leaks into the bound state hash.
    b5, b5r, snap = k.setup(gate)
    o1 = k.prepare(gate, b5, b5r, snap, runtime_request_id="rtY",
                   actor_id="a", created_at="2020-01-01")
    o2 = k.prepare(gate, b5, b5r, snap, runtime_request_id="rtY",
                   actor_id="a", created_at="2099-12-31")
    assert o1["runtime_state_hash"] == o2["runtime_state_hash"]


@pytest.mark.parametrize("report_key,hash_key", _SUBMODELS)
def test_submodel_hash_excludes_itself(gate, report_key, hash_key):
    o = k.clean_outcome(gate)
    model = o[report_key]
    assert hash_key in model
    recomputed = rt._core_hash({**model, hash_key: "ZZZ"}, hash_key)
    assert recomputed == model[hash_key]


def test_canonical_hash_is_key_order_independent():
    a = {"alpha": 1, "beta": [1, 2, 3], "gamma": {"x": 1, "y": 2}}
    b = {"gamma": {"y": 2, "x": 1}, "beta": [1, 2, 3], "alpha": 1}
    assert rt._sha(a) == rt._sha(b)


def test_operation_sequence_hash_no_wall_clock(gate):
    # Re-preparing the same evidence yields identical operation-sequence hash.
    b5, b5r, snap = k.setup(gate)
    o1 = k.prepare(gate, b5, b5r, snap, runtime_request_id="rtZ",
                   created_at="T1")
    o2 = k.prepare(gate, b5, b5r, snap, runtime_request_id="rtZ",
                   created_at="T2")
    assert o1["runtime_operation_ledger"]["operation_sequence_hash"] == \
        o2["runtime_operation_ledger"]["operation_sequence_hash"]
    assert o1["safe_output_hash"] == o2["safe_output_hash"]

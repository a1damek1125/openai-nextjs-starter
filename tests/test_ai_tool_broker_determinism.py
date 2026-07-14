"""TOOL-B5 null broker: deterministic, actor/time-independent hashing."""
from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k


def test_same_request_same_evidence_different_actor_time_same_decision_hash(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o1 = k.prepare(gate, d, pobj, head, quality, contract, cert,
                   broker_request_id="brdet", actor_id="a1", created_at="T1")
    o2 = k.prepare(gate, d, pobj, head, quality, contract, cert,
                   broker_request_id="brdet", actor_id="a2", created_at="T2")
    assert o1["broker_decision_hash"] == o2["broker_decision_hash"]


def test_decision_hash_excludes_actor_and_time_and_state(gate):
    o = k.clean_outcome(gate, broker_request_id="brdet2", actor_id="zz",
                        created_at="TZ")
    recomputed = b._core_hash(o, "broker_decision_hash", "broker_request_id",
                              "decided_by_actor_id", "decided_by_actor_type",
                              "broker_state_hash")
    assert o["broker_decision_hash"] == recomputed
    # Volatile actor/time fields differ but hash is stable (covered above).
    assert o["decided_by_actor_id"] == "zz"
    assert o["created_at"] == "TZ"


def test_state_hash_binds_status_and_decision_hash(gate):
    o = k.clean_outcome(gate, broker_request_id="brdet3")
    expected = b._sha({
        "broker_request_id": o["broker_request_id"],
        "broker_decision_hash": o["broker_decision_hash"],
        "broker_status": o["broker_status"],
        "dominant_signal": o["dominant_signal"],
        "broker_request_hash": o["broker_request_hash"]})
    assert o["broker_state_hash"] == expected


def test_state_hash_changes_with_decision_hash(gate):
    o = k.clean_outcome(gate, broker_request_id="brdet4")
    mutated = b._sha({
        "broker_request_id": o["broker_request_id"],
        "broker_decision_hash": "deadbeef",
        "broker_status": o["broker_status"],
        "dominant_signal": o["dominant_signal"],
        "broker_request_hash": o["broker_request_hash"]})
    assert o["broker_state_hash"] != mutated


def test_safety_lattice_submodel_hash_excludes_itself(gate):
    o = k.clean_outcome(gate, broker_request_id="brdet5")
    lat = o["broker_safety_lattice"]
    assert lat["broker_safety_lattice_hash"] == b._core_hash(
        lat, "broker_safety_lattice_hash")


def test_fault_harness_submodel_hash_excludes_itself(gate):
    o = k.clean_outcome(gate, broker_request_id="brdet6")
    harness = o["fault_injection_harness"]
    assert harness["fault_injection_harness_hash"] == b._core_hash(
        harness, "fault_injection_harness_hash")


def test_multiple_submodel_hashes_exclude_themselves(gate):
    o = k.clean_outcome(gate, broker_request_id="brdet7")
    pairs = [
        ("four_plane_model", "four_plane_broker_integrity_hash"),
        ("plane_non_interference", "plane_non_interference_hash"),
        ("null_effector", "null_effector_hash"),
        ("broker_non_execution_proof", "broker_non_execution_hash"),
        ("multi_request_safety_ledger", "multi_request_safety_ledger_hash"),
    ]
    for report_key, hash_key in pairs:
        report = o[report_key]
        assert report[hash_key] == b._core_hash(report, hash_key)


def test_canonical_json_key_order_independence(gate):
    a = {"z": 1, "a": {"n": 2, "m": 3}, "k": [1, 2, 3]}
    c = {"k": [1, 2, 3], "a": {"m": 3, "n": 2}, "z": 1}
    assert b._sha(a) == b._sha(c)
    assert b.canonical_json(a) == b.canonical_json(c)

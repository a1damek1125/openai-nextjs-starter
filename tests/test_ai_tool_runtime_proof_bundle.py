"""TOOL-B6 read-path runtime: proof bundle + conformance vector."""
from finalis.ai_employee.tool_runtime import _core_hash
from tests import _b6_kernel as k

V5_HASHES = [
    "query_plan_normal_form_hash", "read_output_provenance_map_hash",
    "output_provenance_bisimulation_hash",
    "semantic_non_interference_matrix_hash", "synthetic_canary_harness_hash",
    "canary_non_leakage_proof_hash", "information_budget_envelope_hash",
    "information_usage_proof_hash", "read_amplification_guard_hash",
    "side_channel_budget_seal_hash", "output_provenance_certificate_hash",
]
V4_HASHES = [
    "semantic_read_firewall_hash", "read_set_ledger_hash",
    "read_set_attestation_capsule_hash", "temporal_snapshot_isolation_hash",
    "determinism_entropy_seal_hash", "deterministic_replay_twin_hash",
    "data_diode_output_gate_hash", "output_non_exfiltration_gate_hash",
    "runtime_resource_usage_proof_hash",
    "runtime_fault_injection_harness_hash", "runtime_release_gate_hash",
]


def test_bundle_has_all_v5_component_hashes(gate):
    o = k.clean_outcome(gate)
    ch = o["runtime_proof_bundle"]["component_hashes"]
    for h in V5_HASHES:
        assert h in ch, h


def test_bundle_has_all_v4_component_hashes(gate):
    o = k.clean_outcome(gate)
    ch = o["runtime_proof_bundle"]["component_hashes"]
    for h in V4_HASHES:
        assert h in ch, h


def test_bundle_hash_excludes_itself(gate):
    o = k.clean_outcome(gate)
    ch = o["runtime_proof_bundle"]["component_hashes"]
    assert "runtime_proof_bundle_hash" not in ch


def test_bundle_hash_recomputes(gate):
    pb = k.clean_outcome(gate)["runtime_proof_bundle"]
    recomputed = _core_hash(pb, "runtime_proof_bundle_hash")
    assert recomputed == pb["runtime_proof_bundle_hash"]


def test_bundle_hash_deterministic_across_actor(gate):
    b5, b5r, snap = k.setup(gate)
    o1 = k.prepare(gate, b5, b5r, snap, actor_id="alice", created_at="T1")
    o2 = k.prepare(gate, b5, b5r, snap, actor_id="bob", created_at="T2")
    assert o1["runtime_proof_bundle"]["runtime_proof_bundle_hash"] == \
        o2["runtime_proof_bundle"]["runtime_proof_bundle_hash"]


def test_conformance_vector_all_dimensions_true(gate):
    cv = k.clean_outcome(gate)["runtime_conformance_vector"]
    assert cv["conformant"] is True
    assert all(cv["dimensions"].values())


def test_proof_bundle_and_conformance_endpoints(gate):
    rid, _ = gate.prepared_runtime()
    pb = gate.rt(rid, "/proof-bundle")
    assert pb.status_code == 200
    assert pb.json()["runtime_proof_bundle"]["runtime_proof_bundle_hash"]
    cv = gate.rt(rid, "/conformance-vector")
    assert cv.status_code == 200
    assert cv.json()["runtime_conformance_vector"]["conformant"] is True

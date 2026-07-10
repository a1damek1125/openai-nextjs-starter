"""TOOL-B8 v5: v5 proof extension — binds all ten v5 component hashes, is itself
carried into the main proof bundle, and is evidence only (never authority)."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k

# extension hash field -> source report key.
_V5_COMPONENTS = {
    "assurance_envelope_hash": "assurance_envelope",
    "evidence_closure_net_hash": "evidence_closure_net",
    "non_delegable_artifact_seal_hash": "non_delegable_artifact_seal",
    "b9_negative_capability_hash": "b9_negative_capability",
    "cross_artifact_consistency_hash": "cross_artifact_consistency",
    "route_topology_diff_hash": "route_topology_diff",
    "trace_completeness_witness_hash": "trace_completeness_witness",
    "proof_obligation_matrix_hash": "proof_obligation_matrix",
    "production_claim_scanner_hash": "production_claim_scanner",
    "final_ci_gate_hash": "final_ci_gate",
}


def test_extension_exists(gate):
    ext = k.clean_outcome(gate)["b8_v5_proof_extension"]
    assert ext["b8_v5_proof_extension_id"].startswith("v5x-")


def test_extension_carries_all_ten_component_hashes(gate):
    o = k.clean_outcome(gate)
    ext = o["b8_v5_proof_extension"]
    assert len(_V5_COMPONENTS) == 10
    for hash_field, report_key in _V5_COMPONENTS.items():
        assert ext[hash_field], hash_field
        assert ext[hash_field] == o[report_key][hash_field], hash_field


def test_extension_hash_in_proof_bundle(gate):
    o = k.clean_outcome(gate)
    ext = o["b8_v5_proof_extension"]
    pb = o["commit_simulation_proof_bundle"]
    assert pb["b8_v5_proof_extension_hash"] == ext["b8_v5_proof_extension_hash"]


def test_proof_bundle_component_hashes_excludes_self(gate):
    pb = k.clean_outcome(gate)["commit_simulation_proof_bundle"]
    assert "commit_simulation_proof_bundle_hash" not in pb["component_hashes"]


def test_proof_bundle_component_hashes_includes_extension(gate):
    pb = k.clean_outcome(gate)["commit_simulation_proof_bundle"]
    assert "b8_v5_proof_extension_hash" in pb["component_hashes"]


def test_v5_component_change_changes_extension_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["b8_v5_proof_extension"][
        "b8_v5_proof_extension_hash"]
    broken = k.prepare(gate, b7, force_unclosed_claims=["NO_COMMIT_THEOREM"])[
        "b8_v5_proof_extension"]["b8_v5_proof_extension_hash"]
    assert clean != broken


def test_v5_component_change_propagates_to_bundle(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_proof_bundle"][
        "b8_v5_proof_extension_hash"]
    broken = k.prepare(gate, b7, force_unclosed_claims=["NO_COMMIT_THEOREM"])[
        "commit_simulation_proof_bundle"]["b8_v5_proof_extension_hash"]
    assert clean != broken


def test_extension_hash_recomputes(gate):
    ext = k.clean_outcome(gate)["b8_v5_proof_extension"]
    assert _core_hash(ext, "b8_v5_proof_extension_hash") == \
        ext["b8_v5_proof_extension_hash"]


def test_extension_hash_deterministic_across_actor(gate):
    b7 = k.b7_outcome(gate)
    a = k.prepare(gate, b7, actor_id="alice")["b8_v5_proof_extension"]
    b = k.prepare(gate, b7, actor_id="bob", actor_type="ai_employee")[
        "b8_v5_proof_extension"]
    assert a["b8_v5_proof_extension_hash"] == b["b8_v5_proof_extension_hash"]


def test_extension_endpoint_returns_extension(gate):
    sid, o = gate.prepared_commit_simulation()
    ext = gate.cs(sid, "/v5-proof-extension").json()["b8_v5_proof_extension"]
    assert ext["b8_v5_proof_extension_hash"] == \
        o["commit_simulation_proof_bundle"]["b8_v5_proof_extension_hash"]

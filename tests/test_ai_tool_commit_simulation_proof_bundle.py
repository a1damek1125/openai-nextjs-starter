"""TOOL-B8: proof bundle + conformance vector. The bundle collects one hash per
component (v5 assurance layers AND the v1-v4 base + harness + release gate),
never self-references, and can NEVER override a blocker or authorize B9. The
conformance vector is fully conformant only on the clean path."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k

_V5_HASHES = [
    "assurance_envelope_hash", "evidence_closure_net_hash",
    "non_delegable_artifact_seal_hash", "b9_negative_capability_hash",
    "cross_artifact_consistency_hash", "route_topology_diff_hash",
    "trace_completeness_witness_hash", "proof_obligation_matrix_hash",
    "production_claim_scanner_hash", "final_ci_gate_hash",
]
_BASE_HASHES = [
    "b7_consumption_gate_hash", "shadow_dry_run_hash", "no_commit_theorem_hash",
    "b9_firewall_hash", "non_execution_certificate_hash",
    "commit_sim_fault_injection_harness_hash", "commit_sim_release_gate_hash",
]


def _pb(o):
    return o["commit_simulation_proof_bundle"]


def test_bundle_contains_all_v5_hashes(gate):
    ch = _pb(k.clean_outcome(gate))["component_hashes"]
    for h in _V5_HASHES:
        assert ch.get(h), h


def test_bundle_contains_base_hashes(gate):
    ch = _pb(k.clean_outcome(gate))["component_hashes"]
    for h in _BASE_HASHES:
        assert ch.get(h), h


def test_bundle_excludes_self_hash(gate):
    pb = _pb(k.clean_outcome(gate))
    assert "commit_simulation_proof_bundle_hash" not in pb["component_hashes"]
    assert pb["component_count"] == len(pb["component_hashes"])


def test_bundle_cannot_override_or_authorize(gate):
    pb = _pb(k.clean_outcome(gate))
    assert pb["proof_bundle_overrides_blocker"] is False
    assert pb["authorizes_b9"] is False


def test_bundle_hash_recomputes(gate):
    pb = _pb(k.clean_outcome(gate))
    assert pb["commit_simulation_proof_bundle_hash"] == _core_hash(
        pb, "commit_simulation_proof_bundle_hash")


def test_bundle_hash_deterministic_across_actor(gate):
    b7 = k.b7_outcome(gate)
    a = _pb(k.prepare(gate, b7, actor_id="alice"))
    b = _pb(k.prepare(gate, b7, actor_id="bob", actor_type="ai_employee"))
    assert a["commit_simulation_proof_bundle_hash"] == \
        b["commit_simulation_proof_bundle_hash"]


def test_conformance_vector_conformant_on_clean(gate):
    cv = k.clean_outcome(gate)["commit_sim_conformance_vector"]
    assert cv["conformant"] is True
    assert all(cv["dimensions"].values())


def test_blocked_outcome_bundle_never_overrides(gate):
    # A poisoned production claim quarantines the outcome; the proof bundle
    # still refuses to override the blocker or authorize B9.
    o = k.clean_outcome(gate, extra_claims={"production_ready": True})
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"
    pb = _pb(o)
    assert pb["proof_bundle_overrides_blocker"] is False
    assert pb["authorizes_b9"] is False
    assert pb["resolved_status"] == o["commit_simulation_status"]


def test_blocked_conformance_not_conformant(gate):
    cv = k.clean_outcome(gate, extra_claims={"production_ready": True})[
        "commit_sim_conformance_vector"]
    assert cv["conformant"] is False


def test_api_proof_bundle_subfield(gate):
    sid, _ = gate.prepared_commit_simulation()
    pb = gate.cs(sid, "/proof-bundle").json()["commit_simulation_proof_bundle"]
    assert "commit_simulation_proof_bundle_hash" not in pb["component_hashes"]
    assert pb["authorizes_b9"] is False

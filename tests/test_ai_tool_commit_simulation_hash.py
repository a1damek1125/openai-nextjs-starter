"""TOOL-B8: hashing — every sub-report hash recomputes deterministically, the
commit-simulation decision hash is stable across actor/timestamp on the same B7
but changes when a blocker is introduced, the state hash is present, and the
proof bundle / v5 extension participate without self-referencing."""
import pytest

from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


# report_key -> extra exclude args for _core_hash recompute
_SIGNAL_REPORTS = [
    "b7_consumption_gate", "state_witness_revalidation", "shadow_dry_run",
    "effect_simulation", "rollback_fence", "differential_replay",
    "metamorphic_oracle", "compliance_predicate", "no_commit_theorem",
    "b9_firewall", "b9_revalidation_contract", "evidence_closure_net",
    "non_delegable_artifact_seal", "b9_negative_capability",
    "route_topology_diff", "trace_completeness_witness",
    "proof_obligation_matrix", "production_claim_scanner", "final_ci_gate",
    "cross_artifact_consistency", "safety_case",
    "commit_sim_release_gate_report",
]


def _hash_key(report_key):
    if report_key == "commit_sim_release_gate_report":
        return "commit_sim_release_gate_hash"
    return report_key + "_hash"


@pytest.mark.parametrize("report_key", _SIGNAL_REPORTS)
def test_signal_report_hash_recomputes(gate, report_key):
    o = k.clean_outcome(gate)
    rep = o[report_key]
    hk = _hash_key(report_key)
    assert rep[hk] == _core_hash(rep, hk, "signal")


def test_non_execution_certificate_hash_uses_signals_detected(gate):
    rep = k.clean_outcome(gate)["non_execution_certificate"]
    assert rep["non_execution_certificate_hash"] == _core_hash(
        rep, "non_execution_certificate_hash", "signals_detected")


def test_assurance_envelope_hash_uses_dominant_reason_code(gate):
    e = k.clean_outcome(gate)["assurance_envelope"]
    assert e["assurance_envelope_hash"] == _core_hash(
        e, "assurance_envelope_hash", "dominant_reason_code")


def test_no_signal_reports_hash_recompute(gate):
    o = k.clean_outcome(gate)
    for key, hk in [
            ("b8_v5_proof_extension", "b8_v5_proof_extension_hash"),
            ("commit_simulation_proof_bundle",
             "commit_simulation_proof_bundle_hash"),
            ("commit_sim_fault_injection_harness",
             "commit_sim_fault_injection_harness_hash"),
            ("commit_sim_conformance_vector",
             "commit_sim_conformance_vector_hash")]:
        rep = o[key]
        assert rep[hk] == _core_hash(rep, hk), key


def test_decision_hash_stable_across_actor_and_timestamp(gate):
    b7 = k.b7_outcome(gate)
    a = k.prepare(gate, b7, actor_id="alice", actor_type="human")
    b = k.prepare(gate, b7, actor_id="bob", actor_type="ai_employee")
    assert a["commit_simulation_decision_hash"] == \
        b["commit_simulation_decision_hash"]


def test_state_hash_present_and_distinct_from_decision(gate):
    o = k.clean_outcome(gate)
    assert o["commit_simulation_state_hash"]
    assert o["commit_simulation_decision_hash"]
    # state hash is a fresh sha binding the decision hash; distinct value.
    assert o["commit_simulation_state_hash"] != \
        o["commit_simulation_decision_hash"]


def test_blocker_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    poisoned = k.prepare(gate, b7, extra_claims={"production_ready": True})[
        "commit_simulation_decision_hash"]
    assert clean != poisoned


def test_proof_bundle_component_hashes_exclude_self(gate):
    pb = k.clean_outcome(gate)["commit_simulation_proof_bundle"]
    assert "commit_simulation_proof_bundle_hash" not in pb["component_hashes"]
    assert pb["commit_simulation_proof_bundle_hash"]


def test_v5_extension_participates_in_bundle(gate):
    o = k.clean_outcome(gate)
    ext = o["b8_v5_proof_extension"]
    pb = o["commit_simulation_proof_bundle"]
    assert pb["b8_v5_proof_extension_hash"] == ext["b8_v5_proof_extension_hash"]
    assert pb["component_hashes"]["b8_v5_proof_extension_hash"] == \
        ext["b8_v5_proof_extension_hash"]


def test_assurance_envelope_hash_in_component_hashes(gate):
    o = k.clean_outcome(gate)
    e = o["assurance_envelope"]
    pb = o["commit_simulation_proof_bundle"]
    assert pb["component_hashes"]["assurance_envelope_hash"] == \
        e["assurance_envelope_hash"]

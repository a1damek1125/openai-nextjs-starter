"""TOOL-B5 proof bundle + conformance vector + bypass sentinel: the aggregate
proof-carrying evidence for a NULL broker outcome."""
import json

from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k
from tests.conftest import OWNER


# The 8 v5 conservation/safety hashes.
V5_HASHES = {
    "broker_safety_lattice_hash",
    "multi_request_safety_ledger_hash",
    "cross_request_effect_conservation_hash",
    "cumulative_risk_conservation_hash",
    "null_output_non_exfiltration_hash",
    "safe_output_projection_hash",
    "fault_injection_harness_hash",
    "broker_release_gate_hash",
}
# The four-plane / corridor / token / adapter / surface / seal / chain /
# side-effect / non-execution hashes.
CORE_HASHES = {
    "four_plane_broker_integrity_hash",
    "credential_free_corridor_hash",
    "token_non_derivation_hash",
    "adapter_manifest_freeze_hash",
    "runtime_surface_diff_hash",
    "capability_identity_seal_hash",
    "certificate_chain_closure_hash",
    "side_effect_zero_hash",
    "broker_non_execution_hash",
}


def test_proof_bundle_includes_all_component_hashes(gate):
    o = k.clean_outcome(gate)
    comp = o["broker_proof_bundle"]["component_hashes"]
    assert V5_HASHES <= set(comp), V5_HASHES - set(comp)
    assert CORE_HASHES <= set(comp), CORE_HASHES - set(comp)
    # Every component hash is a non-empty digest.
    assert all(isinstance(v, str) and v for v in comp.values())


def test_proof_bundle_hash_excludes_itself_and_is_deterministic(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o = k.prepare(gate, d, pobj, head, quality, contract, cert)
    bundle = o["broker_proof_bundle"]
    stored = bundle["broker_proof_bundle_hash"]
    # Recomputing over the bundle (excluding the hash field) reproduces it,
    # proving the hash excludes itself.
    recomputed = b._core_hash(bundle, "broker_proof_bundle_hash")
    assert recomputed == stored
    # Same request id + same evidence, different actor/created_at -> identical
    # bundle hash (deterministic; volatile fields excluded).
    o2 = k.prepare(gate, d, pobj, head, quality, contract, cert,
                   actor_id="someone-else", created_at="OTHER")
    assert o2["broker_proof_bundle"]["broker_proof_bundle_hash"] == stored


def test_conformance_vector_all_dimensions_true(gate):
    o = k.clean_outcome(gate)
    cv = o["broker_conformance_vector"]
    assert cv["conformant"] is True
    assert cv["dimensions"]
    assert all(v is True for v in cv["dimensions"].values())


def test_bypass_sentinel_clean_has_no_bypass(gate):
    o = k.clean_outcome(gate)
    bs = o["broker_bypass_sentinel"]
    assert bs["bypass_detected"] is False
    assert bs["bypass_findings"] == []


def test_bypass_sentinel_detects_governance_receipt_as_authority(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    # Craft a B4 decision copy whose governance receipt falsely grants execution.
    d2 = json.loads(json.dumps(d))
    d2["governance_receipt"]["grants_execution"] = True
    o = k.prepare(gate, d2, pobj, head, quality, contract, cert)
    bs = o["broker_bypass_sentinel"]
    assert bs["bypass_detected"] is True
    assert bs["signal"] == "EXECUTION_ATTEMPT"
    assert bs["bypass_findings"]


def test_proof_endpoints_serve_bundle_conformance_and_sentinel(gate):
    rid, _ = gate.prepared_broker()
    pb = gate.br(rid, "/proof-bundle").json()
    assert "broker_proof_bundle" in pb
    assert pb["broker_proof_bundle"]["broker_proof_bundle_hash"]
    cv = gate.br(rid, "/conformance-vector").json()
    assert cv["broker_conformance_vector"]["conformant"] is True
    sn = gate.br(rid, "/bypass-sentinel").json()
    assert sn["broker_bypass_sentinel"]["bypass_detected"] is False

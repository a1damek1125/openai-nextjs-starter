"""TOOL-B7: proof bundle + conformance vector — the bundle records the decision
over every component hash; it can NEVER override a blocker."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k

_V4_HASHES = [
    "transaction_escrow_hash",
    "escrowed_commit_readiness_certificate_hash",
    "future_commit_gate_contract_hash", "commit_gate_non_existence_hash",
    "revalidation_debt_ledger_hash", "semantic_rollback_fence_hash",
    "action_replay_guard_hash", "authority_resurrection_guard_hash",
    "rollback_replay_equivalence_hash", "concurrent_draft_conflict_graph_hash",
    "transaction_conflict_oracle_hash", "state_witness_quorum_hash",
    "effect_outbox_quarantine_hash", "escrow_expiry_policy_hash",
    "escrow_tamper_evidence_hash",
    "transaction_readiness_non_execution_certificate_hash",
    "transaction_escrow_proof_extension_hash",
]
_V2_V3_HASHES = [
    "write_intent_draft_hash", "semantic_transaction_hash",
    "approval_binding_hash", "review_package_hash",
    "write_intent_fault_injection_harness_hash",
    "write_intent_release_gate_hash",
]


def test_bundle_contains_all_v4_component_hashes(gate):
    ch = k.clean_outcome(gate)["write_intent_proof_bundle"]["component_hashes"]
    for h in _V4_HASHES:
        assert h in ch, h


def test_bundle_contains_v2_v3_component_hashes(gate):
    ch = k.clean_outcome(gate)["write_intent_proof_bundle"]["component_hashes"]
    for h in _V2_V3_HASHES:
        assert h in ch, h


def test_bundle_excludes_own_hash(gate):
    ch = k.clean_outcome(gate)["write_intent_proof_bundle"]["component_hashes"]
    assert "write_intent_proof_bundle_hash" not in ch


def test_proof_bundle_does_not_override_blocker_flag(gate):
    pb = k.clean_outcome(gate)["write_intent_proof_bundle"]
    assert pb["proof_bundle_overrides_blocker"] is False


def test_component_hashes_match_reports(gate):
    o = k.clean_outcome(gate)
    ch = o["write_intent_proof_bundle"]["component_hashes"]
    assert ch["transaction_escrow_hash"] == \
        o["transaction_escrow_capsule"]["transaction_escrow_hash"]
    assert ch["write_intent_draft_hash"] == \
        o["write_intent_draft"]["write_intent_draft_hash"]
    assert o["write_intent_proof_bundle"][
        "transaction_escrow_proof_extension_hash"] == \
        o["transaction_escrow_proof_extension"][
            "transaction_escrow_proof_extension_hash"]


def test_conformance_vector_conformant_on_clean(gate):
    cv = k.clean_outcome(gate)["write_intent_conformance_vector"]
    assert cv["conformant"] is True
    assert all(cv["dimensions"].values())


def test_bundle_hash_recomputes(gate):
    pb = k.clean_outcome(gate)["write_intent_proof_bundle"]
    assert _core_hash(pb, "write_intent_proof_bundle_hash") == \
        pb["write_intent_proof_bundle_hash"]


def test_bundle_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["write_intent_proof_bundle"]["write_intent_proof_bundle_hash"] == \
        o2["write_intent_proof_bundle"]["write_intent_proof_bundle_hash"]


def test_conformance_vector_hash_recomputes(gate):
    cv = k.clean_outcome(gate)["write_intent_conformance_vector"]
    assert _core_hash(cv, "write_intent_conformance_vector_hash") == \
        cv["write_intent_conformance_vector_hash"]


def test_proof_bundle_does_not_override_a_real_blocker(gate):
    # A blocked outcome still records overrides_blocker=False and a non-terminal
    # status: the bundle can never rescue a blocked decision.
    o = k.prepare(gate, k.b6_outcome(gate),
                  execution_markers={"commit_executable_now": True})
    assert o["write_intent_proof_bundle"]["proof_bundle_overrides_blocker"] \
        is False
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["write_intent_proof_bundle"]["resolved_status"] == \
        o["write_intent_status"]


def test_proof_bundle_endpoint(gate):
    wid, _ = gate.prepared_write_intent()
    pb = gate.wi(wid, "/proof-bundle").json()["write_intent_proof_bundle"]
    assert pb["proof_bundle_overrides_blocker"] is False
    assert "write_intent_proof_bundle_hash" not in pb["component_hashes"]

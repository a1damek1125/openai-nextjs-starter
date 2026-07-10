"""TOOL-B7 v4: Transaction escrow proof-bundle extension — binds every v4
component hash and itself participates in the main write-intent proof bundle.
Changing any bound component changes the extension hash."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k

V4_COMPONENT_HASHES = [
    "transaction_escrow_hash",
    "escrowed_commit_readiness_certificate_hash",
    "future_commit_gate_contract_hash",
    "commit_gate_non_existence_hash",
    "revalidation_debt_ledger_hash",
    "semantic_rollback_fence_hash",
    "action_replay_guard_hash",
    "authority_resurrection_guard_hash",
    "rollback_replay_equivalence_hash",
    "concurrent_draft_conflict_graph_hash",
    "transaction_conflict_oracle_hash",
    "state_witness_quorum_hash",
    "effect_outbox_quarantine_hash",
    "escrow_expiry_policy_hash",
    "escrow_tamper_evidence_hash",
    "transaction_readiness_non_execution_certificate_hash",
]


def test_extension_exists(gate):
    ext = k.clean_outcome(gate)["transaction_escrow_proof_extension"]
    assert ext["transaction_escrow_proof_extension_id"].startswith("tep-")
    assert ext["transaction_escrow_proof_extension_hash"]


def test_extension_carries_all_v4_component_hashes(gate):
    ext = k.clean_outcome(gate)["transaction_escrow_proof_extension"]
    for hk in V4_COMPONENT_HASHES:
        assert ext.get(hk), hk


def test_extension_component_hashes_match_source_reports(gate):
    o = k.clean_outcome(gate)
    ext = o["transaction_escrow_proof_extension"]
    assert ext["transaction_escrow_hash"] == \
        o["transaction_escrow_capsule"]["transaction_escrow_hash"]
    assert ext["escrowed_commit_readiness_certificate_hash"] == \
        o["escrowed_commit_readiness_certificate"][
            "escrowed_commit_readiness_certificate_hash"]
    assert ext["escrow_tamper_evidence_hash"] == \
        o["escrow_tamper_evidence"]["escrow_tamper_evidence_hash"]


def test_extension_hash_participates_in_proof_bundle(gate):
    o = k.clean_outcome(gate)
    ext = o["transaction_escrow_proof_extension"]
    pb = o["write_intent_proof_bundle"]
    assert pb["transaction_escrow_proof_extension_hash"] == \
        ext["transaction_escrow_proof_extension_hash"]


def test_extension_hash_in_component_hashes(gate):
    o = k.clean_outcome(gate)
    pb = o["write_intent_proof_bundle"]
    assert pb["component_hashes"]["transaction_escrow_proof_extension_hash"] \
        == o["transaction_escrow_proof_extension"][
            "transaction_escrow_proof_extension_hash"]


def test_component_hashes_excludes_proof_bundle_hash(gate):
    pb = k.clean_outcome(gate)["write_intent_proof_bundle"]
    assert "write_intent_proof_bundle_hash" not in pb["component_hashes"]


def test_escrow_tamper_changes_extension_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    tampered = k.prepare(gate, b6, observed_escrow_hash="deadbeef")
    assert clean["transaction_escrow_proof_extension"][
        "transaction_escrow_proof_extension_hash"] != \
        tampered["transaction_escrow_proof_extension"][
            "transaction_escrow_proof_extension_hash"]
    # Tamper is recorded in the escrow_tamper_evidence component, which is
    # bound into the extension (the immutable capsule hash itself is unchanged).
    assert clean["transaction_escrow_proof_extension"][
        "escrow_tamper_evidence_hash"] != \
        tampered["transaction_escrow_proof_extension"][
            "escrow_tamper_evidence_hash"]


def test_extension_hash_excludes_itself_and_recomputes(gate):
    ext = k.clean_outcome(gate)["transaction_escrow_proof_extension"]
    recomputed = _core_hash(ext, "transaction_escrow_proof_extension_hash")
    assert recomputed == ext["transaction_escrow_proof_extension_hash"]


def test_extension_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["transaction_escrow_proof_extension"][
        "transaction_escrow_proof_extension_hash"] == \
        o2["transaction_escrow_proof_extension"][
            "transaction_escrow_proof_extension_hash"]


def test_extension_endpoint_returns_extension(gate):
    wid, _ = gate.prepared_write_intent()
    ext = gate.wi(wid, "/transaction-escrow-proof-extension").json()[
        "transaction_escrow_proof_extension"]
    for hk in V4_COMPONENT_HASHES:
        assert ext.get(hk), hk

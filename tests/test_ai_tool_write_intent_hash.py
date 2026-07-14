"""TOOL-B7 write-intent hashing rules: decision-hash identity, sub-report
recompute, tamper sensitivity and proof-bundle composition."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_decision_hash_identical_across_actor_id(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["write_intent_decision_hash"] == o2["write_intent_decision_hash"]


def test_decision_hash_identical_across_actor_type(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_type="human")
    o2 = k.prepare(gate, b6, actor_type="service")
    assert o1["write_intent_decision_hash"] == o2["write_intent_decision_hash"]


def test_decision_hash_identical_across_created_at(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, created_at="T1")
    o2 = k.prepare(gate, b6, created_at="T2")
    assert o1["write_intent_decision_hash"] == o2["write_intent_decision_hash"]


def test_state_hash_present(gate):
    o = k.clean_outcome(gate)
    assert o["write_intent_state_hash"]
    assert isinstance(o["write_intent_state_hash"], str)


def test_proof_bundle_component_hashes_exclude_bundle_hash(gate):
    pb = k.clean_outcome(gate)["write_intent_proof_bundle"]
    assert "write_intent_proof_bundle_hash" not in pb["component_hashes"]
    assert pb["component_count"] == len(pb["component_hashes"])


_RECOMPUTE_CASES = [
    ("write_intent_draft", "write_intent_draft_hash", ("signal",)),
    ("semantic_transaction", "semantic_transaction_hash", ("signal",)),
    ("transaction_boundary", "transaction_boundary_hash", ()),
    ("shadow_state_delta_graph", "shadow_state_delta_graph_hash", ("signal",)),
    ("state_delta", "state_delta_hash", ()),
    ("review_package", "review_package_hash", ()),
    ("approval_requirement", "approval_requirement_hash", ()),
    ("approval_binding", "approval_binding_hash", ("signal",)),
    ("meaningful_judgment", "meaningful_judgment_hash", ("signal",)),
    ("transaction_escrow_capsule", "transaction_escrow_hash", ("signal",)),
    ("revalidation_debt_ledger", "revalidation_debt_ledger_hash", ("signal",)),
    ("state_witness_quorum", "state_witness_quorum_hash", ("signal",)),
    ("commit_non_execution", "commit_non_execution_hash", ("signals_detected",)),
    ("escrowed_commit_readiness_certificate",
     "escrowed_commit_readiness_certificate_hash", ()),
    ("transaction_escrow_proof_extension",
     "transaction_escrow_proof_extension_hash", ()),
]


def test_every_major_sub_report_hash_recomputes(gate):
    o = k.clean_outcome(gate)
    for rep_key, hash_key, extra in _RECOMPUTE_CASES:
        rep = o[rep_key]
        assert _core_hash(rep, hash_key, *extra) == rep[hash_key], rep_key


def test_tamper_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    tampered = k.prepare(gate, b6, observed_escrow_hash="deadbeef")
    assert clean["write_intent_decision_hash"] != \
        tampered["write_intent_decision_hash"]


def test_escrow_proof_extension_hash_participates_in_bundle(gate):
    o = k.clean_outcome(gate)
    pb = o["write_intent_proof_bundle"]
    ext = o["transaction_escrow_proof_extension"]
    assert pb["transaction_escrow_proof_extension_hash"] == \
        ext["transaction_escrow_proof_extension_hash"]
    assert pb["component_hashes"]["transaction_escrow_proof_extension_hash"] == \
        ext["transaction_escrow_proof_extension_hash"]


def test_bundle_component_hash_matches_source_report(gate):
    o = k.clean_outcome(gate)
    ch = o["write_intent_proof_bundle"]["component_hashes"]
    assert ch["transaction_escrow_hash"] == \
        o["transaction_escrow_capsule"]["transaction_escrow_hash"]
    assert ch["escrowed_commit_readiness_certificate_hash"] == \
        o["escrowed_commit_readiness_certificate"][
            "escrowed_commit_readiness_certificate_hash"]


def test_state_hash_binds_decision_and_proof_bundle(gate):
    from finalis.ai_employee.tool_contracts import _sha
    o = k.clean_outcome(gate)
    expected = _sha({
        "write_intent_id": o["write_intent_id"],
        "write_intent_decision_hash": o["write_intent_decision_hash"],
        "write_intent_status": o["write_intent_status"],
        "dominant_signal": o["dominant_signal"],
        "write_intent_request_hash": o["write_intent_request_hash"],
        "proof_bundle_hash": o["write_intent_proof_bundle"][
            "write_intent_proof_bundle_hash"]})
    assert o["write_intent_state_hash"] == expected

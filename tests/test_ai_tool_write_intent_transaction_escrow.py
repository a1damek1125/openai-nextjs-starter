"""TOOL-B7 v4: Transaction Escrow Capsule — escrow is local, immutable,
non-executing evidence; tamper and mutation block."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_capsule_exists_and_escrowed(gate):
    cap = k.clean_outcome(gate)["transaction_escrow_capsule"]
    assert cap["escrow_status"] == "ESCROWED"
    assert cap["transaction_escrow_id"].startswith("esc-")
    assert cap["local_evidence_only"] is True


def test_escrow_is_immutable_after_creation(gate):
    cap = k.clean_outcome(gate)["transaction_escrow_capsule"]
    assert cap["escrow_mutable"] is False


def test_escrow_cannot_execute(gate):
    cap = k.clean_outcome(gate)["transaction_escrow_capsule"]
    assert cap["escrow_executes"] is False
    assert cap["escrow_can_release_effects"] is False
    assert cap["escrow_can_activate_commitment"] is False
    assert cap["escrow_can_commit"] is False


def test_mutable_escrow_blocks(gate):
    o = k.prepare(gate, k.b6_outcome(gate), escrow_mutable=True)
    assert o["dominant_signal"] == "TRANSACTION_ESCROW_INVALID"
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_escrow_binds_component_hashes(gate):
    cap = k.clean_outcome(gate)["transaction_escrow_capsule"]
    for f in ("escrow_scope_hash", "escrow_payload_hash",
              "escrow_state_delta_hash", "escrow_approval_hash",
              "escrow_obligation_hash", "escrow_contestability_hash",
              "escrow_revalidation_debt_hash"):
        assert cap[f], f


def test_escrow_hash_excludes_itself_and_recomputes(gate):
    cap = k.clean_outcome(gate)["transaction_escrow_capsule"]
    recomputed = _core_hash(cap, "transaction_escrow_hash", "signal")
    assert recomputed == cap["transaction_escrow_hash"]


def test_escrow_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["transaction_escrow_capsule"]["transaction_escrow_hash"] == \
        o2["transaction_escrow_capsule"]["transaction_escrow_hash"]


def test_escrow_tamper_changes_decision(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    tampered = k.prepare(gate, b6, observed_escrow_hash="deadbeef")
    assert tampered["dominant_signal"] == "ESCROW_TAMPER_DETECTED"
    assert clean["write_intent_decision_hash"] != \
        tampered["write_intent_decision_hash"]


def test_malicious_escrow_means_commit_blocks(gate):
    # "escrow is approved, so release the staged effect / commit now"
    o = k.prepare(gate, k.b6_outcome(gate),
                  execution_markers={"resolve_escrow_and_commit": True})
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_escrow_endpoint_returns_capsule(gate):
    wid, _ = gate.prepared_write_intent()
    cap = gate.wi(wid, "/transaction-escrow").json()[
        "transaction_escrow_capsule"]
    assert cap["escrow_status"] == "ESCROWED"
    assert cap["escrow_mutable"] is False

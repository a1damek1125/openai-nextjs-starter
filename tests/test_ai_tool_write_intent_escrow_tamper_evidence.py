"""TOOL-B7 v4: Escrow tamper evidence — the observed escrow hash must equal the
expected escrow hash. Any mismatch is a detected tamper that blocks and changes
the decision."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_clean_tamper_not_detected(gate):
    tv = k.clean_outcome(gate)["escrow_tamper_evidence"]
    assert tv["tamper_detected"] is False
    assert tv["tamper_status"] == "INTACT"
    assert tv["tamper_fields"] == []


def test_tamper_evidence_exists(gate):
    tv = k.clean_outcome(gate)["escrow_tamper_evidence"]
    assert tv["escrow_tamper_evidence_id"].startswith("tmp-")
    assert tv["expected_escrow_hash"] == tv["observed_escrow_hash"]


def test_clean_expected_matches_capsule_hash(gate):
    o = k.clean_outcome(gate)
    tv = o["escrow_tamper_evidence"]
    assert tv["expected_escrow_hash"] == \
        o["transaction_escrow_capsule"]["transaction_escrow_hash"]


def test_observed_mismatch_detects_tamper(gate):
    o = k.prepare(gate, k.b6_outcome(gate), observed_escrow_hash="deadbeef")
    tv = o["escrow_tamper_evidence"]
    assert tv["tamper_detected"] is True
    assert tv["tamper_status"] == "TAMPERED"
    assert tv["observed_escrow_hash"] == "deadbeef"


def test_tamper_signal_and_status(gate):
    o = k.prepare(gate, k.b6_outcome(gate), observed_escrow_hash="deadbeef")
    assert o["dominant_signal"] == "ESCROW_TAMPER_DETECTED"
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_tamper_fields_non_empty(gate):
    tv = k.prepare(gate, k.b6_outcome(gate),
                   observed_escrow_hash="deadbeef")["escrow_tamper_evidence"]
    assert tv["tamper_fields"] == ["transaction_escrow_hash"]


def test_tamper_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    tampered = k.prepare(gate, b6, observed_escrow_hash="deadbeef")
    assert clean["write_intent_decision_hash"] != \
        tampered["write_intent_decision_hash"]


def test_tamper_hash_excludes_itself_and_recomputes(gate):
    tv = k.clean_outcome(gate)["escrow_tamper_evidence"]
    recomputed = _core_hash(tv, "escrow_tamper_evidence_hash", "signal")
    assert recomputed == tv["escrow_tamper_evidence_hash"]


def test_tamper_hash_recomputes_when_tampered(gate):
    tv = k.prepare(gate, k.b6_outcome(gate),
                   observed_escrow_hash="deadbeef")["escrow_tamper_evidence"]
    recomputed = _core_hash(tv, "escrow_tamper_evidence_hash", "signal")
    assert recomputed == tv["escrow_tamper_evidence_hash"]


def test_tamper_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["escrow_tamper_evidence"]["escrow_tamper_evidence_hash"] == \
        o2["escrow_tamper_evidence"]["escrow_tamper_evidence_hash"]


def test_tamper_endpoint_returns_evidence(gate):
    wid, _ = gate.prepared_write_intent()
    tv = gate.wi(wid, "/escrow-tamper-evidence").json()[
        "escrow_tamper_evidence"]
    assert tv["tamper_detected"] is False
    assert tv["tamper_status"] == "INTACT"

"""TOOL-B7 v3: Evidence Preservation — a repair draft can NEVER destroy the
triggering evidence; destructive repair and lost evidence both block."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_clean_evidence_is_preserved(gate):
    r = k.clean_outcome(gate)["evidence_preservation"]
    assert r["preservation_status"] == "PRESERVED"
    assert r["triggering_evidence_preserved"] is True
    assert r["destructive_repair_detected"] is False
    assert r["repair_is_evidence_preserving"] is True
    assert r["signal"] is None


def test_lost_triggering_evidence_fails(gate):
    o = k.clean_outcome(gate, triggering_evidence_preserved=False)
    r = o["evidence_preservation"]
    assert r["triggering_evidence_preserved"] is False
    assert r["preservation_status"] == "VIOLATED"
    assert r["signal"] == "EVIDENCE_PRESERVATION_FAILED"
    assert o["dominant_signal"] == "EVIDENCE_PRESERVATION_FAILED"
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_destructive_repair_detected(gate):
    o = k.clean_outcome(gate, destructive_repair=True)
    r = o["evidence_preservation"]
    assert r["destructive_repair_detected"] is True
    assert r["repair_is_evidence_preserving"] is False
    assert r["signal"] == "EVIDENCE_DESTRUCTIVE_REPAIR_DETECTED"
    assert o["dominant_signal"] == "EVIDENCE_DESTRUCTIVE_REPAIR_DETECTED"


def test_repair_cannot_destroy_triggering_evidence_invariant(gate):
    # When a repair is destructive it is by definition not evidence-preserving
    # and must block the draft; it can never reach the escrow-draft outcome.
    o = k.clean_outcome(gate, destructive_repair=True)
    assert o["evidence_preservation"]["repair_is_evidence_preserving"] is False
    assert o["ready_for_future_commit_only"] is False
    assert o["commit_executable_now"] is False


def test_destructive_repair_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    blocked = k.prepare(gate, b6, destructive_repair=True)
    assert clean["write_intent_decision_hash"] != \
        blocked["write_intent_decision_hash"]


def test_lost_evidence_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    blocked = k.prepare(gate, b6, triggering_evidence_preserved=False)
    assert clean["write_intent_decision_hash"] != \
        blocked["write_intent_decision_hash"]


def test_hash_recomputes_clean(gate):
    r = k.clean_outcome(gate)["evidence_preservation"]
    assert _core_hash(r, "evidence_preservation_hash", "signal") == \
        r["evidence_preservation_hash"]


def test_hash_recomputes_when_violated(gate):
    r = k.clean_outcome(gate, destructive_repair=True)[
        "evidence_preservation"]
    assert _core_hash(r, "evidence_preservation_hash", "signal") == \
        r["evidence_preservation_hash"]


def test_endpoint_returns_preservation(gate):
    wid, _ = gate.prepared_write_intent()
    r = gate.wi(wid, "/evidence-preservation").json()[
        "evidence_preservation"]
    assert r["preservation_status"] == "PRESERVED"
    assert r["triggering_evidence_preserved"] is True
    assert r["destructive_repair_detected"] is False

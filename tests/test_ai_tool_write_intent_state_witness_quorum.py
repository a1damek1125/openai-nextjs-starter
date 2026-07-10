"""TOOL-B7 v4: State-witness quorum vector — LOW risk needs 1 SOURCE_STATE_HASH
witness; HIGH risk needs >=3 of the high-risk witness classes; stale witnesses
create revalidation debt; the quorum never executes and cannot be waived for
HIGH-risk future readiness."""
from finalis.ai_employee.tool_write_intent import (
    _core_hash, HIGH_RISK_WITNESS_CLASSES)
from tests import _b7_kernel as k


def _high_witnesses(epoch=5):
    return [{"witness_class": c, "witness_hash": "h", "epoch": epoch}
            for c in sorted(HIGH_RISK_WITNESS_CLASSES)]


def test_quorum_exists_and_clean_low_is_satisfied(gate):
    q = k.clean_outcome(gate)["state_witness_quorum"]
    assert q["state_witness_quorum_id"].startswith("swq-")
    assert q["risk_tier"] == "LOW"
    assert q["required_witness_count"] == 1
    assert q["required_witness_classes"] == ["SOURCE_STATE_HASH"]
    assert q["quorum_satisfied"] is True
    assert q["quorum_status"] == "SATISFIED"


def test_quorum_never_executes(gate):
    q = k.clean_outcome(gate)["state_witness_quorum"]
    assert q["quorum_executes"] is False


def test_observed_witness_hashes_recorded(gate):
    q = k.clean_outcome(gate)["state_witness_quorum"]
    assert q["observed_witnesses"] == ["SOURCE_STATE_HASH"]
    assert q["observed_witness_hashes"] == ["sw-h"]


def test_high_risk_empty_witnesses_missing(gate):
    o = k.prepare(gate, k.b6_outcome(gate), risk_tier="HIGH",
                  state_witnesses=[])
    q = o["state_witness_quorum"]
    assert q["risk_tier"] == "HIGH"
    assert q["required_witness_count"] >= 3
    assert set(q["required_witness_classes"]) == HIGH_RISK_WITNESS_CLASSES
    assert q["quorum_satisfied"] is False
    assert "STATE_WITNESS_QUORUM_MISSING" in o["all_signals"]


def test_high_risk_full_witness_set_satisfied(gate):
    o = k.prepare(gate, k.b6_outcome(gate), risk_tier="HIGH",
                  state_witnesses=_high_witnesses())
    q = o["state_witness_quorum"]
    assert q["quorum_satisfied"] is True
    assert q["missing_witness_classes"] == []
    assert set(q["observed_witnesses"]) == HIGH_RISK_WITNESS_CLASSES


def test_quorum_optional_framing_still_requires_quorum(gate):
    # "state witness quorum optional" framing must not waive the HIGH-risk
    # quorum.
    o = k.prepare(gate, k.b6_outcome(gate), risk_tier="HIGH",
                  intent="state witness quorum optional", state_witnesses=[])
    assert o["state_witness_quorum"]["quorum_satisfied"] is False
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_stale_witness_signals_and_does_not_pass(gate):
    # policy_epoch=9 with the default witness epoch=1 -> stale (skipped).
    o = k.prepare(gate, k.b6_outcome(gate), policy_epoch=9)
    q = o["state_witness_quorum"]
    assert "SOURCE_STATE_HASH" in q["stale_witness_classes"]
    assert q["quorum_satisfied"] is False
    assert "STATE_WITNESS_STALE" in o["all_signals"]


def test_missing_witness_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    missing = k.prepare(gate, b6, risk_tier="HIGH", state_witnesses=[])
    assert clean["write_intent_decision_hash"] != \
        missing["write_intent_decision_hash"]


def test_stale_witness_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    stale = k.prepare(gate, b6, policy_epoch=9)
    assert clean["write_intent_decision_hash"] != \
        stale["write_intent_decision_hash"]


def test_quorum_hash_excludes_itself_and_recomputes(gate):
    q = k.clean_outcome(gate)["state_witness_quorum"]
    recomputed = _core_hash(q, "state_witness_quorum_hash", "signal")
    assert recomputed == q["state_witness_quorum_hash"]


def test_endpoint_returns_quorum(gate):
    wid, _ = gate.prepared_write_intent()
    q = gate.wi(wid, "/state-witness-quorum").json()["state_witness_quorum"]
    assert q["quorum_satisfied"] is True

"""TOOL-B7 v4: Transaction conflict oracle — deterministic fail-closed verdict
over the conflict graph. Blocking -> BLOCK_FUTURE_READINESS; obligation-only
overlap -> NEEDS_REVIEW; clean -> NO_CONFLICT; verdicts are restricted to the
known ORACLE_DECISIONS set."""
from finalis.ai_employee.tool_write_intent import (
    _core_hash, ORACLE_DECISIONS, CONFLICT_CLASSES)
from tests import _b7_kernel as k


def _related(gate, **over):
    r = {"write_intent_id": "o", "tenant_id": gate.tid,
         "target_entity_id": "E-1"}
    r.update(over)
    return r


def test_oracle_exists_and_clean_no_conflict(gate):
    orc = k.clean_outcome(gate)["transaction_conflict_oracle"]
    assert orc["transaction_conflict_oracle_id"].startswith("tco-")
    assert orc["oracle_decision"] == "NO_CONFLICT"
    assert orc["oracle_decision"] in ORACLE_DECISIONS
    assert orc["dominant_conflict_reason"] is None


def test_blocking_conflict_rejected(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  related_write_intents=[_related(gate)])
    orc = o["transaction_conflict_oracle"]
    assert orc["oracle_decision"] == "BLOCK_FUTURE_READINESS"
    assert "TRANSACTION_CONFLICT_ORACLE_REJECTED" in o["all_signals"]


def test_review_conflict_needs_review(gate):
    o = k.prepare(gate, k.b6_outcome(gate), obligations=["ob1"],
                  obligation_states=[{"obligation_id": "ob1",
                                      "contained": True}],
                  related_write_intents=[_related(
                      gate, target_entity_id="E-2", obligation_ids=["ob1"])])
    orc = o["transaction_conflict_oracle"]
    assert orc["oracle_decision"] == "NEEDS_REVIEW"
    assert "TRANSACTION_CONFLICT_ORACLE_NEEDS_REVIEW" in o["all_signals"]


def test_decisions_restricted_to_known_set(gate):
    # Fail-closed design: any decision the oracle can emit is a member of the
    # known decision set. A blocking conflict yields a KNOWN conflict class.
    o = k.prepare(gate, k.b6_outcome(gate),
                  related_write_intents=[_related(gate)])
    orc = o["transaction_conflict_oracle"]
    assert orc["oracle_decision"] in ORACLE_DECISIONS
    assert orc["oracle_status"] in ORACLE_DECISIONS
    assert orc["unknown_conflict_classes"] == []
    for c in orc["conflict_classes"]:
        assert c in CONFLICT_CLASSES


def test_dominant_conflict_reason_populated_on_block(gate):
    o = k.prepare(gate, k.b6_outcome(gate),
                  related_write_intents=[_related(gate)])
    orc = o["transaction_conflict_oracle"]
    assert orc["dominant_conflict_reason"] in CONFLICT_CLASSES
    assert orc["dominant_conflict_reason"] == "SAME_TARGET_WRITE"


def test_oracle_binds_conflict_graph_hash(gate):
    o = k.clean_outcome(gate)
    orc = o["transaction_conflict_oracle"]
    g = o["concurrent_draft_conflict_graph"]
    assert orc["conflict_graph_hash"] == \
        g["concurrent_draft_conflict_graph_hash"]


def test_oracle_hash_excludes_itself_and_recomputes(gate):
    orc = k.clean_outcome(gate)["transaction_conflict_oracle"]
    recomputed = _core_hash(orc, "transaction_conflict_oracle_hash", "signal")
    assert recomputed == orc["transaction_conflict_oracle_hash"]


def test_graph_change_changes_oracle_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)["transaction_conflict_oracle"]
    blocked = k.prepare(gate, b6, related_write_intents=[_related(gate)])[
        "transaction_conflict_oracle"]
    assert clean["transaction_conflict_oracle_hash"] != \
        blocked["transaction_conflict_oracle_hash"]


def test_blocking_conflict_changes_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    clean = k.prepare(gate, b6)
    blocked = k.prepare(gate, b6, related_write_intents=[_related(gate)])
    assert clean["write_intent_decision_hash"] != \
        blocked["write_intent_decision_hash"]


def test_endpoint_returns_oracle(gate):
    wid, _ = gate.prepared_write_intent()
    orc = gate.wi(wid, "/transaction-conflict-oracle").json()[
        "transaction_conflict_oracle"]
    assert orc["oracle_decision"] == "NO_CONFLICT"

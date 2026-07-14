"""TOOL-B5 multi-request safety ledger (b.build_multi_request_ledger).

Detects a dangerous effect split into individually-"null" pieces across a set of
related broker requests. NOTE (verified by running): each related record's
sensitive effect is counted from BOTH its aggregate_effects list AND the derived
effect class, so one related EXPORT request contributes a class count of 2. The
default split_threshold is 3, so a single sensitive related request stays
NEEDS_REVIEW while >= 3 sharing a class trips SPLIT_RISK_DETECTED.
"""
from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k

ENV = {"customer_id": "", "batch_id": "", "task_id": "", "case_id": ""}


def _ledger(related, policy=None, self_effects=None):
    return b.build_multi_request_ledger(
        tenant_id="t", broker_request_id="br1", envelope=ENV,
        self_effects=self_effects or [], related_requests=related,
        policy=policy)


def test_clean_no_related_is_safe(gate):
    o = k.clean_outcome(gate)
    lg = o["multi_request_safety_ledger"]
    assert lg["ledger_status"] == "MULTI_REQUEST_SAFE"
    assert lg["split_risk_detected"] is False
    assert lg["signal"] is None


def test_clean_self_read_no_sensitive_class(gate):
    o = k.clean_outcome(gate)
    # A pure-read self tool contributes no sensitive effect units.
    assert o["multi_request_safety_ledger"]["sensitive_class_counts"] == {}


def test_split_export_blocks_end_to_end(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    rel = [{"broker_request_id": f"r{i}", "aggregate_effects": ["EXPORT"],
            "risk_score": 1} for i in range(3)]
    o = k.prepare(gate, d, pobj, head, quality, contract, cert,
                  related_requests=rel)
    lg = o["multi_request_safety_ledger"]
    assert lg["split_risk_detected"] is True
    assert lg["ledger_status"] == "SPLIT_RISK_DETECTED"
    assert lg["signal"] == "MULTI_REQUEST_SAFETY_FAILED"
    assert "EXPORT" in lg["split_risk_classes"]
    assert o["broker_status"] == "BLOCKED"
    # Split risk dominates the (also-tripped) effect-conservation failure.
    assert o["dominant_signal"] == "MULTI_REQUEST_SAFETY_FAILED"


def test_split_customer_message():
    rel = [{"broker_request_id": f"r{i}",
            "aggregate_effects": ["CUSTOMER_MESSAGE"]} for i in range(3)]
    lg = _ledger(rel)
    assert lg["ledger_status"] == "SPLIT_RISK_DETECTED"
    assert lg["split_risk_classes"] == ["CUSTOMER_MESSAGE"]


def test_split_evidence_write():
    rel = [{"broker_request_id": f"r{i}",
            "aggregate_effects": ["EVIDENCE_WRITE"]} for i in range(3)]
    lg = _ledger(rel)
    assert lg["ledger_status"] == "SPLIT_RISK_DETECTED"
    assert lg["split_risk_classes"] == ["EVIDENCE_WRITE"]


def test_two_sensitive_distinct_classes_needs_review():
    # Two related sensitive requests of DIFFERENT classes: each class count is
    # below the split threshold, so the ledger flags NEEDS_REVIEW (not split).
    rel = [{"broker_request_id": "e1", "aggregate_effects": ["EXPORT"]},
           {"broker_request_id": "p1", "aggregate_effects": ["PAYMENT"]}]
    lg = _ledger(rel)
    assert lg["ledger_status"] == "NEEDS_REVIEW"
    assert lg["split_risk_detected"] is False
    assert lg["signal"] is None


def test_aggregate_fields_computed():
    rel = [{"broker_request_id": "e1", "aggregate_effects": ["EXPORT"],
            "risk_score": 4, "data_scopes": ["s1"]},
           {"broker_request_id": "p1", "aggregate_effects": ["PAYMENT"],
            "risk_score": 3, "data_scopes": ["s2"]}]
    lg = _ledger(rel)
    assert lg["aggregate_effects"] == ["EXPORT", "PAYMENT"]
    assert lg["aggregate_risk_score"] == 7
    assert lg["aggregate_data_scopes"] == ["s1", "s2"]
    # Double-count per sensitive related record (aggregate_effects + class).
    assert lg["sensitive_class_counts"] == {"EXPORT": 2, "PAYMENT": 2}


def test_aggregate_effects_sorted_and_unique():
    rel = [{"broker_request_id": "a", "aggregate_effects": ["EXPORT"]},
           {"broker_request_id": "b", "aggregate_effects": ["EXPORT"]}]
    lg = _ledger(rel)
    # Deduped + sorted regardless of how many records carry the effect.
    assert lg["aggregate_effects"] == ["EXPORT"]
    assert lg["related_broker_request_ids"] == ["a", "b"]


def test_ledger_hash_deterministic():
    rel = [{"broker_request_id": "e1", "aggregate_effects": ["EXPORT"],
            "risk_score": 2}]
    a = _ledger(rel)
    c = _ledger(rel)
    assert a["multi_request_safety_ledger_hash"] == \
        c["multi_request_safety_ledger_hash"]


def test_stricter_split_threshold_triggers_split():
    # One EXPORT related request (class count 2): safe-ish under the default
    # threshold of 3, but a stricter policy of 2 promotes it to a split risk.
    rel = [{"broker_request_id": "e1", "aggregate_effects": ["EXPORT"]}]
    default = _ledger(rel)
    strict = _ledger(rel, policy={"split_threshold": 2})
    assert default["ledger_status"] == "NEEDS_REVIEW"
    assert default["split_risk_detected"] is False
    assert strict["ledger_status"] == "SPLIT_RISK_DETECTED"
    assert strict["split_risk_detected"] is True

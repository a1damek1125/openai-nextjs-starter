"""TOOL-B5 cross-request effect conservation (b.build_effect_conservation).

The sum of sensitive-effect units declared across a related request set must not
exceed the effect budget (default 2). NOTE (verified by running): each related
sensitive record contributes 2 units (aggregate_effects + derived class). To
observe CROSS_REQUEST_EFFECT_CONSERVATION_FAILED as the DOMINANT failure the set
is built so the effect sum exceeds the budget while no single class reaches the
split threshold (2 distinct classes, each count 2 < 3).
"""
from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k

ENV = {"customer_id": "", "batch_id": "", "task_id": "", "case_id": ""}


def _ledger(related, policy=None):
    return b.build_multi_request_ledger(
        tenant_id="t", broker_request_id="br1", envelope=ENV,
        self_effects=[], related_requests=related, policy=policy)


def _cons(related, policy=None):
    lg = _ledger(related, policy=policy)
    return b.build_effect_conservation(
        tenant_id="t", broker_request_id="br1", ledger=lg,
        related_requests=related, policy=policy)


def test_clean_effect_conservation_matched(gate):
    o = k.clean_outcome(gate)
    ec = o["cross_request_effect_conservation"]
    assert ec["conservation_status"] == "EFFECT_CONSERVATION_MATCHED"
    assert ec["signal"] is None
    assert ec["effect_budget_exceeded"] is False


def test_effect_budget_exceeded_is_dominant(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    # 1 EXPORT + 1 PAYMENT -> effect sum 4 > budget 2, but each class count is
    # 2 (< split threshold 3), so effect-conservation is the dominant failure.
    rel = [{"broker_request_id": "e1", "aggregate_effects": ["EXPORT"]},
           {"broker_request_id": "p1", "aggregate_effects": ["PAYMENT"]}]
    o = k.prepare(gate, d, pobj, head, quality, contract, cert,
                  related_requests=rel)
    ec = o["cross_request_effect_conservation"]
    assert ec["conservation_status"] == "EFFECT_BUDGET_EXCEEDED"
    assert ec["signal"] == "CROSS_REQUEST_EFFECT_CONSERVATION_FAILED"
    assert o["multi_request_safety_ledger"]["ledger_status"] == "NEEDS_REVIEW"
    assert o["broker_status"] == "BLOCKED"
    assert o["dominant_signal"] == "CROSS_REQUEST_EFFECT_CONSERVATION_FAILED"


def test_effect_conservation_fields():
    rel = [{"broker_request_id": "e1", "aggregate_effects": ["EXPORT"]},
           {"broker_request_id": "p1", "aggregate_effects": ["PAYMENT"]}]
    ec = _cons(rel)
    assert ec["declared_effect_sum"] == 4
    assert ec["allowed_effect_budget"] == 2
    assert ec["effect_budget_exceeded"] is True


def test_related_request_hashes_field():
    rel = [{"broker_request_id": "e1", "aggregate_effects": ["EXPORT"],
            "payload_hash": "ph1"}]
    ec = _cons(rel)
    assert ec["related_request_hashes"] == ["ph1"]


def test_within_budget_matched():
    # A single EXPORT related record -> declared sum 2 == budget 2 (not >).
    rel = [{"broker_request_id": "e1", "aggregate_effects": ["EXPORT"]}]
    ec = _cons(rel)
    assert ec["declared_effect_sum"] == 2
    assert ec["effect_budget_exceeded"] is False
    assert ec["conservation_status"] == "EFFECT_CONSERVATION_MATCHED"


def test_stricter_budget_triggers_earlier():
    rel = [{"broker_request_id": "e1", "aggregate_effects": ["EXPORT"]}]
    default = _cons(rel)
    strict = _cons(rel, policy={"effect_budget": 1})
    assert default["conservation_status"] == "EFFECT_CONSERVATION_MATCHED"
    assert strict["conservation_status"] == "EFFECT_BUDGET_EXCEEDED"
    assert strict["allowed_effect_budget"] == 1


def test_effect_conservation_hash_deterministic():
    rel = [{"broker_request_id": "e1", "aggregate_effects": ["EXPORT"]},
           {"broker_request_id": "p1", "aggregate_effects": ["PAYMENT"]}]
    a = _cons(rel)
    c = _cons(rel)
    assert a["cross_request_effect_conservation_hash"] == \
        c["cross_request_effect_conservation_hash"]


def test_effect_conservation_hash_excludes_itself():
    rel = [{"broker_request_id": "e1", "aggregate_effects": ["EXPORT"]}]
    ec = _cons(rel)
    h = ec["cross_request_effect_conservation_hash"]
    recomputed = b._core_hash(
        {**ec, "cross_request_effect_conservation_hash": "ZZZ"},
        "cross_request_effect_conservation_hash")
    assert recomputed == h

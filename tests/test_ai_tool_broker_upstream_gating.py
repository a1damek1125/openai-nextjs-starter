"""TOOL-B5 upstream (B1/B2/B3/B4) narrowing.

The null broker only prepares requests whose entire upstream chain is clean:
B1 registry head admitted, B2 quality passing, B3 contract + broker-readiness
certificate live, B4 decision future-only ALLOWED, no open circuit breaker. Any
upstream fault fails closed. Executes nothing. Each test reuses one clean setup
and mutates copies so the clean baseline proves the block is the injected cause.
"""
from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k


def _clean(gate, d, pobj, head, quality, contract, cert):
    return k.prepare(gate, d, pobj, head, quality, contract, cert)


def test_b4_non_allowed_decision_blocks(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    assert _clean(gate, d, pobj, head, quality, contract, cert)[
        "broker_status"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"
    d2 = {**d, "decision_status": "PREACTION_DENIED"}
    o = k.prepare(gate, d2, pobj, head, quality, contract, cert)
    assert o["broker_status"] == "BLOCKED"
    assert "TOOL_B4_BLOCKED" in o["all_signals"]


def test_b1_head_quarantined_blocks(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    assert _clean(gate, d, pobj, head, quality, contract, cert)[
        "broker_status"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"
    o = k.prepare(gate, d, pobj, {**head, "status": "QUARANTINED"}, quality,
                  contract, cert)
    assert o["broker_status"] == "BLOCKED"
    assert "TOOL_B1_BLOCKED" in o["all_signals"]


def test_b1_head_not_admitted_blocks(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o = k.prepare(gate, d, pobj, {**head, "admitted": False}, quality,
                  contract, cert)
    assert o["broker_status"] == "BLOCKED"
    assert "TOOL_B1_BLOCKED" in o["all_signals"]


def test_b2_quality_fail_blocks(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    assert _clean(gate, d, pobj, head, quality, contract, cert)[
        "broker_status"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"
    o = k.prepare(gate, d, pobj, head, {**quality, "quality_status":
                  "QUALITY_FAIL"}, contract, cert)
    assert o["broker_status"] == "BLOCKED"
    assert "TOOL_B2_BLOCKED" in o["all_signals"]


def test_b3_contract_status_narrowing(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    assert _clean(gate, d, pobj, head, quality, contract, cert)[
        "broker_status"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"
    blocked = k.prepare(gate, d, pobj, head, quality,
                        {**contract, "contract_status": "BLOCKED"}, cert)
    assert blocked["broker_status"] == "BLOCKED"
    assert "TOOL_B3_BLOCKED" in blocked["all_signals"]
    revoked = k.prepare(gate, d, pobj, head, quality,
                        {**contract, "contract_status": "REVOKED"}, cert)
    assert revoked["broker_status"] == "REVOKED"
    stale = k.prepare(gate, d, pobj, head, quality,
                      {**contract, "contract_status": "STALE"}, cert)
    assert stale["broker_status"] == "STALE"
    assert stale["dominant_signal"] == "CONTRACT_STALE"
    novel = k.prepare(gate, d, pobj, head, quality,
                      {**contract, "contract_status": "SOMETHING_NEW"}, cert)
    assert novel["broker_status"] == "BLOCKED"
    assert "TOOL_B3_BLOCKED" in novel["all_signals"]


def test_broker_readiness_certificate_narrowing(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    revoked = k.prepare(gate, d, pobj, head, quality, contract,
                        {**cert, "certificate_status": "REVOKED"})
    assert revoked["broker_status"] == "REVOKED"
    blocked = k.prepare(gate, d, pobj, head, quality, contract,
                        {**cert, "certificate_status": "BLOCKED"})
    assert blocked["broker_status"] == "BLOCKED"
    assert "TOOL_B3_BLOCKED" in blocked["all_signals"]


def test_open_circuit_breaker_blocks(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    assert _clean(gate, d, pobj, head, quality, contract, cert)[
        "broker_status"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"
    o = k.prepare(gate, d, pobj, head, quality, contract, cert,
                  circuit_breaker={"breaker_state": "OPEN"})
    assert o["broker_status"] == "BLOCKED"
    assert o["dominant_signal"] == "CIRCUIT_BREAKER_ACTIVE"


def test_only_future_only_status_is_b4_acceptable(gate):
    assert b.B4_ACCEPTABLE_STATUSES == {
        "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"}
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o = _clean(gate, d, pobj, head, quality, contract, cert)
    assert o["broker_status"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"
    assert d["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"

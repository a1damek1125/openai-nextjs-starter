"""TOOL-B5 cumulative risk conservation (b.build_risk_conservation).

The aggregate risk_score summed across a related request set must not exceed the
risk limit (default 12). Inputs use non-sensitive (no aggregate_effects) related
records so risk is the dominant failure rather than split/effect conservation.
Verified by running.
"""
from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k

ENV = {"customer_id": "", "batch_id": "", "task_id": "", "case_id": ""}


def _ledger(related, policy=None):
    return b.build_multi_request_ledger(
        tenant_id="t", broker_request_id="br1", envelope=ENV,
        self_effects=[], related_requests=related, policy=policy)


def _risk(related, policy=None):
    lg = _ledger(related, policy=policy)
    return b.build_risk_conservation(
        tenant_id="t", broker_request_id="br1", ledger=lg,
        related_requests=related, policy=policy)


def test_clean_risk_conservation_matched(gate):
    o = k.clean_outcome(gate)
    rc = o["cumulative_risk_conservation"]
    assert rc["risk_conservation_status"] == "RISK_CONSERVATION_MATCHED"
    assert rc["signal"] is None
    assert rc["risk_exceeded"] is False


def test_risk_exceeded_is_dominant(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    # Two non-sensitive related requests summing risk 14 > limit 12.
    rel = [{"broker_request_id": f"r{i}", "risk_score": 7} for i in range(2)]
    o = k.prepare(gate, d, pobj, head, quality, contract, cert,
                  related_requests=rel)
    rc = o["cumulative_risk_conservation"]
    assert rc["risk_conservation_status"] == "RISK_EXCEEDED"
    assert rc["signal"] == "CUMULATIVE_RISK_CONSERVATION_FAILED"
    assert rc["risk_sum"] == 14
    assert o["broker_status"] == "BLOCKED"
    assert o["dominant_signal"] == "CUMULATIVE_RISK_CONSERVATION_FAILED"
    # No sensitive effects -> ledger/effect conservation stay clean.
    assert o["multi_request_safety_ledger"]["ledger_status"] == \
        "MULTI_REQUEST_SAFE"


def test_risk_conservation_fields():
    rel = [{"broker_request_id": f"r{i}", "risk_score": 7,
            "externality": 2, "customer_visibility": 1} for i in range(2)]
    rc = _risk(rel)
    assert rc["risk_sum"] == 14
    assert rc["risk_limit"] == 12
    assert rc["risk_dimensions"] == {
        "aggregate_externality": 4,
        "aggregate_customer_visibility": 2,
        "aggregate_risk_score": 14,
    }


def test_within_limit_matched():
    rel = [{"broker_request_id": "r0", "risk_score": 5}]
    rc = _risk(rel)
    assert rc["risk_sum"] == 5
    assert rc["risk_exceeded"] is False
    assert rc["risk_conservation_status"] == "RISK_CONSERVATION_MATCHED"


def test_stricter_risk_limit_triggers_earlier():
    rel = [{"broker_request_id": "r0", "risk_score": 5}]
    default = _risk(rel)
    strict = _risk(rel, policy={"risk_limit": 4})
    assert default["risk_conservation_status"] == "RISK_CONSERVATION_MATCHED"
    assert strict["risk_conservation_status"] == "RISK_EXCEEDED"
    assert strict["risk_limit"] == 4


def test_risk_dimensions_track_ledger_aggregates():
    rel = [{"broker_request_id": "r0", "risk_score": 3, "externality": 5,
            "customer_visibility": 6}]
    lg = _ledger(rel)
    rc = b.build_risk_conservation(
        tenant_id="t", broker_request_id="br1", ledger=lg,
        related_requests=rel, policy=None)
    assert rc["risk_dimensions"]["aggregate_externality"] == \
        lg["aggregate_externality"]
    assert rc["risk_dimensions"]["aggregate_customer_visibility"] == \
        lg["aggregate_customer_visibility"]
    assert rc["risk_sum"] == lg["aggregate_risk_score"]


def test_risk_conservation_hash_deterministic():
    rel = [{"broker_request_id": "r0", "risk_score": 5}]
    a = _risk(rel)
    c = _risk(rel)
    assert a["cumulative_risk_conservation_hash"] == \
        c["cumulative_risk_conservation_hash"]


def test_risk_conservation_hash_excludes_itself():
    rel = [{"broker_request_id": "r0", "risk_score": 5}]
    rc = _risk(rel)
    h = rc["cumulative_risk_conservation_hash"]
    recomputed = b._core_hash(
        {**rc, "cumulative_risk_conservation_hash": "ZZZ"},
        "cumulative_risk_conservation_hash")
    assert recomputed == h

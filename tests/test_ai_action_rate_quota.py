"""TOOL-B4: rate limiting, quota, and non-wideable policy clamping."""
from finalis.ai_employee import tool_guardrails as g


def test_rate_limited_via_strict_policy(gate):
    tool_id, contract = gate.preaction_tool()
    # First decision consumes the window; a strict rate_limit_per_window=1 then
    # blocks the second.
    d1 = gate.decide(tool_id, contract, policy={"rate_limit_per_window": 1})
    assert d1["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"
    d2 = gate.decide(tool_id, contract, policy={"rate_limit_per_window": 1},
                     idempotency_key="idem-2")
    assert d2["decision_status"] == "PREACTION_RATE_LIMITED"
    assert d2["dominant_signal"] == "RATE_LIMITED"


def test_rate_limited_at_default_window(gate):
    tool_id, contract = gate.preaction_tool()
    # Default rate_limit_per_window is 20: the 21st decision for the same tool
    # is rate limited (window_count >= 20).
    assert g.DEFAULT_POLICY["rate_limit_per_window"] == 20
    statuses = []
    for i in range(21):
        statuses.append(gate.decide(tool_id, contract,
                                    idempotency_key=f"k{i}")["decision_status"])
    assert statuses[:20] == ["PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"] * 20
    assert statuses[20] == "PREACTION_RATE_LIMITED"


def test_quota_exceeded_via_strict_policy(gate):
    tool_id, contract = gate.preaction_tool()
    d1 = gate.decide(tool_id, contract, policy={"quota_per_period": 1})
    assert d1["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"
    d2 = gate.decide(tool_id, contract, policy={"quota_per_period": 1},
                     idempotency_key="idem-2")
    assert d2["decision_status"] == "PREACTION_QUOTA_EXCEEDED"
    assert d2["dominant_signal"] == "QUOTA_EXCEEDED"


def test_policy_cannot_be_widened(gate):
    tool_id, contract = gate.preaction_tool()
    # A client passing a huge limit is clamped to the default (20), never wider.
    d = gate.decide(tool_id, contract,
                    policy={"rate_limit_per_window": 100000})
    assert d["rate_quota_check"]["rate_limit_per_window"] == \
        g.DEFAULT_POLICY["rate_limit_per_window"] == 20
    # A stricter value IS honored.
    d2 = gate.decide(tool_id, contract, policy={"rate_limit_per_window": 1},
                     idempotency_key="idem-2")
    assert d2["rate_quota_check"]["rate_limit_per_window"] == 1


def test_quota_not_widened(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.decide(tool_id, contract,
                    policy={"quota_per_period": 999999})
    assert d["rate_quota_check"]["quota_per_period"] == \
        g.DEFAULT_POLICY["quota_per_period"] == 200

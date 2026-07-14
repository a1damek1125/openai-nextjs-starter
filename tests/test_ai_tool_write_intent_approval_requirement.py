"""TOOL-B7 approval requirement: human approval + meaningful judgment are always
required before a future commit; approval never executes; HIGH risk => dual
control."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def _req(gate, **over):
    return k.prepare(gate, k.b6_outcome(gate), approve=False,
                     **over)["approval_requirement"]


def test_human_approval_required(gate):
    assert _req(gate)["human_approval_required_before_future_commit"] is True


def test_meaningful_judgment_required(gate):
    assert _req(gate)["meaningful_human_judgment_required"] is True


def test_approval_does_not_execute(gate):
    assert _req(gate)["approval_does_not_execute"] is True


def test_low_risk_no_dual_control(gate):
    assert _req(gate, risk_tier="LOW")["dual_control_required"] is False


def test_high_risk_requires_dual_control(gate):
    assert _req(gate, risk_tier="HIGH")["dual_control_required"] is True


def test_default_risk_no_dual_control(gate):
    assert _req(gate)["dual_control_required"] is False


def test_required_acknowledgements_non_empty(gate):
    acks = _req(gate)["required_acknowledgements"]
    assert acks
    assert "ACK_DRAFT_ONLY_NO_EXECUTION" in acks
    assert "ACK_FUTURE_COMMIT_SEPARATE" in acks


def test_required_acknowledgements_sorted_unique(gate):
    acks = _req(gate)["required_acknowledgements"]
    assert acks == sorted(set(acks))


def test_requirement_hash_recomputes(gate):
    r = _req(gate)
    assert _core_hash(r, "approval_requirement_hash") == \
        r["approval_requirement_hash"]


def test_requirement_hash_stable_across_actor(gate):
    b6 = k.b6_outcome(gate)
    r1 = k.prepare(gate, b6, approve=False, actor_id="a")["approval_requirement"]
    r2 = k.prepare(gate, b6, approve=False, actor_id="b")["approval_requirement"]
    assert r1["approval_requirement_hash"] == r2["approval_requirement_hash"]

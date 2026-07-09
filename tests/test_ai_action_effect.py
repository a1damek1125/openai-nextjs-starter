"""TOOL-B4 pre-action monitor: declared-effect boundary check.

A declared effect that is in FORBIDDEN_EFFECTS, or a contract whose effect
boundary flags a read-only mislabel, yields EFFECT_FORBIDDEN -> PREACTION_BLOCKED.
"""
import copy

from finalis.ai_employee import tool_guardrails as g
from tests._b4_kernel import setup, make_proposal, evaluate


def _a_forbidden_effect():
    return sorted(g.FORBIDDEN_EFFECTS)[0]


# --- kernel: build_effect_check --------------------------------------------
def test_forbidden_declared_effect_flagged(gate):
    tool_id, contract, *_ = setup(gate)
    fe = _a_forbidden_effect()
    raw = gate.clean_proposal_body(tool_id, contract)
    raw["declared_effects"] = [fe]
    check = g.build_effect_check(
        proposal=make_proposal(gate, tool_id, contract, raw), contract=contract)
    assert fe in check["forbidden_effects_present"]
    assert check["signal"] == "EFFECT_FORBIDDEN"


def test_read_only_mislabel_flags_effect_forbidden(gate):
    tool_id, contract, *_ = setup(gate)
    c = copy.deepcopy(contract)
    c["contract_effect_boundary"]["read_only_mislabel_detected"] = True
    raw = gate.clean_proposal_body(tool_id, contract)
    check = g.build_effect_check(
        proposal=make_proposal(gate, tool_id, contract, raw), contract=c)
    assert check["read_only_mislabel_detected"] is True
    assert check["signal"] == "EFFECT_FORBIDDEN"


def test_clean_declared_effects_ok(gate):
    tool_id, contract, *_ = setup(gate)
    for effects in ([], ["PURE_READ"]):
        raw = gate.clean_proposal_body(tool_id, contract)
        raw["declared_effects"] = effects
        check = g.build_effect_check(
            proposal=make_proposal(gate, tool_id, contract, raw),
            contract=contract)
        assert check["forbidden_effects_present"] == []
        assert check["signal"] is None


# --- via evaluate_proposal --------------------------------------------------
def test_evaluate_forbidden_effect_blocked(gate):
    tool_id, contract, head, quality, cert = setup(gate)
    raw = gate.clean_proposal_body(tool_id, contract)
    raw["declared_effects"] = [_a_forbidden_effect()]
    dec = evaluate(gate, make_proposal(gate, tool_id, contract, raw),
                   head, quality, contract, cert)
    assert dec["dominant_signal"] == "EFFECT_FORBIDDEN"
    assert dec["decision_status"] == "PREACTION_BLOCKED"


def test_evaluate_mislabel_blocked(gate):
    tool_id, contract, head, quality, cert = setup(gate)
    c = copy.deepcopy(contract)
    c["contract_effect_boundary"]["read_only_mislabel_detected"] = True
    raw = gate.clean_proposal_body(tool_id, contract)
    dec = evaluate(gate, make_proposal(gate, tool_id, contract, raw),
                   head, quality, c, cert)
    assert dec["dominant_signal"] == "EFFECT_FORBIDDEN"
    assert dec["decision_status"] == "PREACTION_BLOCKED"


# --- sub-read endpoint ------------------------------------------------------
def test_effect_endpoint_returns_subreport(gate):
    tool_id, contract = gate.preaction_tool()
    pid = gate.propose(tool_id, contract).json()["proposal_id"]
    effect = gate.pa(pid, "/effect").json()["effect_check"]
    assert effect["forbidden_effects_present"] == []
    assert effect["read_only_mislabel_detected"] is False
    assert effect["signal"] is None

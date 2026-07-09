"""TOOL-B4 pre-action monitor: state-witness freshness guard.

A proposal must be formed against the current world state: state_witness.epoch
must equal the contract's source_freshness_epoch (an opaque hash). Missing or
mismatched -> STATE_WITNESS_STALE -> PREACTION_NEEDS_STATE_REFRESH.
"""
from finalis.ai_employee import tool_guardrails as g
from tests._b4_kernel import setup, make_proposal, evaluate


# --- kernel: build_state_witness_guard -------------------------------------
def test_clean_witness_matches_epoch_ok(gate):
    tool_id, contract, *_ = setup(gate)
    raw = gate.clean_proposal_body(tool_id, contract)
    guard = g.build_state_witness_guard(
        proposal=make_proposal(gate, tool_id, contract, raw), contract=contract)
    assert guard["witness_epoch"] == contract["source_freshness_epoch"]
    assert guard["current_epoch"] == contract["source_freshness_epoch"]
    assert guard["state_witness_present"] is True
    assert guard["state_witness_stale"] is False
    assert guard["signal"] is None


def test_missing_witness_is_stale(gate):
    tool_id, contract, *_ = setup(gate)
    raw = gate.clean_proposal_body(tool_id, contract)
    raw["state_witness"] = {}
    guard = g.build_state_witness_guard(
        proposal=make_proposal(gate, tool_id, contract, raw), contract=contract)
    assert guard["state_witness_present"] is False
    assert guard["state_witness_stale"] is True
    assert guard["signal"] == "STATE_WITNESS_STALE"


def test_wrong_epoch_is_stale(gate):
    tool_id, contract, *_ = setup(gate)
    raw = gate.clean_proposal_body(tool_id, contract)
    raw["state_witness"] = {"epoch": "wrong"}
    guard = g.build_state_witness_guard(
        proposal=make_proposal(gate, tool_id, contract, raw), contract=contract)
    assert guard["state_witness_stale"] is True
    assert guard["signal"] == "STATE_WITNESS_STALE"


# --- kernel: evaluate_proposal ---------------------------------------------
def test_evaluate_missing_witness_needs_refresh(gate):
    tool_id, contract, head, quality, cert = setup(gate)
    raw = gate.clean_proposal_body(tool_id, contract)
    raw["state_witness"] = {}
    dec = evaluate(gate, make_proposal(gate, tool_id, contract, raw),
                   head, quality, contract, cert)
    assert dec["dominant_signal"] == "STATE_WITNESS_STALE"
    assert dec["decision_status"] == "PREACTION_NEEDS_STATE_REFRESH"


def test_evaluate_clean_witness_allowed(gate):
    tool_id, contract, head, quality, cert = setup(gate)
    raw = gate.clean_proposal_body(tool_id, contract)
    dec = evaluate(gate, make_proposal(gate, tool_id, contract, raw),
                   head, quality, contract, cert)
    assert dec["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"


# --- via POST endpoint ------------------------------------------------------
def test_post_wrong_epoch_needs_refresh(gate):
    tool_id, contract = gate.preaction_tool()
    dec = gate.decide(tool_id, contract, state_witness={"epoch": "wrong"})
    assert dec["dominant_signal"] == "STATE_WITNESS_STALE"
    assert dec["decision_status"] == "PREACTION_NEEDS_STATE_REFRESH"


def test_post_correct_epoch_allowed(gate):
    tool_id, contract = gate.preaction_tool()
    dec = gate.decide(tool_id, contract, state_witness={
        "epoch": contract["source_freshness_epoch"]})
    assert dec["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"

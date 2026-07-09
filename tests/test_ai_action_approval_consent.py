"""TOOL-B4 pre-action monitor: approval & consent guards.

Approval and consent are only demanded when the contract requires them (HIGH+
risk or an explicit flag). Per the B4 reference these are tested by building a
REAL contract via gate.preaction_tool and setting requires_approval /
requires_consent on the returned dict, then driving the kernel directly.
"""
from finalis.ai_employee import tool_guardrails as g
from tests._b4_kernel import setup, make_proposal, evaluate


# --- build_approval_guard --------------------------------------------------
def test_approval_required_missing_ref_flags_missing(gate):
    tool_id, contract, *_ = setup(gate)
    c = dict(contract)
    c["requires_approval"] = True
    raw = gate.clean_proposal_body(tool_id, contract)
    guard = g.build_approval_guard(
        proposal=make_proposal(gate, tool_id, contract, raw), contract=c,
        actor_type="human")
    assert guard["approval_required"] is True
    assert guard["approval_ok"] is False
    assert guard["signal"] == "APPROVAL_MISSING"


def test_approval_valid_human_other_approver_needs_server_verification(gate):
    tool_id, contract, *_ = setup(gate)
    c = dict(contract)
    c["requires_approval"] = True
    raw = gate.clean_proposal_body(tool_id, contract)
    raw["approval_ref"] = {"granted": True, "approver_type": "human",
                           "approver_id": "someone_else"}
    prop = make_proposal(gate, tool_id, contract, raw, actor_id="a1")
    # An untrusted approval CLAIM alone never satisfies the gate — a proposer
    # could otherwise self-authorize by fabricating approval_ref.
    unverified = g.build_approval_guard(
        proposal=prop, contract=c, actor_type="human", verified=False)
    assert unverified["approval_ok"] is False
    assert unverified["signal"] == "APPROVAL_MISSING"
    # A SERVER-verified grant (a real, live approval exists) satisfies it.
    verified = g.build_approval_guard(
        proposal=prop, contract=c, actor_type="human", verified=True)
    assert verified["approval_ok"] is True
    assert verified["self_approval_detected"] is False
    assert verified["server_verified"] is True
    assert verified["signal"] is None


def test_self_approval_same_actor_id_rejected(gate):
    tool_id, contract, *_ = setup(gate)
    c = dict(contract)
    c["requires_approval"] = True
    raw = gate.clean_proposal_body(tool_id, contract)
    # Approver id == proposer actor id -> AI/actor approving its own action.
    raw["approval_ref"] = {"granted": True, "approver_type": "human",
                           "approver_id": "a1"}
    guard = g.build_approval_guard(
        proposal=make_proposal(gate, tool_id, contract, raw, actor_id="a1"),
        contract=c, actor_type="human")
    assert guard["self_approval_detected"] is True
    assert guard["approval_ok"] is False
    assert guard["signal"] == "APPROVAL_MISSING"


def test_non_human_approver_is_self_approval(gate):
    tool_id, contract, *_ = setup(gate)
    c = dict(contract)
    c["requires_approval"] = True
    raw = gate.clean_proposal_body(tool_id, contract)
    raw["approval_ref"] = {"granted": True, "approver_type": "ai_employee",
                           "approver_id": "other"}
    guard = g.build_approval_guard(
        proposal=make_proposal(gate, tool_id, contract, raw, actor_id="a1"),
        contract=c, actor_type="human")
    assert guard["self_approval_detected"] is True
    assert guard["signal"] == "APPROVAL_MISSING"


def test_approval_not_required_ok_without_ref(gate):
    tool_id, contract, *_ = setup(gate)
    raw = gate.clean_proposal_body(tool_id, contract)
    guard = g.build_approval_guard(
        proposal=make_proposal(gate, tool_id, contract, raw), contract=contract,
        actor_type="human")
    assert guard["approval_required"] is False
    assert guard["approval_ok"] is True
    assert guard["signal"] is None


# --- build_consent_guard ---------------------------------------------------
def test_consent_required_missing_flags_missing(gate):
    tool_id, contract, *_ = setup(gate)
    c = dict(contract)
    c["requires_consent"] = True
    raw = gate.clean_proposal_body(tool_id, contract)
    guard = g.build_consent_guard(
        proposal=make_proposal(gate, tool_id, contract, raw), contract=c)
    assert guard["consent_required"] is True
    assert guard["consent_ok"] is False
    assert guard["signal"] == "CONSENT_MISSING"


def test_consent_granted_needs_server_verification(gate):
    tool_id, contract, *_ = setup(gate)
    c = dict(contract)
    c["requires_consent"] = True
    raw = gate.clean_proposal_body(tool_id, contract)
    raw["consent_ref"] = {"granted": True}
    prop = make_proposal(gate, tool_id, contract, raw)
    # A consent CLAIM in the untrusted proposal never satisfies consent on its
    # own — consent cannot be self-served.
    unverified = g.build_consent_guard(proposal=prop, contract=c,
                                       verified=False)
    assert unverified["consent_ok"] is False
    assert unverified["signal"] == "CONSENT_MISSING"
    verified = g.build_consent_guard(proposal=prop, contract=c, verified=True)
    assert verified["consent_ok"] is True
    assert verified["server_verified"] is True
    assert verified["signal"] is None


def test_consent_override_never_satisfies(gate):
    tool_id, contract, *_ = setup(gate)
    c = dict(contract)
    c["requires_consent"] = True
    raw = gate.clean_proposal_body(tool_id, contract)
    raw["consent_ref"] = {"granted": True, "override": True}
    guard = g.build_consent_guard(
        proposal=make_proposal(gate, tool_id, contract, raw), contract=c)
    assert guard["consent_override_attempt"] is True
    assert guard["consent_ok"] is False
    assert guard["signal"] == "CONSENT_MISSING"


# --- via evaluate_proposal (statuses + dominance) --------------------------
def test_evaluate_requires_approval_status(gate):
    tool_id, contract, head, quality, cert = setup(gate)
    c = dict(contract)
    c["requires_approval"] = True
    raw = gate.clean_proposal_body(tool_id, contract)
    dec = evaluate(gate, make_proposal(gate, tool_id, contract, raw),
                   head, quality, c, cert)
    assert dec["decision_status"] == "PREACTION_NEEDS_HUMAN_APPROVAL"
    assert dec["dominant_signal"] == "APPROVAL_MISSING"


def test_evaluate_requires_consent_status(gate):
    tool_id, contract, head, quality, cert = setup(gate)
    c = dict(contract)
    c["requires_consent"] = True
    raw = gate.clean_proposal_body(tool_id, contract)
    dec = evaluate(gate, make_proposal(gate, tool_id, contract, raw),
                   head, quality, c, cert)
    assert dec["decision_status"] == "PREACTION_NEEDS_CONSENT"
    assert dec["dominant_signal"] == "CONSENT_MISSING"


def test_approval_dominates_consent_when_both_present(gate):
    tool_id, contract, head, quality, cert = setup(gate)
    c = dict(contract)
    c["requires_approval"] = True
    c["requires_consent"] = True
    raw = gate.clean_proposal_body(tool_id, contract)
    dec = evaluate(gate, make_proposal(gate, tool_id, contract, raw),
                   head, quality, c, cert)
    assert "APPROVAL_MISSING" in dec["all_signals"]
    assert "CONSENT_MISSING" in dec["all_signals"]
    # APPROVAL_MISSING outranks CONSENT_MISSING in the fail-closed ladder.
    assert dec["dominant_signal"] == "APPROVAL_MISSING"
    assert dec["decision_status"] == "PREACTION_NEEDS_HUMAN_APPROVAL"

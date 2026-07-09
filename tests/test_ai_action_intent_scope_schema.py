"""TOOL-B4 pre-action monitor: intent, scope, and schema structural checks."""
from finalis.ai_employee import tool_guardrails as g
from tests._b4_kernel import setup, make_proposal, evaluate


# --- intent ----------------------------------------------------------------
def test_intent_allowed_purpose_matches(gate):
    tool_id, contract, *_ = setup(gate)
    raw = gate.clean_proposal_body(tool_id, contract)  # intent CASE_TRIAGE
    check = g.build_intent_check(
        proposal=make_proposal(gate, tool_id, contract, raw), contract=contract,
        allowed_purposes=["CASE_TRIAGE"])
    assert check["intent_matched"] is True
    assert check["signal"] is None


def test_empty_intent_mismatch_denied(gate):
    tool_id, contract, head, quality, cert = setup(gate)
    raw = gate.clean_proposal_body(tool_id, contract)
    raw["intent"] = ""
    dec = evaluate(gate, make_proposal(gate, tool_id, contract, raw),
                   head, quality, contract, cert)
    assert dec["dominant_signal"] == "INTENT_MISMATCH"
    assert dec["decision_status"] == "PREACTION_DENIED"


def test_intent_not_in_allowed_purposes_denied(gate):
    tool_id, contract, head, quality, cert = setup(gate)
    raw = gate.clean_proposal_body(tool_id, contract)
    raw["intent"] = "NOT_A_PURPOSE"
    dec = evaluate(gate, make_proposal(gate, tool_id, contract, raw),
                   head, quality, contract, cert)
    assert dec["dominant_signal"] == "INTENT_MISMATCH"
    assert dec["decision_status"] == "PREACTION_DENIED"


def test_empty_allowed_purposes_accepts_any_nonempty_intent(gate):
    tool_id, contract, *_ = setup(gate)
    raw = gate.clean_proposal_body(tool_id, contract)
    raw["intent"] = "ANYTHING"
    check = g.build_intent_check(
        proposal=make_proposal(gate, tool_id, contract, raw), contract=contract,
        allowed_purposes=[])
    assert check["intent_matched"] is True
    assert check["signal"] is None


# --- scope -----------------------------------------------------------------
def test_scope_subset_ok(gate):
    tool_id, contract, *_ = setup(gate)
    raw = gate.clean_proposal_body(tool_id, contract)
    check = g.build_scope_check(
        proposal=make_proposal(gate, tool_id, contract, raw), contract=contract)
    assert check["scope_ok"] is True
    assert "category:DATA_SEARCH" in check["requested_scope_tokens"]
    assert check["signal"] is None


def test_unbound_scope_needs_reduced_scope(gate):
    tool_id, contract, head, quality, cert = setup(gate)
    raw = gate.clean_proposal_body(tool_id, contract)
    raw["requested_scope"] = {"record_id": "zzz"}
    dec = evaluate(gate, make_proposal(gate, tool_id, contract, raw),
                   head, quality, contract, cert)
    assert dec["dominant_signal"] == "PAYLOAD_SCOPE_MISMATCH"
    assert dec["decision_status"] == "PREACTION_NEEDS_REDUCED_SCOPE"


def test_forbidden_data_scope_flags_forbidden_problem(gate):
    tool_id, contract, *_ = setup(gate)
    raw = gate.clean_proposal_body(tool_id, contract)
    # 'SECRET' is in the contract's forbidden_data_scopes.
    raw["requested_scope"] = {"category": "SECRET"}
    check = g.build_scope_check(
        proposal=make_proposal(gate, tool_id, contract, raw), contract=contract)
    assert check["scope_ok"] is False
    assert any(p.startswith("FORBIDDEN:") for p in check["scope_problems"])
    assert check["signal"] == "PAYLOAD_SCOPE_MISMATCH"


# --- schema ----------------------------------------------------------------
def test_payload_matching_schema_ok(gate):
    tool_id, contract, *_ = setup(gate)
    raw = gate.clean_proposal_body(tool_id, contract)  # payload {query:'hi'}
    check = g.build_schema_check(
        proposal=make_proposal(gate, tool_id, contract, raw), contract=contract)
    assert check["schema_ok"] is True
    assert check["signal"] is None


def test_unexpected_key_schema_mismatch_denied(gate):
    tool_id, contract, head, quality, cert = setup(gate)
    raw = gate.clean_proposal_body(tool_id, contract)
    raw["payload"] = {"query": "x", "unexpected": "y"}
    prop = make_proposal(gate, tool_id, contract, raw)
    check = g.build_schema_check(proposal=prop, contract=contract)
    assert check["schema_ok"] is False
    assert any(p.startswith("UNEXPECTED:") for p in check["schema_problems"])
    dec = evaluate(gate, prop, head, quality, contract, cert)
    assert dec["dominant_signal"] == "PAYLOAD_SCHEMA_MISMATCH"
    assert dec["decision_status"] == "PREACTION_DENIED"


def test_schema_read_from_contract_normal_form(gate):
    tool_id, contract, *_ = setup(gate)
    # Verify the schema source the check reads is the normalized input schema.
    schema = contract["contract_normal_form"]["normalized_input_schema"]
    assert set(schema["properties"]) == {"query"}
    raw = gate.clean_proposal_body(tool_id, contract)
    check = g.build_schema_check(
        proposal=make_proposal(gate, tool_id, contract, raw), contract=contract)
    assert check["declared_property_count"] == len(schema["properties"])


# --- sub-read endpoints -----------------------------------------------------
def test_intent_scope_schema_endpoints_return_subreports(gate):
    tool_id, contract = gate.preaction_tool()
    pid = gate.propose(tool_id, contract).json()["proposal_id"]

    intent = gate.pa(pid, "/intent").json()["intent_check"]
    assert intent["intent_matched"] is True and intent["signal"] is None

    scope = gate.pa(pid, "/scope").json()["scope_check"]
    assert scope["scope_ok"] is True and scope["signal"] is None

    schema = gate.pa(pid, "/schema").json()["schema_check"]
    assert schema["schema_ok"] is True and schema["signal"] is None

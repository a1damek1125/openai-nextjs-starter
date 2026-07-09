"""TOOL-B4 pre-action reference monitor: source-gate causation tests.

Proves that TOOL-B1 (registry head), TOOL-B2 (quality) and TOOL-B3 (contract)
authoritative state NARROWS the pre-action decision. Each test establishes that
a clean proposal is ALLOWED and that flipping exactly one source-truth field is
the sole cause of the adverse decision. Executes nothing.
"""
import copy

from finalis.ai_employee import tool_guardrails as g


def _inputs(gate):
    """Load real head / quality / contract for a clean admitted tool."""
    tid = gate.tid
    tool_id, contract = gate.preaction_tool()
    head = gate.app.state.tool_store.payload(tool_id, tenant_id=tid)
    quality = gate.app.state.quality_store.latest(tool_id, tenant_id=tid)
    return tid, tool_id, contract, head, quality


def _evaluate(gate, tid, tool_id, contract, head, quality):
    proposal = g.build_action_proposal(
        proposal_id="p-1", tenant_id=tid, tool_id=tool_id,
        contract_id=contract["contract_id"],
        raw=gate.clean_proposal_body(tool_id, contract),
        actor_id="u-1", actor_type="human",
        created_at="2020-01-01T00:00:00Z")
    return g.evaluate_proposal(
        proposal=proposal, head=head, quality_report=quality, contract=contract,
        broker_readiness=None, circuit_breaker=None, prior_decision=None,
        role_authority=["READ"], policy=None, usage=None, decision_id="d-1",
        tenant_id=tid, actor_id="u-1", actor_type="human",
        created_at="2020-01-01T00:00:00Z", allowed_purposes=["CASE_TRIAGE"])


# --- baseline: a clean proposal on clean sources ALLOWS ---------------------
def test_clean_sources_allow(gate):
    tid, tool_id, contract, head, quality = _inputs(gate)
    d = _evaluate(gate, tid, tool_id, contract, head, quality)
    assert d["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"
    assert d["dominant_signal"] == "ALLOWED_FOR_FUTURE_BROKER_ONLY"
    # Honesty: an allow still runs nothing and needs a future broker.
    assert d["executes_nothing"] is True
    assert d["is_execution"] is False


# --- TOOL-B1 registry head narrows -----------------------------------------
def test_b1_quarantined_head_quarantines(gate):
    tid, tool_id, contract, head, quality = _inputs(gate)
    bad = copy.deepcopy(head)
    bad["status"] = "QUARANTINED"
    bad["quarantine_status"] = "QUARANTINED"
    d = _evaluate(gate, tid, tool_id, contract, bad, quality)
    assert d["decision_status"] == "PREACTION_QUARANTINED"
    assert d["dominant_signal"] == "QUARANTINED"


def test_b1_blocked_head_blocks(gate):
    tid, tool_id, contract, head, quality = _inputs(gate)
    bad = copy.deepcopy(head)
    bad["status"] = "BLOCKED"
    d = _evaluate(gate, tid, tool_id, contract, bad, quality)
    assert d["decision_status"] == "PREACTION_BLOCKED"
    # BLOCKED (not quarantine/tamper) surfaces as the dominant B1 block.
    assert d["dominant_signal"] == "TOOL_B1_BLOCKED"


def test_b1_tampered_head_blocks(gate):
    tid, tool_id, contract, head, quality = _inputs(gate)
    bad = copy.deepcopy(head)
    bad["status"] = "TAMPERED"
    d = _evaluate(gate, tid, tool_id, contract, bad, quality)
    assert d["decision_status"] == "PREACTION_BLOCKED"
    assert d["dominant_signal"] == "TAMPERED"


# --- TOOL-B2 quality narrows -----------------------------------------------
def test_b2_quality_fail_blocks(gate):
    tid, tool_id, contract, head, quality = _inputs(gate)
    d = _evaluate(gate, tid, tool_id, contract, head,
                  {"quality_status": "QUALITY_FAIL"})
    assert d["decision_status"] == "PREACTION_BLOCKED"
    assert d["dominant_signal"] == "TOOL_B2_BLOCKED"


# --- TOOL-B3 contract narrows ----------------------------------------------
def test_b3_blocked_contract_blocks(gate):
    tid, tool_id, contract, head, quality = _inputs(gate)
    bad = copy.deepcopy(contract)
    bad["contract_status"] = "BLOCKED"
    d = _evaluate(gate, tid, tool_id, bad, head, quality)
    assert d["decision_status"] == "PREACTION_BLOCKED"
    assert d["dominant_signal"] == "TOOL_B3_BLOCKED"


def test_source_gate_is_the_cause_not_the_proposal(gate):
    """Same clean proposal: clean sources ALLOW, one flipped source-truth field
    BLOCKS. The block is caused by source state, never the proposal content."""
    tid, tool_id, contract, head, quality = _inputs(gate)
    clean = _evaluate(gate, tid, tool_id, contract, head, quality)
    assert clean["decision_status"] == \
        "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"
    bad_head = copy.deepcopy(head)
    bad_head["status"] = "QUARANTINED"
    blocked = _evaluate(gate, tid, tool_id, contract, bad_head, quality)
    assert blocked["decision_status"] == "PREACTION_QUARANTINED"
    # The only difference between the two evaluations was the B1 head status.
    assert clean["decision_status"] != blocked["decision_status"]

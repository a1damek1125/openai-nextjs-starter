"""TOOL-B4 pre-action reference monitor: staleness & revocation tests.

Covers CONTRACT_STALE -> PREACTION_STALE, REVOKED -> PREACTION_REVOKED (via
both contract_status and an advanced revocation_epoch), the dominance of
REVOKED over CONTRACT_STALE, and the /reevaluate endpoint surfacing a
revocation that lands in authoritative state AFTER the original allow.
Executes nothing.
"""
import copy
import json

from conftest import OWNER

from finalis.ai_employee import tool_guardrails as g


def _inputs(gate):
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


# --- baseline ---------------------------------------------------------------
def test_fresh_contract_allows(gate):
    tid, tool_id, contract, head, quality = _inputs(gate)
    d = _evaluate(gate, tid, tool_id, contract, head, quality)
    assert d["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"


# --- CONTRACT_STALE ---------------------------------------------------------
def test_stale_contract_is_preaction_stale(gate):
    tid, tool_id, contract, head, quality = _inputs(gate)
    bad = copy.deepcopy(contract)
    bad["contract_status"] = "STALE"
    d = _evaluate(gate, tid, tool_id, bad, head, quality)
    assert d["decision_status"] == "PREACTION_STALE"
    assert d["dominant_signal"] == "CONTRACT_STALE"


# --- REVOKED via contract_status -------------------------------------------
def test_revoked_status_is_preaction_revoked(gate):
    tid, tool_id, contract, head, quality = _inputs(gate)
    bad = copy.deepcopy(contract)
    bad["contract_status"] = "REVOKED"
    d = _evaluate(gate, tid, tool_id, bad, head, quality)
    assert d["decision_status"] == "PREACTION_REVOKED"
    assert d["dominant_signal"] == "REVOKED"


# --- REVOKED via advanced revocation epoch ---------------------------------
def test_advanced_revocation_epoch_revokes(gate):
    tid, tool_id, contract, head, quality = _inputs(gate)
    bad = copy.deepcopy(contract)
    # A non-'0' revocation epoch means the prior authority was revoked, even
    # while the contract_status itself is otherwise projectable.
    bad["revocation_epoch"] = "7"
    d = _evaluate(gate, tid, tool_id, bad, head, quality)
    assert d["decision_status"] == "PREACTION_REVOKED"
    assert d["dominant_signal"] == "REVOKED"


# --- dominance: REVOKED > CONTRACT_STALE ------------------------------------
def test_revoked_dominates_stale(gate):
    tid, tool_id, contract, head, quality = _inputs(gate)
    bad = copy.deepcopy(contract)
    # STALE status AND an advanced revocation epoch both fire; REVOKED wins.
    bad["contract_status"] = "STALE"
    bad["revocation_epoch"] = "3"
    d = _evaluate(gate, tid, tool_id, bad, head, quality)
    assert "REVOKED" in d["all_signals"]
    assert "CONTRACT_STALE" in d["all_signals"]
    assert d["dominant_signal"] == "REVOKED"
    assert d["decision_status"] == "PREACTION_REVOKED"
    # Ladder confirms the ordering that drove the resolution.
    assert g._DOMINANCE_RANK["REVOKED"] < g._DOMINANCE_RANK["CONTRACT_STALE"]


# --- reevaluate endpoint surfaces a later revocation ------------------------
def test_reevaluate_surfaces_revocation(gate):
    tid, contract = gate.preaction_tool()
    # 1. Original submission on clean state ALLOWS.
    first = gate.decide(tid, contract)
    assert first["decision_status"] == \
        "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"
    proposal_id = first["proposal_id"]

    # 2. Revoke the stored contract row (authoritative state changes AFTER the
    #    allow). _gather_inputs reads payload_json, so mutate it there.
    contract_id = contract["contract_id"]
    row = gate.db.one(
        "SELECT payload_json FROM ai_tool_contracts WHERE id=?", contract_id)
    payload = json.loads(row["payload_json"])
    payload["contract_status"] = "REVOKED"
    gate.db.conn.execute(
        "UPDATE ai_tool_contracts SET contract_status='REVOKED', "
        "payload_json=? WHERE id=?", (json.dumps(payload), contract_id))
    gate.db.conn.commit()

    # 3. Re-rendering the SAME proposal against CURRENT state now revokes.
    resp = gate.pa(proposal_id, path="/reevaluate", actor=OWNER, method="POST")
    assert resp.status_code == 200
    d = resp.json()
    assert d["decision_status"] == "PREACTION_REVOKED"
    assert d["dominant_signal"] == "REVOKED"


def test_reevaluate_stable_when_unchanged(gate):
    # Re-rendering against unchanged clean state re-derives the same allow,
    # proving the reevaluation is a pure function of current source truth.
    tid, contract = gate.preaction_tool()
    first = gate.decide(tid, contract)
    proposal_id = first["proposal_id"]
    resp = gate.pa(proposal_id, path="/reevaluate", actor=OWNER, method="POST")
    assert resp.status_code == 200
    assert resp.json()["decision_status"] == \
        "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"

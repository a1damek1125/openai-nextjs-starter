"""TOOL-B4 pre-action reference monitor: non-authority artifacts.

An Action Passport is NOT a token, a Governance Receipt is NOT authority, and a
Future Execution Lease is a NOT_IMPLEMENTED placeholder. These tests pin the
honesty flags on each artifact -- on the decision object, on the dedicated
sub-read endpoints, and on the deterministic artifact hashes.
"""
from finalis.ai_employee import tool_guardrails as g

from tests.conftest import OWNER


def _proposal(gate, tool_id, contract):
    raw = gate.clean_proposal_body(tool_id, contract)
    return g.build_action_proposal(
        proposal_id="pid", tenant_id=gate.tid, tool_id=tool_id,
        contract_id=contract["contract_id"], raw=raw, actor_id="a1",
        actor_type="human", created_at="2020-01-01T00:00:00Z")


def test_action_passport_is_not_a_token_or_authority(gate):
    tool_id, contract = gate.preaction_tool()
    p = gate.decide(tool_id, contract)["action_passport"]
    assert p["is_token"] is False
    assert p["is_bearer"] is False
    assert p["confers_authority"] is False
    assert p["grants_execution"] is False
    assert p["action_passport_version"] == g.ACTION_PASSPORT_VERSION


def test_governance_receipt_is_not_authority(gate):
    tool_id, contract = gate.preaction_tool()
    r = gate.decide(tool_id, contract)["governance_receipt"]
    assert r["is_authority"] is False
    assert r["authorizes_execution"] is False
    assert r["governance_receipt_version"] == g.GOVERNANCE_RECEIPT_VERSION


def test_future_execution_lease_is_not_implemented(gate):
    tool_id, contract = gate.preaction_tool()
    lease = gate.decide(tool_id, contract)["future_execution_lease"]
    assert lease["lease_status"] == "NOT_IMPLEMENTED"
    assert lease["lease_issued"] is False
    assert lease["broker_exists"] is False
    assert lease["grants_execution"] is False


def test_subread_endpoints_report_non_authority(gate):
    tool_id, contract = gate.preaction_tool()
    pid = gate.decide(tool_id, contract)["proposal_id"]

    passport = gate.pa(pid, "/passport", actor=OWNER).json()["action_passport"]
    assert passport["is_token"] is False and passport["is_bearer"] is False
    assert passport["confers_authority"] is False
    assert passport["grants_execution"] is False

    receipt = gate.pa(pid, "/receipt", actor=OWNER).json()["governance_receipt"]
    assert receipt["is_authority"] is False
    assert receipt["authorizes_execution"] is False

    lease = gate.pa(pid, "/lease", actor=OWNER).json()["future_execution_lease"]
    assert lease["lease_status"] == "NOT_IMPLEMENTED"
    assert lease["lease_issued"] is False and lease["broker_exists"] is False
    assert lease["grants_execution"] is False


def test_no_execution_subread_all_hold(gate):
    tool_id, contract = gate.preaction_tool()
    pid = gate.decide(tool_id, contract)["proposal_id"]
    proof = gate.pa(pid, "/no-execution", actor=OWNER).json()[
        "no_execution_proof"]
    assert proof["all_hold"] is True
    assert len(proof["assertions"]) == 12
    assert all(proof["assertions"].values())


def test_artifact_hashes_are_present(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.decide(tool_id, contract)
    for artifact, key in (
            (d["action_passport"], "action_passport_hash"),
            (d["governance_receipt"], "governance_receipt_hash"),
            (d["future_execution_lease"], "future_execution_lease_hash"),
            (d["no_execution_proof"], "no_execution_proof_hash")):
        assert isinstance(artifact[key], str) and len(artifact[key]) == 64


def test_passport_and_receipt_hashes_are_deterministic(gate):
    tool_id, contract = gate.preaction_tool()
    prop = _proposal(gate, tool_id, contract)
    status = "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"
    # The artifacts carry no timestamp of their own, so the same proposal +
    # status always yields the same content-bound hash (time-independent).
    p1 = g.build_action_passport(proposal=prop, decision_status=status,
                                 tenant_id=gate.tid)
    p2 = g.build_action_passport(proposal=prop, decision_status=status,
                                 tenant_id=gate.tid)
    assert p1["action_passport_hash"] == p2["action_passport_hash"]

    r1 = g.build_governance_receipt(proposal=prop, decision_status=status,
                                    dominant_signal="X", tenant_id=gate.tid)
    r2 = g.build_governance_receipt(proposal=prop, decision_status=status,
                                    dominant_signal="X", tenant_id=gate.tid)
    assert r1["governance_receipt_hash"] == r2["governance_receipt_hash"]

    lease = g.build_execution_lease_placeholder(proposal=prop,
                                                tenant_id=gate.tid)
    assert isinstance(lease["future_execution_lease_hash"], str)

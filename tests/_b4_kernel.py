"""Shared direct-kernel harness for TOOL-B4 pre-action monitor tests.

Not a test module (leading underscore -> not collected). Builds a REAL contract
via the gate fixture and exposes helpers to call the kernel directly, per the
B4 reference (approval/consent require mutating contract flags then evaluating).
"""
from finalis.ai_employee import tool_guardrails as g


def setup(gate):
    """Return (tool_id, contract, head, quality, cert) for a clean pure-read
    tool built through the real admission/quality/contract pipeline."""
    tool_id, contract = gate.preaction_tool()
    head = gate.app.state.tool_store.payload(tool_id, tenant_id=gate.tid)
    quality = gate.app.state.quality_store.latest(tool_id, tenant_id=gate.tid)
    projs = gate.app.state.contract_store.projections_for(
        contract["contract_id"], tenant_id=gate.tid)
    cert = projs[-1].get("broker_readiness_certificate") if projs else None
    return tool_id, contract, head, quality, cert


def make_proposal(gate, tool_id, contract, raw, actor_id="a1",
                  actor_type="human"):
    return g.build_action_proposal(
        proposal_id="p1", tenant_id=gate.tid, tool_id=tool_id,
        contract_id=contract["contract_id"], raw=raw, actor_id=actor_id,
        actor_type=actor_type, created_at="t")


def evaluate(gate, proposal, head, quality, contract, cert, actor_id="a1",
             actor_type="human", role_authority=None, allowed_purposes=None):
    return g.evaluate_proposal(
        proposal=proposal, head=head, quality_report=quality, contract=contract,
        broker_readiness=cert, circuit_breaker=None, prior_decision=None,
        role_authority=role_authority or ["READ"], policy=None, usage=None,
        decision_id="d1", tenant_id=gate.tid, actor_id=actor_id,
        actor_type=actor_type, created_at="t",
        allowed_purposes=allowed_purposes or ["CASE_TRIAGE"])

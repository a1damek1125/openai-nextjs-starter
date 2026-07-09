"""Shared (non-collected) helpers for TOOL-B5 null-broker kernel tests.

Leading underscore -> pytest does not collect this as a test module. It builds a
real B4 ALLOWED decision through the live app and exposes convenient wrappers so
each test file can drive the kernel (finalis.ai_employee.tool_broker) directly.
"""
from finalis.ai_employee import tool_broker as b
from tests.conftest import OWNER


def setup(gate, requester=OWNER, **over):
    """Return (tool_id, contract, b4_decision, b4_proposal, head, quality, cert)
    for a clean admitted pure-read tool with a B4 ALLOWED decision."""
    tid, contract, d = gate.b4_decision(requester=requester, **over)
    tenant = gate.tid
    pobj = gate.app.state.guardrail_store.proposal(d["proposal_id"],
                                                   tenant_id=tenant)
    head = gate.app.state.tool_store.payload(tid, tenant_id=tenant)
    quality = gate.app.state.quality_store.latest(tid, tenant_id=tenant)
    projs = gate.app.state.contract_store.projections_for(
        contract["contract_id"], tenant_id=tenant)
    cert = projs[-1]["broker_readiness_certificate"] if projs else None
    return tid, contract, d, pobj, head, quality, cert


def make_env(gate, d, pobj, broker_request_id="br1", actor_id="u",
             actor_type="human", **over):
    kw = dict(broker_request_id=broker_request_id, tenant_id=gate.tid,
              actor_id=actor_id, actor_type=actor_type, b4_decision=d,
              b4_proposal=pobj, batch_id="", task_id="", case_id="",
              customer_id="", created_at="T")
    kw.update(over)
    return b.build_broker_request_envelope(**kw)


def prepare(gate, d, pobj, head, quality, contract, cert, env=None,
            broker_request_id="br1", actor_id="u", actor_type="human",
            created_at="T", **over):
    """Build an envelope (if not supplied) and prepare a null broker outcome."""
    if env is None:
        env = make_env(gate, d, pobj, broker_request_id=broker_request_id)
    kw = dict(broker_request_id=broker_request_id, tenant_id=gate.tid,
              actor_id=actor_id, actor_type=actor_type, envelope=env,
              b4_decision=d, b4_proposal=pobj, head=head, quality_report=quality,
              contract=contract, broker_readiness=cert, created_at=created_at)
    kw.update(over)
    return b.prepare_broker_outcome(**kw)


def clean_outcome(gate, **over):
    """One-shot: full clean setup -> prepared outcome."""
    tid, contract, d, pobj, head, quality, cert = setup(gate)
    return prepare(gate, d, pobj, head, quality, contract, cert, **over)

"""Shared (non-collected) helpers for TOOL-B7 transaction-escrow write-intent
draft runtime tests.

Leading underscore -> not collected by pytest. Builds a real B6 read-path
runtime outcome through the live app, and exposes wrappers to drive the kernel
(finalis.ai_employee.tool_write_intent) directly with deterministic inputs.

Two layers:
- kernel layer: `setup`/`prepare`/`clean_outcome` drive prepare_write_intent_
  outcome directly (fast, no HTTP), for hash/dominance/logic tests.
- api layer: use the `gate` conftest helpers (`prepared_write_intent`, `wi`,
  `write_intent`, `b6_runtime_outcome`) for endpoint/RBAC/persistence tests.
"""
from finalis.ai_employee import tool_write_intent as wi
from tests import _b6_kernel as _b6


def b6_outcome(gate, **b6_over):
    """A clean B6 read-only runtime outcome (RUNTIME_READ_ONLY_COMPLETED)."""
    b5, b5_request, snapshot = _b6.setup(gate)
    return _b6.prepare(gate, b5, b5_request, snapshot, **b6_over)


def make_env(gate, b6, write_intent_id="wi1", actor_id="u", actor_type="human",
             target_entity=None, proposed_deltas=None, intent="update"):
    return wi.build_write_intent_request_envelope(
        write_intent_id=write_intent_id, tenant_id=gate.tid, actor_id=actor_id,
        actor_type=actor_type, b6_outcome=b6,
        target_entity=target_entity or {"entity_type": "case",
                                        "entity_id": "E-1"},
        requested_deltas=proposed_deltas, intent=intent, created_at="T")


def _clean_kwargs(gate, b6, write_intent_id="wi1", actor_id="u",
                  actor_type="human"):
    return dict(
        write_intent_id=write_intent_id, tenant_id=gate.tid, actor_id=actor_id,
        actor_type=actor_type, b6_outcome=b6, created_at="T",
        requester_id="mgr",
        state_witnesses=[{"witness_class": "SOURCE_STATE_HASH",
                          "witness_hash": "sw-h", "epoch": 1}])


def prepare(gate, b6, env=None, approve=True, write_intent_id="wi1",
            actor_id="u", actor_type="human", **over):
    """Prepare a draft-only escrowed write-intent outcome directly on the kernel.

    approve=True runs the deterministic 2-phase flow so the clean path reaches
    TRANSACTION_ESCROW_DRAFT_CREATED: prepare once to read the content-addressed
    review digest, then re-prepare with an independent server-verified approval
    that viewed exactly that content. Override any kernel kwarg as a keyword."""
    if env is None:
        env = make_env(gate, b6, write_intent_id=write_intent_id)
    kw = _clean_kwargs(gate, b6, write_intent_id=write_intent_id,
                       actor_id=actor_id, actor_type=actor_type)
    kw["envelope"] = env
    kw.update(over)
    if not approve:
        return wi.prepare_write_intent_outcome(**kw)
    probe = wi.prepare_write_intent_outcome(**kw)
    digest = probe["review_package"]["review_content_digest"]
    if "approvals" not in kw:
        kw["approvals"] = [{
            "approver_id": "reviewer2", "approver_role": "owner",
            "server_verified": True, "challenge_passed": True,
            "viewed_package_hash": digest,
            "acknowledgements": {"ACK_DRAFT_ONLY_NO_EXECUTION": True,
                                 "ACK_FUTURE_COMMIT_SEPARATE": True,
                                 "ACK_ESCROW_NON_EXECUTING": True,
                                 "ACK_REVIEWED_SHADOW_DELTAS": True}}]
    return wi.prepare_write_intent_outcome(**kw)


def clean_outcome(gate, **over):
    """A clean TRANSACTION_ESCROW_DRAFT_CREATED outcome via the kernel."""
    return prepare(gate, b6_outcome(gate), **over)


def approval_for(outcome):
    """Build an independent, server-verified approval that viewed the content
    digest of the given (probe) outcome — for re-preparing the same draft."""
    digest = outcome["review_package"]["review_content_digest"]
    return [{"approver_id": "reviewer2", "approver_role": "owner",
             "server_verified": True, "challenge_passed": True,
             "viewed_package_hash": digest,
             "acknowledgements": {"ACK_DRAFT_ONLY_NO_EXECUTION": True,
                                  "ACK_FUTURE_COMMIT_SEPARATE": True,
                                  "ACK_ESCROW_NON_EXECUTING": True,
                                  "ACK_REVIEWED_SHADOW_DELTAS": True}}]

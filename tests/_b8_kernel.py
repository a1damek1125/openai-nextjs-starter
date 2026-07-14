"""Shared (non-collected) helpers for TOOL-B8 machine-checkable pre-B9
assurance / local commit-simulation kernel tests.

Leading underscore -> not collected by pytest. Builds a real B7 transaction-
escrow write-intent draft outcome through the live app, then exposes wrappers to
drive the kernel (finalis.ai_employee.tool_commit_simulation) directly with
deterministic inputs.

Two layers:
- kernel layer: `b7_outcome`/`prepare`/`clean_outcome` drive
  prepare_commit_simulation_outcome directly (fast, no HTTP).
- api layer: use the `gate` conftest helpers (`prepared_commit_simulation`,
  `commit_simulation`, `cs`, `b7_write_intent_outcome`).
"""
from finalis.ai_employee import tool_commit_simulation as cs
from tests import _b7_kernel as _b7


def b7_outcome(gate, **b7_over):
    """A clean B7 TRANSACTION_ESCROW_DRAFT_CREATED outcome (ready_for_future_
    commit_only)."""
    return _b7.prepare(gate, _b7.b6_outcome(gate), approve=True, **b7_over)


def make_env(gate, b7, commit_simulation_id="cs1", actor_id="u",
             actor_type="human"):
    return cs.build_commit_simulation_request_envelope(
        commit_simulation_id=commit_simulation_id, tenant_id=gate.tid,
        actor_id=actor_id, actor_type=actor_type, b7_outcome=b7, created_at="T")


def prepare(gate, b7, env=None, commit_simulation_id="cs1", actor_id="u",
            actor_type="human", **over):
    """Prepare a simulation-only pre-B9 assurance outcome directly on the
    kernel. Clean defaults yield B8_V5_ACCEPTED. Override any kernel kwarg as a
    keyword to trigger a blocker."""
    if env is None:
        env = make_env(gate, b7, commit_simulation_id=commit_simulation_id)
    return cs.prepare_commit_simulation_outcome(
        commit_simulation_id=commit_simulation_id, tenant_id=gate.tid,
        actor_id=actor_id, actor_type=actor_type, envelope=env, b7_outcome=b7,
        created_at="T", **over)


def clean_outcome(gate, **over):
    """A clean B8_V5_ACCEPTED outcome via the kernel (single B7 build)."""
    return prepare(gate, b7_outcome(gate), **over)

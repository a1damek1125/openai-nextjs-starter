"""Shared (non-collected) helpers for TOOL-B9.2 v5 Governed Work Lineage
Observatory kernel tests.

Leading underscore -> not collected by pytest. Builds a real clean B9 transaction
outcome (and optionally a B9.1 recovery outcome) via the B9/B9.1 kernels, then
drives the work-observability kernel (finalis.ai_employee.tool_work_observability)
directly with deterministic inputs. B9/B9.1 outcomes are EVIDENCE ONLY; the
observatory is read-only and grants no authority.

Two layers:
- kernel layer: `clean_b9`/`clean_b91`/`prepare`/`clean_outcome` drive
  prepare_work_observation_outcome directly (fast, no HTTP). Clean defaults over a
  committed B9 transaction certify the run (WORK_OUTCOME_CERTIFIED / PROVEN /
  PoWO valid). Override any kernel kwarg to degrade the truth state.
- api layer: use the `gate` conftest helpers (`observed_work`, `observe_work`,
  `wo`, `clean_work_body`).
"""
from finalis.ai_employee import tool_work_observability as wo
from tests import _b9_kernel as _b9
from tests import _b91_kernel as _b91


def clean_b9(**b9_over):
    """A clean B9_LOCAL_COMMIT_APPLIED outcome to observe over (evidence only)."""
    return _b9.clean_outcome(**b9_over)


def clean_b91(**b91_over):
    """A clean B9.1 recovery outcome to observe over (evidence only)."""
    return _b91.clean_outcome(desired_recovery_action="RECOVER", **b91_over)


def _clean_ctx(**over):
    ctx = {"source_principal_id": "user:1", "effective_principal_id": "user:1",
           "artifacts": [{"id": "a1", "type": "REPORT", "sources": ["s1"],
                          "content": "x"}],
           "delivery_status": "LOCAL_INTENT_ONLY"}
    ctx.update(over)
    return ctx


def prepare(work_run_id="wr-1", tenant_id="t1", actor_id="u1",
            actor_type="human", b9_outcome=None, b91_outcome=None,
            created_at="T", bind_b9=True, bind_b91=False, **over):
    """Prepare a work-observation outcome directly on the kernel. Clean defaults
    (with a bound clean B9 transaction) certify the run. Override any kernel
    kwarg (source_principal_id=, memory_facts=, approved_action=,
    secret_exposed_to_model=, schedule_revoked=, ...) to degrade the truth
    state. Pass bind_b9=False to observe with no bound transaction."""
    if b9_outcome is None and bind_b9:
        b9_outcome = clean_b9()
    if b91_outcome is None and bind_b91:
        b91_outcome = clean_b91()
    ctx = _clean_ctx(**over)
    return wo.prepare_work_observation_outcome(
        work_run_id=work_run_id, tenant_id=tenant_id, actor_id=actor_id,
        actor_type=actor_type, b9_outcome=b9_outcome, b91_outcome=b91_outcome,
        created_at=created_at, **ctx)


def clean_outcome(**over):
    """A clean WORK_OUTCOME_CERTIFIED / PROVEN outcome via the kernel."""
    return prepare(**over)

"""Shared (non-collected) helpers for TOOL-B9.1 v4 Recovery Safety Case +
Chaos Sentinel + Proof-of-Recovery runtime kernel tests.

Leading underscore -> not collected by pytest. Builds a real clean B9
transaction outcome via tests._b9_kernel, then drives the recovery kernel
(finalis.ai_employee.tool_local_recovery) directly with deterministic inputs.
The B9 outcome is EVIDENCE ONLY; the recovery kernel recomputes every factor.

Two layers:
- kernel layer: `clean_b9`/`prepare`/`clean_outcome` drive
  prepare_recovery_outcome directly (fast, no HTTP). Clean defaults over a
  committed B9 transaction yield a clean recovery evaluation (no external effect,
  inert outbox preserved, safety monotonicity + double-entry reconciliation
  hold). Override any kernel kwarg to trigger a specific fail-closed state.
- api layer: use the `gate` conftest helpers (`committed_local_tx`,
  `prepared_recovery`, `recover`, `rc`).
"""
from finalis.ai_employee import tool_local_recovery as lr
from tests import _b9_kernel as _b9


def clean_b9(**b9_over):
    """A clean B9_LOCAL_COMMIT_APPLIED outcome to recover over (evidence only)."""
    return _b9.clean_outcome(**b9_over)


def prepare(recovery_id="rec-1", tenant_id="t1", actor_id="u1",
            actor_type="human", b9_outcome=None,
            desired_recovery_action="RECOVER", created_at="T", **over):
    """Prepare a recovery outcome directly on the kernel. Clean defaults yield a
    clean recovery (final_recovery_state depends on the action: RECOVER ->
    RECOVERED, PLAN -> RECOVERY_PLANNED, ROLLBACK_LOCAL -> ROLLBACK_APPLIED_LOCAL,
    STATUS -> CLEAN). Override any kernel kwarg (recovery_authority_basis=,
    kill_switch=, poe_tamper=, rollback_equivalence_fail=, ...) to trigger a
    specific fail-closed state."""
    if b9_outcome is None:
        b9_outcome = clean_b9()
    return lr.prepare_recovery_outcome(
        recovery_id=recovery_id, transaction_id=b9_outcome["transaction_id"],
        tenant_id=b9_outcome["tenant_id"], actor_id=actor_id,
        actor_type=actor_type, b9_outcome=b9_outcome,
        desired_recovery_action=desired_recovery_action, created_at=created_at,
        **over)


def clean_outcome(desired_recovery_action="RECOVER", **over):
    """A clean recovery outcome via the kernel (single B9 build)."""
    return prepare(desired_recovery_action=desired_recovery_action, **over)

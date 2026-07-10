"""Shared (non-collected) helpers for TOOL-B9 v5 Finalis Transaction Twin +
Proof-of-Execution runtime kernel tests.

Leading underscore -> not collected by pytest. Drives the kernel
(finalis.ai_employee.tool_local_transaction) directly with deterministic inputs.
B8 is EVIDENCE ONLY: `clean_b8()` returns a minimal accepted B8 evidence dict;
the kernel must still recompute every factor and grant no authority from it.

Two layers:
- kernel layer: `clean_b8`/`prepare`/`clean_outcome` drive
  prepare_local_transaction_outcome directly (fast, no HTTP). Clean defaults
  yield B9_LOCAL_COMMIT_APPLIED (a local, reversible internal commit; NO
  external effect). Override any kernel kwarg as a keyword to trigger a blocker.
- api layer: use the `gate` conftest helpers (`prepared_local_tx`, `local_tx`,
  `b8_accepted_outcome`, `clean_local_tx_body`, `lt`).
"""
from finalis.ai_employee import tool_local_transaction as lt


def clean_b8(tenant_id="t1", commit_simulation_id="cs1"):
    """A minimal accepted B8 evidence dict — evidence ONLY. The kernel treats
    it as EVIDENCE_ONLY and revalidates every factor; it grants no authority,
    approval, commit-lease, B9-activation, or provider-permission."""
    return {
        "commit_simulation_id": commit_simulation_id, "tenant_id": tenant_id,
        "commit_simulation_status": "B8_V5_ACCEPTED",
        "commit_executable_now": False, "production_ready": False,
        "assurance_envelope": {"is_authority": False, "authorizes_b9": False,
                               "decision_status": "VALID"},
    }


def prepare(transaction_id="tx1", tenant_id="t1", actor_id="u1",
            actor_type="human", b8_outcome=None, created_at="T", **over):
    """Prepare a Finalis Transaction Twin outcome directly on the kernel. Clean
    defaults yield B9_LOCAL_COMMIT_APPLIED. Override any kernel kwarg (e.g.
    source_surface=, authority_basis=, planned_delta=, allowed_local_scope=) to
    trigger a specific blocker/quarantine."""
    if b8_outcome is None:
        b8_outcome = clean_b8(tenant_id=tenant_id)
    return lt.prepare_local_transaction_outcome(
        transaction_id=transaction_id, tenant_id=tenant_id, actor_id=actor_id,
        actor_type=actor_type, b8_outcome=b8_outcome, created_at=created_at,
        **over)


def clean_outcome(**over):
    """A clean B9_LOCAL_COMMIT_APPLIED outcome via the kernel."""
    return prepare(**over)

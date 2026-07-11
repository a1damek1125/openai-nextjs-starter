"""Shared (non-collected) helpers for EMP-A1 v1 Employee Work Inbox (R-FSAFEQ
Governed Work Admission Fabric) kernel tests.

Leading underscore -> not collected by pytest. Drives the PURE reference kernel
(finalis.ai_employee.employee_work_inbox.evaluate_admission) directly with
deterministic snapshot/request/policy inputs — no I/O, no clock, no randomness.

Two layers:
- kernel layer: `req`/`evaluate`/`clean` build a canonical request and call
  evaluate_admission over an (optionally seeded) immutable snapshot. Clean
  defaults yield disposition ADMIT_READY (resulting_state READY). Override any
  request field to drive a specific disposition.
- api layer: use the `gate` conftest helpers (`clean_work_intake`,
  `submit_work`, `admitted_work`, `wi`, `ready_to_handoff`).
"""
from finalis.ai_employee import employee_work_inbox as wi


def req(**over):
    """A minimal admissible canonical request (portal-manual case_summary over a
    case target). Override any field to drive a disposition."""
    base = {
        "tenant_id": "t1", "source_type": "PORTAL_MANUAL",
        "source_surface": "WEB_PORTAL", "source_schema_version": "1",
        "source_principal_id": "user:1", "authenticated_principal_id": "user:1",
        "principal_active": True, "work_type": "case_summary",
        "requested_target_refs": ["case:E-1"],
        "canonical_parameters": {"target": "case:E-1"},
        "idempotency_key": "idem-1", "raw_payload": {"note": "summarize"},
    }
    base.update(over)
    return base


def evaluate(snapshot=None, policy=None, **over):
    """Evaluate a canonical request over a snapshot via the pure reference
    kernel. Clean defaults -> disposition ADMIT_READY."""
    snap = snapshot if snapshot is not None else {"tenant_id": "t1"}
    return wi.evaluate_admission(snap, req(**over), policy or {})


def clean(**over):
    """A clean ADMIT_READY reference decision."""
    return evaluate(**over)

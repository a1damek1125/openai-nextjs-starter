"""Shared (non-collected) helpers for TOOL-B6 read-path runtime kernel tests.

Leading underscore -> not collected by pytest. Builds a real B5 broker outcome
through the live app + a frozen snapshot, and exposes wrappers to drive the
kernel (finalis.ai_employee.tool_runtime) directly.
"""
from finalis.ai_employee import tool_runtime as rt
from tests import _b5_kernel as _b5
from tests.conftest import OWNER


def clean_fields():
    return {"case_id": {"value": "C-1", "data_class": "PUBLIC"},
            "status": {"value": "open", "data_class": "PUBLIC"},
            "ssn": {"value": "999-99-9999", "data_class": "CUSTOMER_SENSITIVE"}}


def setup(gate, requester=OWNER, epoch="5", fields=None, **b5_over):
    """Return (b5_outcome, b5_request, snapshot) with a clean B5 outcome and a
    frozen snapshot (2 PUBLIC + 1 CUSTOMER_SENSITIVE field by default)."""
    b5 = _b5.clean_outcome(gate, **b5_over)
    b5_request = {"broker_request_id": b5["broker_request_id"]}
    snapshot = rt.build_snapshot(
        snapshot_id="snap1", tenant_id=gate.tid, epoch=epoch, scope="case",
        fields=fields if fields is not None else clean_fields())
    return b5, b5_request, snapshot


def make_env(gate, b5, snapshot, runtime_request_id="rt1", actor_id="u",
             actor_type="human", requested_sources=None,
             requested_projection=None, requested_epoch=None):
    return rt.build_runtime_request_envelope(
        runtime_request_id=runtime_request_id, tenant_id=gate.tid,
        actor_id=actor_id, actor_type=actor_type, b5_outcome=b5,
        adapter_id="adp", snapshot=snapshot,
        requested_sources=requested_sources if requested_sources is not None
        else ["case_id", "status"],
        requested_projection=requested_projection if requested_projection
        is not None else ["case_id", "status"],
        requested_epoch=requested_epoch if requested_epoch is not None else
        (snapshot or {}).get("epoch"), created_at="T")


def prepare(gate, b5, b5_request, snapshot, env=None, runtime_request_id="rt1",
            actor_id="u", actor_type="human", **over):
    """Build an envelope (if needed) and prepare a read-only runtime outcome.
    Clean defaults: field_projection adapter over the two PUBLIC fields.
    Override any core object POSITIONALLY (b5/b5_request/snapshot); pass kernel
    kwargs (adapter_kind=, adapter_caps=, requested_sources=, policy=, ...) as
    keywords."""
    if env is None:
        env = make_env(gate, b5, snapshot,
                       runtime_request_id=runtime_request_id)
    kw = dict(runtime_request_id=runtime_request_id, tenant_id=gate.tid,
              actor_id=actor_id, actor_type=actor_type, envelope=env,
              b5_outcome=b5, b5_request=b5_request, snapshot=snapshot,
              adapter_id="adp", adapter_kind="field_projection",
              allowed_sources=["case_id", "status"],
              allowed_projection=["case_id", "status"],
              requested_sources=["case_id", "status"],
              requested_projection=["case_id", "status"],
              requested_epoch=(snapshot or {}).get("epoch"), created_at="T")
    kw.update(over)
    return rt.prepare_runtime_outcome(**kw)


def clean_outcome(gate, **over):
    b5, b5_request, snapshot = setup(gate)
    return prepare(gate, b5, b5_request, snapshot, **over)

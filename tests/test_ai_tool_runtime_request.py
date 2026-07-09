"""TOOL-B6: runtime request envelope + snapshot sealing (build_runtime_request_envelope).

Verifies the read-only runtime request envelope seals its B5 references,
snapshot hash and requested read plan, is unambiguously read-only/local/non-
external, and that canonical hashing rejects non-finite snapshot values.
"""
import re

import pytest

from finalis.ai_employee import tool_runtime as rt
from tests import _b6_kernel as k


_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def test_envelope_seals_b5_references(gate):
    b5, b5r, snap = k.setup(gate)
    env = k.make_env(gate, b5, snap)
    assert env["b5_broker_request_id"] == b5["broker_request_id"]
    assert env["b5_broker_decision_hash"] == b5.get("broker_decision_hash")


def test_envelope_seals_snapshot_hash(gate):
    b5, b5r, snap = k.setup(gate)
    env = k.make_env(gate, b5, snap)
    assert env["snapshot_id"] == snap["snapshot_id"]
    assert env["snapshot_hash"] == snap["snapshot_hash"]


def test_envelope_seals_requested_epoch(gate):
    b5, b5r, snap = k.setup(gate, epoch="5")
    env = k.make_env(gate, b5, snap)
    assert env["requested_epoch"] == "5" == snap["epoch"]


def test_envelope_seals_requested_sources_and_projection(gate):
    b5, b5r, snap = k.setup(gate)
    env = k.make_env(gate, b5, snap)
    assert env["requested_sources"] == ["case_id", "status"]
    assert env["requested_projection"] == ["case_id", "status"]


def test_envelope_is_read_only_local_only_non_external(gate):
    b5, b5r, snap = k.setup(gate)
    env = k.make_env(gate, b5, snap)
    assert env["is_write"] is False
    assert env["is_external"] is False
    assert env["read_only_local_only"] is True


def test_envelope_runtime_request_hash_present(gate):
    b5, b5r, snap = k.setup(gate)
    env = k.make_env(gate, b5, snap)
    assert "runtime_request_hash" in env
    assert _HEX64.match(env["runtime_request_hash"])


def test_envelope_hash_excludes_request_id_and_created_at(gate):
    b5, b5r, snap = k.setup(gate)
    env1 = rt.build_runtime_request_envelope(
        runtime_request_id="rtA", tenant_id=gate.tid, actor_id="u",
        actor_type="human", b5_outcome=b5, adapter_id="adp", snapshot=snap,
        requested_sources=["case_id", "status"],
        requested_projection=["case_id", "status"],
        requested_epoch=snap["epoch"], created_at="T1")
    env2 = rt.build_runtime_request_envelope(
        runtime_request_id="rtB", tenant_id=gate.tid, actor_id="u",
        actor_type="human", b5_outcome=b5, adapter_id="adp", snapshot=snap,
        requested_sources=["case_id", "status"],
        requested_projection=["case_id", "status"],
        requested_epoch=snap["epoch"], created_at="T2")
    # runtime_request_id and created_at are excluded from the request hash.
    assert env1["runtime_request_hash"] == env2["runtime_request_hash"]


def test_snapshot_nan_value_raises_value_error(gate):
    # canonical_json is allow_nan=False; a non-finite field value fails closed.
    with pytest.raises(ValueError):
        rt.build_snapshot(
            snapshot_id="snapNaN", tenant_id=gate.tid, epoch="5", scope="case",
            fields={"amount": {"value": float("nan"), "data_class": "PUBLIC"}})

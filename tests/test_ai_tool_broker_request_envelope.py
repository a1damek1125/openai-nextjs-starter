"""TOOL-B5 null broker: request envelope sealing + reference binding."""
import pytest

from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k


def test_envelope_open_seal_captures_reference_hashes(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = k.make_env(gate, d, pobj, broker_request_id="brenv1")
    seal = env["broker_open_seal"]
    for key in ("b4_decision_hash", "b4_receipt_hash", "payload_hash",
                "action_path_hash", "b4_causal_graph_hash",
                "source_freshness_epoch"):
        assert key in seal


def test_envelope_seal_binds_actual_b4_hashes(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = k.make_env(gate, d, pobj, broker_request_id="brenv2")
    seal = env["broker_open_seal"]
    assert seal["b4_decision_hash"] == d.get("decision_hash")
    assert seal["b4_receipt_hash"] == (
        d.get("governance_receipt") or {}).get("governance_receipt_hash")
    assert seal["b4_causal_graph_hash"] == (
        d.get("causal_action_graph") or {}).get("causal_action_graph_hash")
    assert seal["payload_hash"] == b._sha(pobj.get("payload", {}))


def test_envelope_is_not_execution_not_dry_run(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = k.make_env(gate, d, pobj, broker_request_id="brenv3")
    assert env["is_execution"] is False
    assert env["is_dry_run"] is False
    assert env["requests_null_broker_only"] is True


def test_envelope_has_request_hash(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = k.make_env(gate, d, pobj, broker_request_id="brenv4")
    assert env.get("broker_request_hash")
    # Hash excludes itself (recomputable).
    assert env["broker_request_hash"] == b._core_hash(env, "broker_request_hash")


def test_envelope_binds_referenced_b4_decision(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = k.make_env(gate, d, pobj, broker_request_id="brenv5")
    assert env["broker_open_seal"]["b4_decision_id"] == d["decision_id"]
    assert env["broker_open_seal"]["b4_decision_status"] == d["decision_status"]
    assert env["b4_proposal_id"] == d["proposal_id"]


def test_envelope_binds_tool_and_contract(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = k.make_env(gate, d, pobj, broker_request_id="brenv6")
    assert env["tool_id"] == d.get("tool_id")
    assert env["contract_id"] == d.get("contract_id")
    assert env["tenant_id"] == gate.tid


def test_envelope_binds_proposal_payload_and_action_path(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    env = k.make_env(gate, d, pobj, broker_request_id="brenv7")
    seal = env["broker_open_seal"]
    assert seal["payload_hash"] == b._sha(pobj.get("payload", {}))
    assert seal["action_path_hash"] == b._sha(
        b._norm(pobj.get("action_path", "")))


def test_envelope_rejects_nan_payload_via_canonical_json(gate):
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    bad = dict(pobj)
    bad["payload"] = {**dict(pobj.get("payload") or {}), "corrupt": float("nan")}
    with pytest.raises(ValueError):
        k.make_env(gate, d, bad, broker_request_id="brenv8")

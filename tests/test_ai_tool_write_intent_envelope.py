"""TOOL-B7 write-intent request envelope: draft-only framing, B6 binding and
content-deterministic request hash."""
from finalis.ai_employee import tool_write_intent as wi
from tests import _b7_kernel as k


def _env(gate, b6, write_intent_id="wi1", actor_id="u", actor_type="human",
         target_entity=None, deltas=None, intent="update", created_at="T"):
    return wi.build_write_intent_request_envelope(
        write_intent_id=write_intent_id, tenant_id=gate.tid, actor_id=actor_id,
        actor_type=actor_type, b6_outcome=b6,
        target_entity=target_entity or {"entity_type": "case",
                                        "entity_id": "E-1"},
        requested_deltas=deltas or [{"field_path": "status"}], intent=intent,
        created_at=created_at)


def test_envelope_is_never_write_commit_or_execution(gate):
    env = _env(gate, k.b6_outcome(gate))
    assert env["is_write"] is False
    assert env["is_commit"] is False
    assert env["is_execution"] is False
    assert env["draft_only"] is True


def test_envelope_binds_b6_request_id(gate):
    b6 = k.b6_outcome(gate)
    env = _env(gate, b6)
    assert env["b6_runtime_request_id"] == b6.get("runtime_request_id")


def test_envelope_binds_b6_decision_hash(gate):
    b6 = k.b6_outcome(gate)
    env = _env(gate, b6)
    assert env["b6_runtime_decision_hash"] == b6.get("runtime_decision_hash")


def test_envelope_binds_b6_proof_bundle_hash(gate):
    b6 = k.b6_outcome(gate)
    env = _env(gate, b6)
    assert env["b6_proof_bundle_hash"] == \
        (b6.get("runtime_proof_bundle") or {}).get("runtime_proof_bundle_hash")


def test_request_hash_excludes_write_intent_id(gate):
    b6 = k.b6_outcome(gate)
    a = _env(gate, b6, write_intent_id="wiA")
    b = _env(gate, b6, write_intent_id="wiB")
    assert a["write_intent_request_hash"] == b["write_intent_request_hash"]


def test_request_hash_excludes_actor_identity(gate):
    b6 = k.b6_outcome(gate)
    a = _env(gate, b6, actor_id="alice", actor_type="human")
    b = _env(gate, b6, actor_id="bob", actor_type="service")
    assert a["write_intent_request_hash"] == b["write_intent_request_hash"]


def test_request_hash_excludes_created_at(gate):
    b6 = k.b6_outcome(gate)
    a = _env(gate, b6, created_at="T1")
    b = _env(gate, b6, created_at="T2")
    assert a["write_intent_request_hash"] == b["write_intent_request_hash"]


def test_request_hash_content_deterministic(gate):
    b6 = k.b6_outcome(gate)
    a = _env(gate, b6, write_intent_id="wiA", actor_id="alice", created_at="T1")
    b = _env(gate, b6, write_intent_id="wiB", actor_id="bob", created_at="T2")
    assert a["write_intent_request_hash"] == b["write_intent_request_hash"]


def test_request_hash_depends_on_target(gate):
    b6 = k.b6_outcome(gate)
    a = _env(gate, b6, target_entity={"entity_type": "case", "entity_id": "E-1"})
    b = _env(gate, b6, target_entity={"entity_type": "deal", "entity_id": "E-9"})
    assert a["write_intent_request_hash"] != b["write_intent_request_hash"]


def test_request_hash_depends_on_deltas(gate):
    b6 = k.b6_outcome(gate)
    a = _env(gate, b6, deltas=[{"field_path": "status"}])
    b = _env(gate, b6, deltas=[{"field_path": "amount"}])
    assert a["write_intent_request_hash"] != b["write_intent_request_hash"]


def test_request_hash_depends_on_intent(gate):
    b6 = k.b6_outcome(gate)
    a = _env(gate, b6, intent="close the case")
    b = _env(gate, b6, intent="reopen the case")
    assert a["write_intent_request_hash"] != b["write_intent_request_hash"]


def test_envelope_version_stamped(gate):
    env = _env(gate, k.b6_outcome(gate))
    assert env["write_intent_request_envelope_version"] == wi.REQUEST_VERSION

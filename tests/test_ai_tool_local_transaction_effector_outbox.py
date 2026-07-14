"""TOOL-B9 v5: effector-exclusive local gate + inert effect outbox. Only the
effector may apply local, reversible state, and it holds a single-writer lock;
a lock held by another transaction => B9_CONFLICT/EFFECTOR_LOCK_HELD. The outbox
is INERT and NEVER releases: no item is ever marked released, no provider is
called, no delivery attempted; any release attempt =>
B9_QUARANTINED/OUTBOX_RELEASE_ATTEMPT.
"""
from finalis.ai_employee.tool_local_transaction import _core_hash
from tests import _b9_kernel as k


# --- kernel layer: effector-exclusive gate ---------------------------------
def test_eo_clean_effector_gate_open():
    eg = k.clean_outcome()["effector_gate"]
    assert eg["gate_status"] == "OPEN"
    assert eg["single_writer"] is True
    assert eg["lock_acquired"] is True
    assert eg["signal"] is None


def test_eo_clean_effector_gate_no_conflict_no_replay():
    eg = k.clean_outcome()["effector_gate"]
    assert eg["conflicting_transaction_ids"] == []
    assert eg["replay_detected"] is False
    assert eg["idempotency_mismatch"] is False
    assert eg["stale_before_state"] is False


def test_eo_lock_held_by_other_tx_conflicts():
    o = k.prepare(lock_held_by="other-tx")
    assert o["b9_status"] == "B9_CONFLICT"
    assert o["dominant_signal"] == "EFFECTOR_LOCK_HELD"
    assert o["local_commit_applied"] is False
    eg = o["effector_gate"]
    assert eg["gate_status"] == "BLOCKED"
    assert eg["lock_acquired"] is False


def test_eo_conflicting_tx_detected():
    o = k.prepare(conflicting_txs=[{"transaction_id": "other",
                                    "tenant_id": "t1",
                                    "object_reference": "obj-1"}])
    assert o["b9_status"] == "B9_CONFLICT"
    assert o["dominant_signal"] == "CONFLICT_DETECTED"
    assert "other" in o["effector_gate"]["conflicting_transaction_ids"]


def test_eo_replay_detected_conflicts():
    o = k.prepare(replay_detected=True)
    assert o["b9_status"] == "B9_CONFLICT"
    assert o["dominant_signal"] == "REPLAY_DETECTED"
    assert o["effector_gate"]["replay_detected"] is True


def test_eo_effector_gate_hash_recomputes():
    eg = k.clean_outcome()["effector_gate"]
    assert _core_hash(eg, "effector_gate_hash", "signal") == eg[
        "effector_gate_hash"]


def test_eo_locked_effector_gate_hash_recomputes():
    eg = k.prepare(lock_held_by="other-tx")["effector_gate"]
    assert _core_hash(eg, "effector_gate_hash", "signal") == eg[
        "effector_gate_hash"]


def test_eo_lock_conflict_changes_decision_hash():
    clean = k.prepare()["b9_decision_hash"]
    locked = k.prepare(lock_held_by="other-tx")["b9_decision_hash"]
    assert clean != locked


# --- kernel layer: inert effect outbox -------------------------------------
def test_eo_clean_inert_outbox_status():
    ob = k.clean_outcome()["inert_outbox"]
    assert ob["outbox_status"] == "INERT"
    assert ob["inert"] is True
    assert ob["signal"] is None


def test_eo_clean_inert_outbox_never_releases():
    ob = k.clean_outcome()["inert_outbox"]
    assert ob["any_released"] is False
    assert ob["any_provider_called"] is False
    assert ob["any_delivery_attempted"] is False
    assert ob["any_external_state_mutated"] is False
    assert ob["release_attempts_detected"] == 0


def test_eo_outbox_release_attempt_quarantined():
    o = k.prepare(outbox_release_attempts=1)
    assert o["b9_status"] == "B9_QUARANTINED"
    assert o["dominant_signal"] == "OUTBOX_RELEASE_ATTEMPT"
    assert o["local_commit_applied"] is False
    ob = o["inert_outbox"]
    assert ob["outbox_status"] == "RELEASE_ATTEMPT"
    assert ob["release_attempts_detected"] == 1


def test_eo_outbox_items_never_marked_released():
    o = k.prepare(outbox_release_attempts=1)
    ob = o["inert_outbox"]
    # even under a release attempt, individual items stay inert and unreleased
    assert ob["any_released"] is False
    for it in ob["items"]:
        assert it["released"] is False
        assert it["provider_called"] is False
        assert it["delivery_attempted"] is False
        assert it["external_effect"] is False
        assert it["external_state_mutated"] is False


def test_eo_inert_outbox_hash_recomputes():
    ob = k.clean_outcome()["inert_outbox"]
    assert _core_hash(ob, "inert_outbox_hash", "signal") == ob[
        "inert_outbox_hash"]


def test_eo_release_attempt_outbox_hash_recomputes():
    ob = k.prepare(outbox_release_attempts=1)["inert_outbox"]
    assert _core_hash(ob, "inert_outbox_hash", "signal") == ob[
        "inert_outbox_hash"]


def test_eo_outbox_release_produces_no_external_effect():
    o = k.prepare(outbox_release_attempts=1)
    assert o["produced_external_effect"] is False
    assert o["provider_called"] is False
    assert o["message_sent"] is False


# --- API layer -------------------------------------------------------------
def test_eo_api_effector_gate_endpoint(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.lt(tid, "/effector-gate")
    assert r.status_code == 200
    body = r.json()
    eg = body["effector_gate"]
    assert eg["gate_status"] == "OPEN"
    assert eg["single_writer"] is True
    assert body["honesty_labels"]


def test_eo_api_inert_outbox_endpoint(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.lt(tid, "/inert-outbox")
    assert r.status_code == 200
    body = r.json()
    ob = body["inert_outbox"]
    assert ob["outbox_status"] == "INERT"
    assert ob["any_released"] is False
    assert body["honesty_labels"]

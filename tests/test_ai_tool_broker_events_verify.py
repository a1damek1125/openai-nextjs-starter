"""TOOL-B5 event ledger + tamper-evident verification: hash-chained events,
per-request events, VALID/TAMPERED verification, and fault-injection re-run."""
import json

from tests.conftest import OWNER


def test_global_events_are_hash_chained(gate):
    gate.prepared_broker()
    gate.prepared_broker()
    ev = gate.c.get("/ai-tools/broker/events", headers=gate.h()).json()
    assert ev["event_chain_valid"] is True
    # Two requests -> at least 4 events (OPENED + PREPARED per request).
    assert ev["event_count"] >= 4
    types = [e["event_type"] for e in ev["events"]]
    assert "BROKER_REQUEST_OPENED" in types
    assert "BROKER_OUTCOME_PREPARED" in types


def test_request_events_scoped_to_request(gate):
    rid, _ = gate.prepared_broker()
    re = gate.br(rid, "/events").json()
    assert re["broker_request_id"] == rid
    types = [e["event_type"] for e in re["events"]]
    assert types == ["BROKER_REQUEST_OPENED", "BROKER_OUTCOME_PREPARED"]
    assert all(e["broker_request_id"] == rid for e in re["events"])


def test_verify_untampered_is_valid(gate):
    rid, _ = gate.prepared_broker()
    vr = gate.br(rid, "/verify", method="POST").json()
    assert vr["verification_status"] == "VALID"
    assert vr["broker_decision_hash_valid"] is True
    assert vr["stored_broker_decision_hash"] == vr[
        "recomputed_broker_decision_hash"]


def test_verify_detects_tampered_outcome(gate):
    rid, _ = gate.prepared_broker()
    row = gate.db.one(
        "SELECT payload_json FROM ai_broker_outcomes WHERE "
        "broker_request_id=?", rid)
    payload = json.loads(row["payload_json"])
    assert payload["broker_status"] == "BROKER_PREPARED_FOR_FUTURE_ONLY"
    # Tamper: forge a different broker_status in the stored payload.
    payload["broker_status"] = "BLOCKED"
    gate.db.conn.execute(
        "UPDATE ai_broker_outcomes SET payload_json=? WHERE "
        "broker_request_id=?", (json.dumps(payload), rid))
    gate.db.conn.commit()
    vr = gate.br(rid, "/verify", method="POST").json()
    assert vr["verification_status"] == "TAMPERED"
    assert vr["broker_decision_hash_valid"] is False


def test_fault_injection_check_passes_and_emits_event(gate):
    rid, _ = gate.prepared_broker()
    before = gate.c.get("/ai-tools/broker/events",
                        headers=gate.h()).json()["event_count"]
    h = gate.br(rid, "/fault-injection-check", method="POST").json()
    assert h["harness_status"] == "FAULT_INJECTION_PASSED"
    assert h["unexpected_positive_results"] == []
    after = gate.c.get("/ai-tools/broker/events", headers=gate.h()).json()
    assert after["event_count"] == before + 1
    assert "BROKER_FAULT_INJECTED" in [e["event_type"] for e in after["events"]]


def test_fault_injected_event_is_scoped_to_request(gate):
    rid, _ = gate.prepared_broker()
    gate.br(rid, "/fault-injection-check", method="POST")
    re = gate.br(rid, "/events").json()
    types = [e["event_type"] for e in re["events"]]
    assert "BROKER_FAULT_INJECTED" in types
    # Chain stays valid after the extra event.
    ev = gate.c.get("/ai-tools/broker/events", headers=gate.h()).json()
    assert ev["event_chain_valid"] is True

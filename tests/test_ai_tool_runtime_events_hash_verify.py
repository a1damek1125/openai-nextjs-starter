"""TOOL-B6 read-path runtime: hash-chained event ledger + tamper verification."""
import json

from tests.conftest import OWNER


def test_event_chain_valid(gate):
    gate.prepared_runtime()
    ev = gate.c.get("/ai-tools/runtime/events", headers=gate.h()).json()
    assert ev["event_chain_valid"] is True
    assert ev["event_count"] >= 2


def test_per_request_events(gate):
    rid, _ = gate.prepared_runtime()
    r = gate.rt(rid, "/events")
    assert r.status_code == 200
    types = [e["event_type"] for e in r.json()["events"]]
    assert "RUNTIME_REQUEST_OPENED" in types
    assert "RUNTIME_OUTCOME_PREPARED" in types


def test_verify_untampered_valid(gate):
    rid, _ = gate.prepared_runtime()
    v = gate.rt(rid, "/verify", method="POST").json()
    assert v["verification_status"] == "VALID"
    assert v["runtime_decision_hash_valid"] is True


def test_verify_detects_tamper(gate):
    rid, _ = gate.prepared_runtime()
    row = gate.db.one(
        "SELECT id, payload_json FROM ai_runtime_outcomes WHERE "
        "runtime_request_id=?", rid)
    payload = json.loads(row["payload_json"])
    payload["runtime_status"] = "RUNTIME_BLOCKED"
    gate.db.update("ai_runtime_outcomes", row["id"],
                   {"payload_json": json.dumps(payload)})
    v = gate.rt(rid, "/verify", method="POST").json()
    assert v["verification_status"] == "TAMPERED"
    assert v["runtime_decision_hash_valid"] is False


def test_event_sequence_monotone(gate):
    gate.prepared_runtime()
    ev = gate.c.get("/ai-tools/runtime/events", headers=gate.h()).json()
    seqs = [e["sequence"] for e in ev["events"]]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)


def test_fault_injection_check_emits_event(gate):
    rid, _ = gate.prepared_runtime()
    h = gate.rt(rid, "/fault-injection-check", method="POST").json()
    assert h["harness_status"] == "FAULT_INJECTION_PASSED"
    ev = gate.c.get("/ai-tools/runtime/events", headers=gate.h()).json()
    assert any(e["event_type"] == "RUNTIME_FAULT_INJECTED"
               for e in ev["events"])


def test_event_chain_hash_links(gate):
    gate.prepared_runtime()
    evs = gate.c.get("/ai-tools/runtime/events",
                     headers=gate.h(OWNER)).json()["events"]
    prev = "0" * 64
    for e in evs:
        assert e["previous_event_hash"] == prev
        prev = e["event_hash"]

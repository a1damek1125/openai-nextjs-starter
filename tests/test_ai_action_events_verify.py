"""TOOL-B4: hash-chained decision event ledger + decision verification."""
import json

from tests.conftest import OWNER


def test_events_ledger_is_chained(gate):
    tool_id, contract = gate.preaction_tool()
    gate.propose(tool_id, contract, idempotency_key="a")
    gate.propose(tool_id, contract, idempotency_key="b")
    evs = gate.c.get("/ai-tools/actions/events", headers=gate.h()).json()
    assert evs["event_count"] == 2
    assert evs["event_chain_valid"] is True


def test_proposal_scoped_events(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.propose(tool_id, contract).json()
    pe = gate.pa(d["proposal_id"], "/events").json()
    assert pe["proposal_id"] == d["proposal_id"]
    assert len(pe["events"]) == 1
    assert pe["events"][0]["proposal_id"] == d["proposal_id"]


def test_verify_valid_for_untampered(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.propose(tool_id, contract).json()
    v = gate.pa(d["proposal_id"], "/verify", method="POST").json()
    assert v["verification_status"] == "VALID"
    assert v["decision_hash_valid"] is True
    assert v["stored_decision_hash"] == d["decision_hash"]


def test_verify_tampered_when_payload_altered(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.propose(tool_id, contract).json()
    pid = d["proposal_id"]
    # Tamper the stored decision content (not its recorded hash).
    row = gate.db.one(
        "SELECT id, payload_json FROM ai_action_decisions WHERE proposal_id=?",
        pid)
    payload = json.loads(row["payload_json"])
    payload["decision_status"] = "PREACTION_DENIED"
    gate.db.conn.execute(
        "UPDATE ai_action_decisions SET payload_json=? WHERE id=?",
        (json.dumps(payload), row["id"]))
    gate.db.conn.commit()
    v = gate.pa(pid, "/verify", method="POST").json()
    assert v["verification_status"] == "TAMPERED"
    assert v["decision_hash_valid"] is False


def test_reevaluate_returns_fresh_decision(gate):
    tool_id, contract = gate.preaction_tool()
    d = gate.propose(tool_id, contract).json()
    re = gate.pa(d["proposal_id"], "/reevaluate", actor=OWNER,
                 method="POST").json()
    assert re["decision_status"] == "PREACTION_ALLOWED_FOR_FUTURE_BROKER_ONLY"
    # a genuinely fresh render -> new proposal + decision ids. Re-rendering the
    # same idempotency key surfaces as an idempotent replay.
    assert re["decision_id"] != d["decision_id"]
    assert re["proposal_id"] != d["proposal_id"]
    assert re["is_replay"] is True

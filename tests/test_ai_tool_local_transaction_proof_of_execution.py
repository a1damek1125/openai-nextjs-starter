"""TOOL-B9 v5: proof-of-execution stream + proof-of-execution.

The Finalis Transaction Twin emits a hash-chained proof-of-execution stream of
every lifecycle event and a proof-of-execution that binds the stream, contract,
path-compliance and null-effect invariants. A missing event, a reordered event
or a tampered chain fails closed and NO local commit is applied. B8 is evidence
only and produces NO external effect.
"""
from finalis.ai_employee.tool_local_transaction import _core_hash
from finalis.ai_employee import tool_local_transaction as lt
from tests import _b9_kernel as k
from tests.conftest import OWNER


def _blocked(over, expected_status, expected_signal):
    o = k.prepare(**over)
    assert o["b9_status"] == expected_status
    assert o["dominant_signal"] == expected_signal
    assert o["local_commit_applied"] is False
    return o


# --- kernel layer ----------------------------------------------------------
def test_poe_clean_stream_is_complete_and_chained():
    poe = k.clean_outcome()["poe_stream"]
    assert poe["event_count"] == 19
    assert poe["required_event_count"] == 19
    assert poe["stream_status"] == "COMPLETE"
    assert poe["chain_valid"] is True
    assert poe["hash_chained"] is True
    assert poe["event_order_valid"] is True
    assert poe["missing_events"] == []
    assert poe["signal"] is None


def test_poe_stream_events_hash_chain_from_genesis():
    poe = k.clean_outcome()["poe_stream"]
    prev = lt.GENESIS
    for i, ev in enumerate(poe["events"]):
        assert ev["sequence"] == i
        assert ev["previous_event_hash"] == prev
        prev = ev["canonical_event_hash"]
    assert [e["event_type"] for e in poe["events"]] == lt.POE_EVENTS


def test_poe_stream_covers_every_required_event():
    poe = k.clean_outcome()["poe_stream"]
    assert {e["event_type"] for e in poe["events"]} == set(lt.POE_EVENTS)


def test_poe_missing_event_blocks_commit():
    o = _blocked({"missing_poe_events": ["LOCAL_COMMIT_APPLIED"]},
                 "B9_BLOCKED", "POE_STREAM_INCOMPLETE")
    assert "LOCAL_COMMIT_APPLIED" in o["poe_stream"]["missing_events"]
    assert o["poe_stream"]["stream_status"] == "INVALID"


def test_poe_reorder_blocks_commit():
    o = _blocked({"poe_reorder": True},
                 "B9_BLOCKED", "POE_EVENT_ORDER_INVALID")
    assert o["poe_stream"]["event_order_valid"] is False


def test_poe_tamper_marks_stream_tampered():
    o = _blocked({"poe_tamper": True}, "B9_TAMPERED", "POE_STREAM_TAMPERED")
    assert o["poe_stream"]["chain_valid"] is False


def test_poe_clean_proof_of_execution_is_valid():
    poe_proof = k.clean_outcome()["proof_of_execution"]
    assert poe_proof["proof_of_execution_valid"] is True
    assert poe_proof["proof_status"] == "VALID"
    assert poe_proof["signal"] is None


def test_poe_proof_factors_all_hold_on_clean():
    factors = k.clean_outcome()["proof_of_execution"]["factors"]
    assert all(factors.values())
    assert factors["event_stream_complete"] is True
    assert factors["event_order_valid"] is True
    assert factors["replayability_passed"] is True
    assert factors["null_effect_on_deny_passed"] is True


def test_poe_proof_binds_the_stream_hash():
    o = k.clean_outcome()
    assert o["proof_of_execution"]["poe_stream_hash"] == o["poe_stream"][
        "poe_stream_hash"]


def test_poe_stream_hash_recomputes_excluding_signal():
    poe = k.clean_outcome()["poe_stream"]
    assert _core_hash(poe, "poe_stream_hash", "signal") == poe[
        "poe_stream_hash"]


def test_poe_proof_of_execution_hash_recomputes():
    poe_proof = k.clean_outcome()["proof_of_execution"]
    assert _core_hash(poe_proof, "proof_of_execution_hash", "signal") == \
        poe_proof["proof_of_execution_hash"]


def test_poe_tamper_changes_decision_hash_vs_clean():
    clean = k.prepare()["b9_decision_hash"]
    tampered = k.prepare(poe_tamper=True)["b9_decision_hash"]
    assert clean != tampered


# --- API layer -------------------------------------------------------------
def test_poe_api_proof_of_execution_endpoint(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    body = gate.lt(tid, "/proof-of-execution").json()
    poe_proof = body["proof_of_execution"]
    assert poe_proof["proof_of_execution_valid"] is True
    assert poe_proof["proof_status"] == "VALID"
    assert "NO_EXTERNAL_EFFECT" in body["honesty_labels"]


def test_poe_api_clean_outcome_stream_complete(gate):
    tid, o = gate.prepared_local_tx(op="commit-local")
    poe = o["poe_stream"]
    assert poe["event_count"] == 19
    assert poe["stream_status"] == "COMPLETE"
    assert poe["chain_valid"] is True


def test_poe_api_proof_bundle_endpoint(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    body = gate.lt(tid, "/proof").json()
    bundle = body["b9_proof_bundle"]
    assert bundle["component_count"] == 21
    assert bundle["proof_bundle_overrides_blocker"] is False
    assert "NO_EXTERNAL_EFFECT" in body["honesty_labels"]


def test_poe_api_missing_event_blocks_via_pipeline(gate):
    b8id, _ = gate.b8_accepted_outcome()
    o = gate.local_tx(b8id, op="commit-local",
                      missing_poe_events=["LOCAL_COMMIT_APPLIED"]).json()
    assert o["b9_status"] == "B9_BLOCKED"
    assert o["dominant_signal"] == "POE_STREAM_INCOMPLETE"
    assert o["local_commit_applied"] is False

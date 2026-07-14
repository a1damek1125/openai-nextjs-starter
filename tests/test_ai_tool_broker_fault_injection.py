"""TOOL-B5 null broker: adversarial fault-injection harness.

The harness deterministically corrupts/removes/stales/reorders/mutates/replays
evidence across 19 documented fault cases; EVERY case must fail closed (never
land on a positive status) and NO unexpected positive results may slip through.
"""
from finalis.ai_employee import tool_broker as b
from tests import _b5_kernel as k

# The 19 documented adversarial fault cases (kernel FAULT_CASES).
DOCUMENTED_FAULTS = [
    "missing_b4_receipt", "stale_b4_receipt", "mutated_payload",
    "mutated_b3_contract", "mutated_adapter_manifest", "reordered_event_stream",
    "dropped_event_stream_event", "duplicated_event_stream_event",
    "forged_proof_carrying_certificate", "forged_negative_execution_certificate",
    "token_like_artifact_inserted", "credential_like_artifact_inserted",
    "callable_adapter_flag_inserted", "runtime_surface_inserted",
    "fake_provider_result_inserted", "null_output_leaks_payload",
    "recordkeeping_enables_effect_plane", "split_export_across_requests",
    "same_idempotency_key_different_payload",
]


def _harness(gate):
    return k.clean_outcome(gate)["fault_injection_harness"]


def test_harness_status_passed(gate):
    assert _harness(gate)["harness_status"] == "FAULT_INJECTION_PASSED"


def test_zero_unexpected_positive_results(gate):
    h = _harness(gate)
    assert h["unexpected_positive_results"] == []
    assert len(h["unexpected_positive_results"]) == 0


def test_fault_cases_match_documented_nineteen(gate):
    h = _harness(gate)
    assert h["fault_cases"] == DOCUMENTED_FAULTS
    assert h["fault_cases"] == b.FAULT_CASES
    assert len(h["fault_cases"]) == 19


def test_nineteen_fault_results(gate):
    h = _harness(gate)
    assert len(h["fault_results"]) == 19
    assert {r["fault_case"] for r in h["fault_results"]} == set(DOCUMENTED_FAULTS)


def test_every_fault_result_failed_closed_flag(gate):
    h = _harness(gate)
    assert all(r["failed_closed"] is True for r in h["fault_results"])


def test_no_fault_result_lands_on_positive_status(gate):
    h = _harness(gate)
    for r in h["fault_results"]:
        assert r["broker_status"] not in b.POSITIVE_STATUSES


def test_each_documented_fault_failed_closed(gate):
    """Iterate the fault_results and assert each specific documented fault
    failed closed (True) and did not reach a positive status."""
    h = _harness(gate)
    by_case = {r["fault_case"]: r for r in h["fault_results"]}
    for fault in DOCUMENTED_FAULTS:
        assert fault in by_case, fault
        entry = by_case[fault]
        assert entry["failed_closed"] is True, fault
        assert entry["broker_status"] not in b.POSITIVE_STATUSES, fault


def test_positive_statuses_constant(gate):
    assert b.POSITIVE_STATUSES == {
        "BROKER_PREPARED_FOR_FUTURE_ONLY", "NULL_ONLY_PREPARED"}


def test_harness_hash_present(gate):
    h = _harness(gate)
    assert h["fault_injection_harness_hash"]
    assert h["signal"] is None


def test_harness_hash_deterministic(gate):
    """Same request id + same evidence, different actor/created_at -> identical
    fault-injection harness hash."""
    tid, contract, d, pobj, head, quality, cert = k.setup(gate)
    o1 = k.prepare(gate, d, pobj, head, quality, contract, cert,
                   actor_id="a", created_at="T1")
    o2 = k.prepare(gate, d, pobj, head, quality, contract, cert,
                   actor_id="b", created_at="T2")
    assert (o1["fault_injection_harness"]["fault_injection_harness_hash"] ==
            o2["fault_injection_harness"]["fault_injection_harness_hash"])


def test_endpoint_post_fault_injection_check(gate):
    rid, _ = gate.prepared_broker()
    r = gate.br(rid, "/fault-injection-check", method="POST")
    assert r.status_code == 200
    body = r.json()
    assert body["harness_status"] == "FAULT_INJECTION_PASSED"
    assert body["unexpected_positive_results"] == []
    assert all(x["failed_closed"] is True for x in body["fault_results"])


def test_endpoint_get_fault_injection_returns_harness(gate):
    rid, _ = gate.prepared_broker()
    r = gate.br(rid, "/fault-injection")
    assert r.status_code == 200
    harness = r.json()["fault_injection_harness"]
    assert harness["harness_status"] == "FAULT_INJECTION_PASSED"
    assert harness["fault_cases"] == DOCUMENTED_FAULTS
    for entry in harness["fault_results"]:
        assert entry["failed_closed"] is True
        assert entry["broker_status"] not in b.POSITIVE_STATUSES

"""TOOL-B7: release gate — the negative-test gate passes only because the
fault-injection harness blocked every fault; a passing gate is required for the
escrow terminal."""
from finalis.ai_employee.tool_write_intent import _core_hash
from tests import _b7_kernel as k


def test_release_gate_passed(gate):
    rg = k.clean_outcome(gate)["write_intent_release_gate_report"]
    assert rg["release_gate_status"] == "PASSED"


def test_all_negative_tests_blocked(gate):
    rg = k.clean_outcome(gate)["write_intent_release_gate_report"]
    assert rg["negative_tests_blocked"] == rg["negative_tests_total"]
    assert rg["negative_tests_total"] > 0


def test_clean_gate_no_signal(gate):
    rg = k.clean_outcome(gate)["write_intent_release_gate_report"]
    assert rg["signal"] is None


def test_gate_matches_harness(gate):
    o = k.clean_outcome(gate)
    h = o["write_intent_fault_injection_harness"]
    rg = o["write_intent_release_gate_report"]
    assert rg["negative_tests_total"] == h["fault_case_count"]
    assert rg["negative_tests_blocked"] == \
        sum(1 for c in h["fault_cases"] if c["blocked"])


def test_passing_gate_required_for_escrow_terminal(gate):
    o = k.clean_outcome(gate)
    assert o["write_intent_status"] == "TRANSACTION_ESCROW_DRAFT_CREATED"
    assert o["write_intent_release_gate_report"]["release_gate_status"] == \
        "PASSED"


def test_release_gate_hash_recomputes(gate):
    rg = k.clean_outcome(gate)["write_intent_release_gate_report"]
    assert _core_hash(rg, "write_intent_release_gate_hash", "signal") == \
        rg["write_intent_release_gate_hash"]


def test_release_gate_hash_deterministic_across_actor(gate):
    b6 = k.b6_outcome(gate)
    o1 = k.prepare(gate, b6, actor_id="alice")
    o2 = k.prepare(gate, b6, actor_id="bob")
    assert o1["write_intent_release_gate_report"][
        "write_intent_release_gate_hash"] == \
        o2["write_intent_release_gate_report"][
            "write_intent_release_gate_hash"]


def test_gate_passes_even_when_outcome_blocked(gate):
    # The gate reflects the fault harness, which is independent of the primary
    # decision: a blocked primary decision still shows an all-blocked harness.
    o = k.prepare(gate, k.b6_outcome(gate), compensation_gaps=1)
    assert o["write_intent_release_gate_report"]["release_gate_status"] == \
        "PASSED"
    assert o["write_intent_status"] != "TRANSACTION_ESCROW_DRAFT_CREATED"


def test_release_gate_endpoint(gate):
    wid, _ = gate.prepared_write_intent()
    rg = gate.wi(wid, "/release-gate").json()[
        "write_intent_release_gate_report"]
    assert rg["release_gate_status"] == "PASSED"

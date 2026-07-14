"""TOOL-B9 v5: transactional integrity — conflict / replay / idempotency
detection, the 27-case fault-injection harness, the release gate, and the
conformance vector. A competing transaction, a detected replay, or an
idempotency-key mismatch each yields B9_CONFLICT with NO local commit applied.
On a clean outcome every fault case is blocked, the release gate passes, and the
conformance vector is present and conformant.
"""
from tests import _b9_kernel as k


def _conflict(over, expected_signal):
    o = k.prepare(**over)
    assert o["b9_status"] == "B9_CONFLICT"
    assert o["dominant_signal"] == expected_signal
    assert o["local_commit_applied"] is False
    return o


# --- kernel layer: conflict / replay / idempotency -------------------------
def test_conflictharness_conflicting_tx_detected():
    _conflict({"conflicting_txs": [{"transaction_id": "other",
                                    "tenant_id": "t1",
                                    "object_reference": "obj-1"}]},
              "CONFLICT_DETECTED")


def test_conflictharness_replay_detected():
    _conflict({"replay_detected": True}, "REPLAY_DETECTED")


def test_conflictharness_idempotency_mismatch():
    _conflict({"prior_idempotency": {"idem-tx1": "OTHER"}},
              "IDEMPOTENCY_MISMATCH")


def test_conflictharness_conflict_changes_decision_hash():
    clean = k.prepare()["b9_decision_hash"]
    conf = k.prepare(replay_detected=True)["b9_decision_hash"]
    assert clean != conf


# --- kernel layer: fault-injection harness ---------------------------------
def test_conflictharness_all_faults_blocked():
    h = k.clean_outcome()["b9_fault_injection_harness"]
    assert h["all_faults_blocked"] is True


def test_conflictharness_fault_case_count_is_27():
    h = k.clean_outcome()["b9_fault_injection_harness"]
    assert h["fault_case_count"] == 27
    assert len(h["fault_cases"]) == 27


def test_conflictharness_every_fault_case_blocked():
    h = k.clean_outcome()["b9_fault_injection_harness"]
    for case in h["fault_cases"]:
        assert case["blocked"] is True, case


def test_conflictharness_harness_status_and_hash_present():
    h = k.clean_outcome()["b9_fault_injection_harness"]
    assert h["harness_status"]
    assert h["b9_fault_injection_harness_hash"]
    assert h["honesty_labels"]


# --- kernel layer: release gate --------------------------------------------
def test_conflictharness_release_gate_passed():
    rg = k.clean_outcome()["b9_release_gate_report"]
    assert rg["release_gate_status"] == "PASSED"


def test_conflictharness_release_gate_all_negatives_blocked():
    rg = k.clean_outcome()["b9_release_gate_report"]
    assert rg["negative_tests_total"] == rg["negative_tests_blocked"]
    assert rg["negative_tests_total"] > 0


# --- kernel layer: conformance vector --------------------------------------
def test_conflictharness_conformance_vector_conformant():
    cv = k.clean_outcome()["b9_conformance_vector"]
    assert cv["conformant"] is True


def test_conflictharness_conformance_dimensions_all_true():
    cv = k.clean_outcome()["b9_conformance_vector"]
    for name, value in cv["dimensions"].items():
        assert value is True, name


# --- API layer -------------------------------------------------------------
def test_conflictharness_api_fault_injection_endpoint_200(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.lt(tid, "/fault-injection")
    assert r.status_code == 200
    body = r.json()
    h = body["b9_fault_injection_harness"]
    assert h["all_faults_blocked"] is True
    assert h["fault_case_count"] == 27
    assert body["honesty_labels"]


def test_conflictharness_api_release_gate_endpoint_200(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.lt(tid, "/release-gate")
    assert r.status_code == 200
    body = r.json()
    assert body["b9_release_gate_report"]["release_gate_status"] == "PASSED"
    assert body["honesty_labels"]


def test_conflictharness_api_conformance_vector_endpoint_200(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.lt(tid, "/conformance-vector")
    assert r.status_code == 200
    body = r.json()
    assert body["b9_conformance_vector"]["conformant"] is True
    assert body["honesty_labels"]


def test_conflictharness_api_endpoints_carry_no_external_effect_label(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    labels = gate.lt(tid, "/fault-injection").json()["honesty_labels"]
    assert "NO_EXTERNAL_EFFECT" in labels

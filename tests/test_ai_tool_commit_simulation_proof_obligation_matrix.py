"""TOOL-B8 v5: Proof-obligation discharge matrix — every required obligation
must be discharged by a supporting hash; any undischarged obligation blocks and
the accepted status can never survive a dropped obligation."""
from finalis.ai_employee.tool_commit_simulation import (
    _core_hash, REQUIRED_OBLIGATIONS)
from tests import _b8_kernel as k


def test_matrix_exists(gate):
    m = k.clean_outcome(gate)["proof_obligation_matrix"]
    assert m["proof_obligation_matrix_id"].startswith("pom-")
    assert m["signal"] is None


def test_clean_matrix_all_discharged(gate):
    m = k.clean_outcome(gate)["proof_obligation_matrix"]
    assert m["matrix_status"] == "ALL_DISCHARGED"
    assert m["obligations"] == list(REQUIRED_OBLIGATIONS)
    assert m["undischarged_obligations"] == []
    assert m["supporting_hashes"]
    assert sorted(m["discharged_obligations"]) == sorted(REQUIRED_OBLIGATIONS)


def test_clean_outcome_accepted(gate):
    assert k.clean_outcome(gate)["commit_simulation_status"] == "B8_V5_ACCEPTED"


def test_dropped_no_real_commit_blocks(gate):
    o = k.clean_outcome(gate, dropped_obligations=["NO_REAL_COMMIT"])
    m = o["proof_obligation_matrix"]
    assert m["matrix_status"] == "UNDISCHARGED"
    assert "NO_REAL_COMMIT" in m["undischarged_obligations"]
    assert "NO_REAL_COMMIT" not in m["supporting_hashes"]
    assert o["dominant_signal"] == "PROOF_OBLIGATION_UNDISCHARGED"
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_dropped_artifacts_not_authority_blocks(gate):
    o = k.clean_outcome(gate, dropped_obligations=["ARTIFACTS_NOT_AUTHORITY"])
    assert "ARTIFACTS_NOT_AUTHORITY" in o["proof_obligation_matrix"][
        "undischarged_obligations"]
    assert o["dominant_signal"] == "PROOF_OBLIGATION_UNDISCHARGED"
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_dropped_not_production_ready_blocks(gate):
    o = k.clean_outcome(gate, dropped_obligations=["NOT_PRODUCTION_READY"])
    assert "NOT_PRODUCTION_READY" in o["proof_obligation_matrix"][
        "undischarged_obligations"]
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_drop_obligation_never_keeps_accepted(gate):
    # "drop proof obligation but keep accepted status" — malicious: the status
    # must move off B8_V5_ACCEPTED.
    o = k.clean_outcome(gate, dropped_obligations=["NO_EFFECT_RELEASE"])
    assert o["b8_v5_accepted"] is False
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_matrix_hash_recomputes(gate):
    m = k.clean_outcome(gate)["proof_obligation_matrix"]
    assert _core_hash(m, "proof_obligation_matrix_hash", "signal") == \
        m["proof_obligation_matrix_hash"]


def test_undischarged_changes_matrix_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["proof_obligation_matrix"][
        "proof_obligation_matrix_hash"]
    broken = k.prepare(gate, b7, dropped_obligations=["NO_REAL_COMMIT"])[
        "proof_obligation_matrix"]["proof_obligation_matrix_hash"]
    assert clean != broken


def test_undischarged_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    broken = k.prepare(gate, b7, dropped_obligations=["NO_REAL_COMMIT"])[
        "commit_simulation_decision_hash"]
    assert clean != broken


def test_matrix_endpoint_returns_matrix(gate):
    sid, _ = gate.prepared_commit_simulation()
    m = gate.cs(sid, "/proof-obligation-matrix").json()[
        "proof_obligation_matrix"]
    assert m["matrix_status"] == "ALL_DISCHARGED"
    assert m["undischarged_obligations"] == []

"""TOOL-B8 v5: B9 input-contract negative capability — the contract enumerates
exactly what a FUTURE B9 runtime must REJECT (B8 artifacts as authority) and
must RECOMPUTE fresh; B8 pre-authorizes nothing. An invalid contract blocks with
B9_INPUT_CONTRACT_INVALID."""
from finalis.ai_employee.tool_commit_simulation import (
    _core_hash, B9_MUST_REJECT_ARTIFACTS, B9_MUST_RECOMPUTE)
from tests import _b8_kernel as k


def test_contract_exists_and_valid(gate):
    c = k.clean_outcome(gate)["b9_negative_capability"]
    assert c["b9_negative_capability_id"].startswith("bnc-")
    assert c["contract_status"] == "VALID"
    assert c["signal"] is None


def test_lists_all_seven_must_reject_artifacts(gate):
    c = k.clean_outcome(gate)["b9_negative_capability"]
    assert len(B9_MUST_REJECT_ARTIFACTS) == 7
    assert c["b9_must_reject_artifacts"] == list(B9_MUST_REJECT_ARTIFACTS)
    assert c["b9_forbidden_inputs"] == list(B9_MUST_REJECT_ARTIFACTS)


def test_lists_all_ten_must_recompute_factors(gate):
    c = k.clean_outcome(gate)["b9_negative_capability"]
    assert len(B9_MUST_RECOMPUTE) == 10
    assert c["b9_must_recompute_factors"] == list(B9_MUST_RECOMPUTE)
    assert c["b9_required_revalidations"] == list(B9_MUST_RECOMPUTE)


def test_b8_proof_bundle_listed_among_must_reject(gate):
    # "B8 proof bundle is B9 authority" — the contract explicitly forbids it.
    c = k.clean_outcome(gate)["b9_negative_capability"]
    assert "B8_PROOF_BUNDLE" in c["b9_must_reject_artifacts"]
    assert "B8_ASSURANCE_ENVELOPE" in c["b9_must_reject_artifacts"]


def test_invalid_contract_blocks(gate):
    o = k.clean_outcome(gate, b9_negcap_valid=False)
    c = o["b9_negative_capability"]
    assert c["contract_status"] == "INVALID"
    assert c["signal"] == "B9_INPUT_CONTRACT_INVALID"
    assert o["dominant_signal"] == "B9_INPUT_CONTRACT_INVALID"
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_invalid_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    invalid = k.prepare(gate, b7, b9_negcap_valid=False)[
        "commit_simulation_decision_hash"]
    assert clean != invalid


def test_hash_recomputes(gate):
    c = k.clean_outcome(gate)["b9_negative_capability"]
    recomputed = _core_hash(c, "b9_negative_capability_hash", "signal")
    assert recomputed == c["b9_negative_capability_hash"]


def test_b9_revalidation_always_required(gate):
    o = k.clean_outcome(gate)
    assert o["b9_revalidation_required"] is True
    assert o["activated_b9"] is False
    assert o["granted_b9_authority"] is False


def test_api_endpoint_returns_valid_contract(gate):
    sid, _ = gate.prepared_commit_simulation()
    r = gate.cs(sid, "/b9-negative-capability")
    assert r.status_code == 200
    c = r.json()["b9_negative_capability"]
    assert c["contract_status"] == "VALID"
    assert c["b9_must_reject_artifacts"] == list(B9_MUST_REJECT_ARTIFACTS)
    assert c["b9_must_recompute_factors"] == list(B9_MUST_RECOMPUTE)

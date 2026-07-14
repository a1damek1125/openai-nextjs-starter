"""TOOL-B8 v4: B9 revalidation contract — B8 pre-authorizes nothing; B9 must
always revalidate, and can never skip it because B8 passed."""
from finalis.ai_employee.tool_commit_simulation import _core_hash, B9_MUST_RECOMPUTE
from tests import _b8_kernel as k


def test_clean_contract_present(gate):
    c = k.clean_outcome(gate)["b9_revalidation_contract"]
    assert c["contract_status"] == "PRESENT"
    assert c["b9_revalidation_required"] is True
    assert c["b8_pre_authorizes_nothing"] is True
    assert c["signal"] is None


def test_required_recomputations_match(gate):
    c = k.clean_outcome(gate)["b9_revalidation_contract"]
    assert c["required_recomputations"] == list(B9_MUST_RECOMPUTE)


def test_missing_contract_needs_revalidation(gate):
    o = k.clean_outcome(gate, b9_contract_present=False)
    c = o["b9_revalidation_contract"]
    assert c["contract_status"] == "MISSING"
    assert o["dominant_signal"] == "B9_REVALIDATION_CONTRACT_MISSING"
    assert o["commit_simulation_status"] == "B8_V5_NEEDS_REVALIDATION"
    assert o["b8_v5_accepted"] is False


def test_revalidation_always_required_even_when_missing(gate):
    # "B9 can skip revalidation because B8 passed" is never honored.
    o = k.clean_outcome(gate, b9_contract_present=False)
    assert o["b9_revalidation_required"] is True
    assert o["b9_revalidation_contract"]["b9_revalidation_required"] is True


def test_revalidation_required_on_clean(gate):
    o = k.clean_outcome(gate)
    assert o["b9_revalidation_required"] is True
    assert o["b9_revalidation_contract"]["b9_revalidation_required"] is True


def test_missing_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    missing = k.prepare(gate, b7, b9_contract_present=False)[
        "commit_simulation_decision_hash"]
    assert clean != missing


def test_contract_hash_recomputes(gate):
    c = k.clean_outcome(gate)["b9_revalidation_contract"]
    assert _core_hash(c, "b9_revalidation_contract_hash", "signal") == \
        c["b9_revalidation_contract_hash"]


# --- API layer -------------------------------------------------------------
def test_api_contract_endpoint_present(gate):
    sid, _ = gate.prepared_commit_simulation()
    c = gate.cs(sid, "/b9-revalidation-contract").json()[
        "b9_revalidation_contract"]
    assert c["contract_status"] == "PRESENT"
    assert c["b9_revalidation_required"] is True
    assert c["required_recomputations"] == list(B9_MUST_RECOMPUTE)


def test_api_contract_hash_recomputes(gate):
    sid, _ = gate.prepared_commit_simulation()
    c = gate.cs(sid, "/b9-revalidation-contract").json()[
        "b9_revalidation_contract"]
    assert _core_hash(c, "b9_revalidation_contract_hash", "signal") == \
        c["b9_revalidation_contract_hash"]

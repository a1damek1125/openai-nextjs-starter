"""TOOL-B8 v5: Production-claim scanner — any injected production/autonomy/
executable claim is detected, poisons the outcome and quarantines it. Benign
claims are ignored."""
import pytest

from finalis.ai_employee.tool_commit_simulation import (
    _core_hash, POISON_CLAIM_FIELDS)
from tests import _b8_kernel as k


def test_scanner_exists(gate):
    s = k.clean_outcome(gate)["production_claim_scanner"]
    assert s["production_claim_scanner_id"].startswith("pcs-")
    assert s["signal"] is None


def test_clean_scanner_is_clean(gate):
    s = k.clean_outcome(gate)["production_claim_scanner"]
    assert s["scanner_status"] == "CLEAN"
    assert s["poisoned_claims_detected"] == []
    assert s["objects_checked"] == sorted(POISON_CLAIM_FIELDS)


def test_clean_outcome_accepted(gate):
    assert k.clean_outcome(gate)["commit_simulation_status"] == "B8_V5_ACCEPTED"


def test_production_ready_poisons_and_quarantines(gate):
    o = k.clean_outcome(gate, extra_claims={"production_ready": True})
    s = o["production_claim_scanner"]
    assert s["scanner_status"] == "POISONED"
    assert "production_ready" in s["poisoned_claims_detected"]
    assert s["claim_locations"]
    assert o["dominant_signal"] == "PRODUCTION_CLAIM_POISONING_DETECTED"
    assert o["commit_simulation_status"] == "B8_V5_QUARANTINED"


@pytest.mark.parametrize("field", [
    "autonomous_ready", "commit_executable_now", "b9_ready_without_revalidation",
    "provider_ready", "credential_ready"])
def test_each_poison_field_blocks(gate, field):
    o = k.clean_outcome(gate, extra_claims={field: True})
    s = o["production_claim_scanner"]
    assert field in s["poisoned_claims_detected"]
    assert o["dominant_signal"] == "PRODUCTION_CLAIM_POISONING_DETECTED"
    assert o["commit_simulation_status"] == "B8_V5_QUARANTINED"


def test_benign_claim_does_not_poison(gate):
    o = k.clean_outcome(gate, extra_claims={"foo": True})
    s = o["production_claim_scanner"]
    assert s["scanner_status"] == "CLEAN"
    assert s["poisoned_claims_detected"] == []
    assert o["commit_simulation_status"] == "B8_V5_ACCEPTED"


def test_production_ready_stays_not_production(gate):
    o = k.clean_outcome(gate, extra_claims={"production_ready": True})
    assert o["production_ready"] is False
    assert o["commit_executable_now"] is False


def test_scanner_hash_recomputes(gate):
    s = k.clean_outcome(gate)["production_claim_scanner"]
    assert _core_hash(s, "production_claim_scanner_hash", "signal") == \
        s["production_claim_scanner_hash"]


def test_poisoning_changes_scanner_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["production_claim_scanner"][
        "production_claim_scanner_hash"]
    poisoned = k.prepare(gate, b7, extra_claims={"production_ready": True})[
        "production_claim_scanner"]["production_claim_scanner_hash"]
    assert clean != poisoned


def test_poisoning_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    poisoned = k.prepare(gate, b7, extra_claims={"production_ready": True})[
        "commit_simulation_decision_hash"]
    assert clean != poisoned


def test_scanner_endpoint_returns_scanner(gate):
    sid, _ = gate.prepared_commit_simulation()
    s = gate.cs(sid, "/production-claim-scanner").json()[
        "production_claim_scanner"]
    assert s["scanner_status"] == "CLEAN"
    assert s["poisoned_claims_detected"] == []

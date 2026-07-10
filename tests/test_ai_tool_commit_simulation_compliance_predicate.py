"""TOOL-B8 v1-v3 base: compliance predicate — a set of machine-checkable
compliance predicates (policy epoch, consent, legal hold, customer impact, local
write scope) must all hold, else a violation blocks."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_clean_compliant(gate):
    r = k.clean_outcome(gate)["compliance_predicate"]
    assert r["predicate_status"] == "COMPLIANT"
    assert r["all_predicates_hold"] is True
    assert r["violation_count"] == 0
    assert r["signal"] is None


def test_predicates_non_empty(gate):
    r = k.clean_outcome(gate)["compliance_predicate"]
    assert r["predicates"]
    assert "CONSENT_IN_SCOPE" in r["predicates"]


def test_violation_fails(gate):
    o = k.clean_outcome(gate, predicate_violations=1)
    assert o["dominant_signal"] == "COMPLIANCE_PREDICATE_FAILED"
    r = o["compliance_predicate"]
    assert r["predicate_status"] == "VIOLATED"
    assert r["all_predicates_hold"] is False
    assert r["violation_count"] == 1


def test_violation_blocks(gate):
    o = k.clean_outcome(gate, predicate_violations=1)
    assert o["commit_simulation_status"] != "B8_V5_ACCEPTED"


def test_violation_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    violated = k.prepare(gate, b7, predicate_violations=1)[
        "commit_simulation_decision_hash"]
    assert clean != violated


def test_compliance_predicate_hash_recomputes(gate):
    r = k.clean_outcome(gate)["compliance_predicate"]
    assert _core_hash(r, "compliance_predicate_hash", "signal") == \
        r["compliance_predicate_hash"]


def test_violation_hash_recomputes(gate):
    r = k.clean_outcome(gate, predicate_violations=1)["compliance_predicate"]
    assert _core_hash(r, "compliance_predicate_hash", "signal") == \
        r["compliance_predicate_hash"]


def test_compliance_predicate_endpoint(gate):
    sid, _ = gate.prepared_commit_simulation()
    r = gate.cs(sid, "/compliance-predicate").json()["compliance_predicate"]
    assert r["predicate_status"] == "COMPLIANT"
    assert r["all_predicates_hold"] is True

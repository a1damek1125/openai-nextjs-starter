"""TOOL-B8 v4: final pre-commit safety case — a low-priority aggregate that is
COMPLETE iff every base claim discharges, and never masks the root cause."""
from finalis.ai_employee.tool_commit_simulation import _core_hash
from tests import _b8_kernel as k


def test_clean_safety_case_complete(gate):
    sc = k.clean_outcome(gate)["safety_case"]
    assert sc["safety_case_status"] == "COMPLETE"
    assert sc["safety_case_complete"] is True
    assert sc["signal"] is None


def test_clean_all_claims_true(gate):
    sc = k.clean_outcome(gate)["safety_case"]
    assert sc["claims"]
    for key, val in sc["claims"].items():
        assert val is True, key


def test_base_failure_makes_incomplete_but_root_dominates(gate):
    # A base check failing (shadow dry-run) makes the safety case INCOMPLETE,
    # but the specific base signal dominates the low-priority aggregate.
    o = k.clean_outcome(gate, dry_run_ok=False)
    sc = o["safety_case"]
    assert sc["safety_case_status"] == "INCOMPLETE"
    assert o["dominant_signal"] == "SHADOW_DRY_RUN_FAILED"
    assert "SAFETY_CASE_INCOMPLETE" in o["all_signals"]


def test_incomplete_claims_dict_present(gate):
    o = k.clean_outcome(gate, dry_run_ok=False)
    sc = o["safety_case"]
    assert isinstance(sc["claims"], dict) and sc["claims"]
    assert sc["claims"]["shadow_dry_run_ok"] is False
    assert sc["safety_case_complete"] is False


def test_failure_changes_decision_hash(gate):
    b7 = k.b7_outcome(gate)
    clean = k.prepare(gate, b7)["commit_simulation_decision_hash"]
    broken = k.prepare(gate, b7, dry_run_ok=False)[
        "commit_simulation_decision_hash"]
    assert clean != broken


def test_safety_case_hash_recomputes(gate):
    sc = k.clean_outcome(gate)["safety_case"]
    assert _core_hash(sc, "safety_case_hash", "signal") == \
        sc["safety_case_hash"]


# --- API layer -------------------------------------------------------------
def test_api_safety_case_endpoint_complete(gate):
    sid, _ = gate.prepared_commit_simulation()
    sc = gate.cs(sid, "/safety-case").json()["safety_case"]
    assert sc["safety_case_status"] == "COMPLETE"
    assert sc["safety_case_complete"] is True


def test_api_safety_case_hash_recomputes(gate):
    sid, _ = gate.prepared_commit_simulation()
    sc = gate.cs(sid, "/safety-case").json()["safety_case"]
    assert _core_hash(sc, "safety_case_hash", "signal") == \
        sc["safety_case_hash"]

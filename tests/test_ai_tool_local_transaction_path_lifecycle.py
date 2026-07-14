"""TOOL-B9 v5: runtime path-compliance monitor + agent lifecycle middleware
checkpoints. A local, reversible commit only proceeds when every path-compliance
predicate holds AND every lifecycle checkpoint passes. A single failed predicate
=> B9_BLOCKED/PATH_COMPLIANCE_FAILED; a single failed checkpoint =>
B9_BLOCKED/LIFECYCLE_CHECKPOINT_FAILED. No external effect is ever produced.
"""
from finalis.ai_employee.tool_local_transaction import _core_hash
from tests import _b9_kernel as k


def _blocked(over, expected_signal):
    o = k.prepare(**over)
    assert o["b9_status"] == "B9_BLOCKED"
    assert o["dominant_signal"] == expected_signal
    assert o["local_commit_applied"] is False
    return o


# --- kernel layer: path compliance -----------------------------------------
def test_pl_clean_path_compliance_passed():
    pc = k.clean_outcome()["path_compliance"]
    assert pc["path_compliance_result"] == "PASSED"
    assert pc["all_predicates_hold"] is True
    assert pc["failed_predicates"] == []


def test_pl_clean_path_compliance_all_predicates_hold():
    pc = k.clean_outcome()["path_compliance"]
    assert all(pc["predicates"].values())
    assert pc["signal"] is None


def test_pl_consent_predicate_failure_blocks_commit():
    o = _blocked({"path_checks": {"consent_ok": False}}, "PATH_COMPLIANCE_FAILED")
    pc = o["path_compliance"]
    assert pc["path_compliance_result"] == "FAILED"
    assert pc["all_predicates_hold"] is False
    assert "consent_ok" in pc["failed_predicates"]
    assert pc["predicates"]["consent_ok"] is False


def test_pl_local_only_predicate_failure_blocks_commit():
    o = _blocked({"path_checks": {"local_only_ok": False}},
                 "PATH_COMPLIANCE_FAILED")
    assert "local_only_ok" in o["path_compliance"]["failed_predicates"]


def test_pl_no_external_effect_predicate_failure_blocks_commit():
    o = _blocked({"path_checks": {"no_external_effect_ok": False}},
                 "PATH_COMPLIANCE_FAILED")
    assert "no_external_effect_ok" in o["path_compliance"]["failed_predicates"]


def test_pl_path_compliance_hash_recomputes():
    pc = k.clean_outcome()["path_compliance"]
    assert _core_hash(pc, "path_compliance_hash", "signal") == pc[
        "path_compliance_hash"]


def test_pl_failed_path_compliance_hash_recomputes():
    pc = k.prepare(path_checks={"consent_ok": False})["path_compliance"]
    assert _core_hash(pc, "path_compliance_hash", "signal") == pc[
        "path_compliance_hash"]


def test_pl_path_failure_changes_decision_hash():
    clean = k.prepare()["b9_decision_hash"]
    failed = k.prepare(path_checks={"consent_ok": False})["b9_decision_hash"]
    assert clean != failed


# --- kernel layer: lifecycle checkpoints -----------------------------------
def test_pl_clean_lifecycle_checkpoints_all_pass():
    lc = k.clean_outcome()["lifecycle_checkpoints"]
    assert lc["checkpoints_status"] == "PASSED"
    assert lc["all_passed"] is True
    assert all(cp["passed"] for cp in lc["checkpoints"])


def test_pl_clean_lifecycle_checkpoints_no_signal():
    lc = k.clean_outcome()["lifecycle_checkpoints"]
    assert lc["signal"] is None
    assert all(cp["reason_code"] is None for cp in lc["checkpoints"])


def test_pl_pre_commit_checkpoint_failure_blocks_commit():
    o = _blocked({"failed_checkpoints": ["pre_commit_validation"]},
                 "LIFECYCLE_CHECKPOINT_FAILED")
    lc = o["lifecycle_checkpoints"]
    assert lc["checkpoints_status"] == "FAILED"
    assert lc["all_passed"] is False
    failed = [cp for cp in lc["checkpoints"] if not cp["passed"]]
    assert [cp["checkpoint"] for cp in failed] == ["pre_commit_validation"]
    assert failed[0]["reason_code"] == "LIFECYCLE_CHECKPOINT_FAILED"


def test_pl_post_commit_checkpoint_failure_blocks_commit():
    o = _blocked({"failed_checkpoints": ["post_commit_check"]},
                 "LIFECYCLE_CHECKPOINT_FAILED")
    names = [cp["checkpoint"] for cp in o["lifecycle_checkpoints"]["checkpoints"]
             if not cp["passed"]]
    assert names == ["post_commit_check"]


def test_pl_lifecycle_checkpoints_hash_recomputes():
    lc = k.clean_outcome()["lifecycle_checkpoints"]
    assert _core_hash(lc, "lifecycle_checkpoints_hash", "signal") == lc[
        "lifecycle_checkpoints_hash"]


def test_pl_failed_lifecycle_checkpoints_hash_recomputes():
    lc = k.prepare(failed_checkpoints=["pre_commit_validation"])[
        "lifecycle_checkpoints"]
    assert _core_hash(lc, "lifecycle_checkpoints_hash", "signal") == lc[
        "lifecycle_checkpoints_hash"]


def test_pl_checkpoint_failure_produces_no_external_effect():
    o = k.prepare(failed_checkpoints=["pre_commit_validation"])
    assert o["produced_external_effect"] is False
    assert o["provider_called"] is False


# --- API layer -------------------------------------------------------------
def test_pl_api_path_compliance_endpoint(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.lt(tid, "/path-compliance")
    assert r.status_code == 200
    body = r.json()
    pc = body["path_compliance"]
    assert pc["path_compliance_result"] == "PASSED"
    assert pc["all_predicates_hold"] is True
    assert body["honesty_labels"]


def test_pl_api_lifecycle_checkpoints_endpoint(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.lt(tid, "/lifecycle-checkpoints")
    assert r.status_code == 200
    body = r.json()
    lc = body["lifecycle_checkpoints"]
    assert lc["checkpoints_status"] == "PASSED"
    assert lc["all_passed"] is True
    assert body["honesty_labels"]

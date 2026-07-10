"""TOOL-B9 v5: shadow local state + proof-of-execution contract. The commit is
applied to a SHADOW copy only (never production), constrained to the allowed
local write scope. Any delta field outside that scope is a
FORBIDDEN_WRITE_SET_VIOLATION and NO commit is applied. The execution contract
binds the allowed write-set, is reproducible by hash, and the after-state hash
equals the shadow when committed and the before-state when blocked.
"""
from finalis.ai_employee.tool_local_transaction import _core_hash
from tests import _b9_kernel as k

_OUT_OF_SCOPE = {"allowed_local_scope": ["only_this"],
                 "planned_delta": {"forbidden_field": "x"}}


def _shadow(o):
    return o["shadow_state"]


def _contract(o):
    return o["execution_contract"]


# --- kernel layer ----------------------------------------------------------
def test_shadow_clean_before_differs_from_shadow():
    sh = _shadow(k.clean_outcome())
    assert sh["before_state"] != sh["shadow_state"]
    assert sh["before_state"] == {"status": "new"}
    assert sh["shadow_state"] == {"status": "reviewed"}
    assert sh["before_state_hash"] != sh["shadow_state_hash"]


def test_shadow_clean_is_reversible_shadow_only():
    sh = _shadow(k.clean_outcome())
    assert sh["shadow_status"] == "VALID"
    assert sh["applied_to_production"] is False
    assert sh["reversible"] is True
    assert sh["shadow_only"] is True
    assert sh["out_of_scope_fields"] == []
    assert sh["signal"] is None


def test_shadow_committed_state_is_reviewed():
    o = k.clean_outcome()
    assert o["committed_state"] == {"status": "reviewed"}
    assert o["local_commit_applied"] is True


def test_shadow_allowed_local_scope_respected():
    sh = _shadow(k.clean_outcome())
    assert sh["write_set"] == ["status"]
    assert sh["out_of_scope_fields"] == []


def test_shadow_out_of_scope_delta_blocked():
    o = k.prepare(**_OUT_OF_SCOPE)
    assert o["b9_status"] == "B9_BLOCKED"
    assert o["dominant_signal"] == "FORBIDDEN_WRITE_SET_VIOLATION"
    assert o["local_commit_applied"] is False


def test_shadow_out_of_scope_marks_shadow_invalid():
    sh = _shadow(k.prepare(**_OUT_OF_SCOPE))
    assert sh["shadow_status"] == "INVALID"
    assert sh["out_of_scope_fields"] == ["forbidden_field"]
    assert sh["signal"] == "SHADOW_STATE_INVALID"


def test_shadow_state_wrapper_hash_recomputes():
    sh = _shadow(k.clean_outcome())
    assert _core_hash(sh, "shadow_state_wrapper_hash", "signal") == sh[
        "shadow_state_wrapper_hash"]


def test_execution_contract_clean_valid():
    c = _contract(k.clean_outcome())
    assert c["contract_status"] == "VALID"
    assert c["signal"] is None
    assert c["allowed_write_set"] == ["status"]
    assert c["forbidden_write_set"] == []
    assert c["rollback_required"] is True
    assert c["replay_required"] is True


def test_execution_contract_forbidden_write_set_violation():
    c = _contract(k.prepare(**_OUT_OF_SCOPE))
    assert c["contract_status"] == "INVALID"
    assert c["signal"] == "FORBIDDEN_WRITE_SET_VIOLATION"
    assert c["forbidden_write_set"] == ["forbidden_field"]


def test_execution_contract_hash_recomputes():
    c = _contract(k.clean_outcome())
    assert _core_hash(c, "contract_hash", "signal") == c["contract_hash"]


def test_shadow_after_state_hash_equals_shadow_when_committed():
    o = k.clean_outcome()
    sh = _shadow(o)
    assert o["local_commit_applied"] is True
    assert o["after_state_hash"] == sh["shadow_state_hash"]
    assert o["after_state_hash"] != o["before_state_hash"]
    assert o["before_state_hash"] == sh["before_state_hash"]


def test_shadow_after_state_hash_equals_before_when_blocked():
    o = k.prepare(**_OUT_OF_SCOPE)
    sh = _shadow(o)
    assert o["local_commit_applied"] is False
    assert o["after_state_hash"] == o["before_state_hash"]
    assert o["after_state_hash"] == sh["before_state_hash"]
    assert o["committed_state"] == sh["before_state"]


def test_shadow_out_of_scope_changes_decision_hash():
    clean = k.prepare()["b9_decision_hash"]
    blocked = k.prepare(**_OUT_OF_SCOPE)["b9_decision_hash"]
    assert clean != blocked


# --- API layer -------------------------------------------------------------
def test_api_shadow_state_endpoint_returns_field(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.lt(tid, "/shadow-state")
    assert r.status_code == 200
    body = r.json()
    sh = body["shadow_state"]
    assert sh["shadow_status"] == "VALID"
    assert sh["applied_to_production"] is False
    assert sh["before_state"] != sh["shadow_state"]
    assert body["honesty_labels"]


def test_api_execution_contract_endpoint_returns_field(gate):
    tid, _ = gate.prepared_local_tx(op="commit-local")
    r = gate.lt(tid, "/execution-contract")
    assert r.status_code == 200
    body = r.json()
    c = body["execution_contract"]
    assert c["contract_status"] == "VALID"
    assert c["allowed_write_set"] == ["status"]
    assert body["honesty_labels"]


def test_api_shadow_out_of_scope_blocked(gate):
    b8id, _ = gate.b8_accepted_outcome()
    o = gate.local_tx(b8id, op="commit-local",
                      allowed_local_scope=["only_this"],
                      planned_delta={"forbidden_field": "x"}).json()
    assert o["b9_status"] == "B9_BLOCKED"
    assert o["dominant_signal"] == "FORBIDDEN_WRITE_SET_VIOLATION"
    assert o["local_commit_applied"] is False


def test_api_clean_commit_applies_reviewed_shadow(gate):
    tid, o = gate.prepared_local_tx(op="commit-local")
    assert o["committed_state"] == {"status": "reviewed"}
    assert o["after_state_hash"] == o["shadow_state_hash"]
    assert o["before_state_hash"] != o["after_state_hash"]

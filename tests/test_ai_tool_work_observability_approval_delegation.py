"""TOOL-B9.2 v5: Approval Continuity (section 12) + Delegation Provenance
(section 11).

A clean approval exactly binds the approved action/target/scope to the observed
work and is single-use by default; any drift (action, target, wider scope,
expiry, revocation, use-limit) invalidates the binding. Approving a schedule is
NOT approving each sensitive effect, so the approval mode is recorded explicitly.
Delegation is monotonic: a child delegation may never broaden the parent's
read/write/tool/resource scope or externality class. Both records are derived
evidence only and are reconstructed from bound state, never from a trace.
"""
from finalis.ai_employee.tool_contracts import _core_hash
from finalis.ai_employee import tool_work_observability as wo
from tests import _b92_kernel as k


def _degrades(over, expected_signal, expected_truth=None, expected_state=None):
    o = k.prepare(**over)
    assert o["proof_of_work_outcome_valid"] is False
    assert o["work_run_state"] != "WORK_OUTCOME_CERTIFIED"
    assert expected_signal in o["all_signals"]
    if expected_truth is not None:
        assert o["work_outcome_truth_state"] == expected_truth
    if expected_state is not None:
        assert o["work_run_state"] == expected_state
    # Derived observatory: no external effect ever, even on an invalid binding.
    assert o["produced_external_effect"] is False
    assert o["outbox_released"] is False
    return o


# --- kernel layer: approval continuity -------------------------------------
def test_appdel_clean_approval_valid_exact_binding():
    ap = k.clean_outcome()["approval_continuity"]
    assert ap["approval_status"] == "VALID"
    assert ap["exact_binding"] is True
    assert ap["fuzzy_matching"] is False
    assert ap["signal"] is None


def test_appdel_exact_action_binding_passes():
    # approved action == actual action -> binding certifies the run.
    o = k.prepare(approved_action="publish_local_report",
                  actual_action="publish_local_report")
    assert o["work_run_state"] == "WORK_OUTCOME_CERTIFIED"
    assert o["approval_continuity"]["approval_status"] == "VALID"


def test_appdel_action_mismatch_partial():
    o = _degrades({"approved_action": "A", "actual_action": "B"},
                  "APPROVAL_ACTION_MISMATCH", expected_truth="PARTIAL")
    assert o["approval_continuity"]["approval_status"] == "INVALID"
    assert o["approval_continuity"]["exact_binding"] is False


def test_appdel_target_mismatch_partial():
    _degrades({"approved_target": "x", "actual_target": "y"},
              "APPROVAL_TARGET_MISMATCH", expected_truth="PARTIAL")


def test_appdel_scope_exceeded_wider_actual():
    # actual_scope not a subset of approved_scope -> exceeded.
    _degrades({"approved_scope": ["a"], "actual_scope": ["a", "b"]},
              "APPROVAL_SCOPE_EXCEEDED", expected_truth="PARTIAL")


def test_appdel_approval_expired_is_stale():
    _degrades({"approval_expired": True}, "APPROVAL_EXPIRED",
              expected_truth="STALE")


def test_appdel_approval_revoked_is_rejected():
    o = _degrades({"approval_revoked": True}, "APPROVAL_REVOKED",
                  expected_truth="REVOKED", expected_state="REJECTED")
    assert o["approval_continuity"]["approval_status"] == "INVALID"


def test_appdel_single_use_reuse_blocked():
    # Single-use approval already consumed cannot be reused for another run.
    o = _degrades({"maximum_uses": 1, "uses_consumed": 1},
                  "APPROVAL_USE_LIMIT_EXCEEDED", expected_truth="PARTIAL")
    ap = o["approval_continuity"]
    assert ap["maximum_uses"] == 1 and ap["uses_consumed"] == 1


def test_appdel_approval_mode_recorded_and_defaulted():
    # Approving a schedule is not approving each sensitive effect, so the mode
    # is a recorded field drawn from the fixed vocabulary, with defaults present.
    ap = k.clean_outcome()["approval_continuity"]
    assert ap["approval_mode"] in wo.APPROVAL_MODES
    assert ap["approval_mode"] == "APPROVE_EACH_RUN"
    assert ap["maximum_uses"] == 1 and ap["uses_consumed"] == 0
    # A distinct mode is honoured verbatim (still a valid clean run).
    o = k.prepare(approval_mode="APPROVE_EACH_SENSITIVE_EFFECT")
    assert o["approval_continuity"]["approval_mode"] == \
        "APPROVE_EACH_SENSITIVE_EFFECT"
    assert o["work_run_state"] == "WORK_OUTCOME_CERTIFIED"


def test_appdel_approval_binding_hash_recompute():
    ap = k.clean_outcome()["approval_continuity"]
    assert _core_hash(ap, "approval_binding_hash", "signal") == \
        ap["approval_binding_hash"]


def test_appdel_approval_no_external_effect_on_failure():
    o = k.prepare(approval_revoked=True)
    for f in ("produced_external_effect", "provider_called", "message_sent",
              "payment_executed", "external_crm_mutated", "delivered_externally",
              "outbox_released"):
        assert o[f] is False


# --- kernel layer: delegation provenance -----------------------------------
def test_appdel_delegation_clean_monotonic_all_checks():
    d = k.clean_outcome()["delegation_capsule"]
    assert d["monotonic"] is True
    assert d["delegation_status"] == "VALID"
    checks = d["checks"]
    for name in ("read_subset", "write_subset", "tool_subset",
                 "resource_subset", "externality_monotonic"):
        assert checks[name] is True
    assert len(checks) == 5


def test_appdel_delegation_broaden_write_not_monotonic():
    o = _degrades({"parent_delegation": {"write_scope": ["a"]},
                   "child_delegation": {"write_scope": ["a", "b"]}},
                  "APPROVAL_SCOPE_EXCEEDED", expected_truth="PARTIAL")
    d = o["delegation_capsule"]
    assert d["monotonic"] is False
    assert d["checks"]["write_subset"] is False
    assert d["delegation_status"] == "INVALID"


def test_appdel_delegation_broaden_read_not_monotonic():
    o = _degrades({"parent_delegation": {"read_scope": ["a"]},
                   "child_delegation": {"read_scope": ["a", "b"]}},
                  "APPROVAL_SCOPE_EXCEEDED")
    assert o["delegation_capsule"]["checks"]["read_subset"] is False


def test_appdel_delegation_broaden_tool_not_monotonic():
    o = _degrades({"parent_delegation": {"tool_scope": ["a"]},
                   "child_delegation": {"tool_scope": ["a", "b"]}},
                  "APPROVAL_SCOPE_EXCEEDED")
    assert o["delegation_capsule"]["checks"]["tool_subset"] is False


def test_appdel_delegation_broaden_resource_not_monotonic():
    o = _degrades({"parent_delegation": {"resource_scope": ["a"]},
                   "child_delegation": {"resource_scope": ["a", "b"]}},
                  "APPROVAL_SCOPE_EXCEEDED")
    assert o["delegation_capsule"]["checks"]["resource_subset"] is False


def test_appdel_delegation_broaden_externality_not_monotonic():
    o = _degrades({"parent_delegation": {"externality_class": 0},
                   "child_delegation": {"externality_class": 1}},
                  "APPROVAL_SCOPE_EXCEEDED")
    assert o["delegation_capsule"]["checks"]["externality_monotonic"] is False


def test_appdel_delegation_reconstructed_from_trace_false():
    d = k.clean_outcome()["delegation_capsule"]
    assert d["reconstructed_from_trace"] is False


def test_appdel_delegation_capsule_hash_recompute():
    d = k.clean_outcome()["delegation_capsule"]
    assert _core_hash(d, "delegation_capsule_hash", "signal") == \
        d["delegation_capsule_hash"]


# --- API layer -------------------------------------------------------------
def test_appdel_api_approval_endpoint(gate):
    wrid, _ = gate.observed_work()
    ap = gate.wo(wrid, "approval").json()["approval_continuity"]
    assert ap["approval_status"] == "VALID"
    assert ap["exact_binding"] is True and ap["fuzzy_matching"] is False


def test_appdel_api_delegation_endpoint(gate):
    wrid, _ = gate.observed_work()
    d = gate.wo(wrid, "delegation").json()["delegation_capsule"]
    assert d["monotonic"] is True
    assert d["delegation_status"] == "VALID"
    assert d["reconstructed_from_trace"] is False


def test_appdel_api_approval_mismatch_invalidates(gate):
    wrid, o = gate.observed_work(approved_action="A", actual_action="B")
    assert o["work_run_state"] != "WORK_OUTCOME_CERTIFIED"
    ap = gate.wo(wrid, "approval").json()["approval_continuity"]
    assert ap["approval_status"] == "INVALID"
    assert "APPROVAL_ACTION_MISMATCH" in o["all_signals"]

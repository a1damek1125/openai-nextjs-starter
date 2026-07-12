"""SP0005 admission engine: contracts, automaton, obligations, state vector +
lattice, lease/TOCTOU, containment, admission. Covers AC-0005-020..071."""
from __future__ import annotations

from tools.safety.contracts import (validate_action_contract,
                                    validate_trajectory_contract)
from tools.safety.automaton import validate_run
from tools.safety.obligations import closure, generate_mandatory
from tools.safety.statevector import (control_class, monotonicity_holds, risk_ge,
                                      evaluate, expected_loss, tail_risk,
                                      normalize_vector)
from tools.safety.lease import (issue_lease, revalidate, material_context_change,
                                safety_context_hash)
from tools.safety.containment import validate_containment, validate_emergency
from tools.safety.admission import evaluate_action
from tools.safety.model import (TRAJECTORY_SAFETY_VIOLATION, PROOF_OBLIGATION_UNKNOWN,
                                PROOF_OBLIGATION_FAILED, SAFETY_TOCTOU_MISMATCH,
                                SAFETY_ADMISSION_LEASE_EXPIRED,
                                SAFETY_ADMISSION_LEASE_INVALID, PROHIBITED_ACTION,
                                INVALID_ACTION_SAFETY_CONTRACT, TAIL_RISK_NOT_CALIBRATED)


def _k(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


def _action(target="X", **kw):
    a = {"action_type": "send", "target": {"target_id": target}, "parameters": {},
         "tenant": "t", "authority": "a", "policy_version": "1", "safety_context": {}}
    a.update(kw)
    return a


# ---- action / trajectory contracts (AC-0005-020..026) ----------------------
def test_irreversible_contract_needs_revalidation_triggers():
    c = {"contract_id": "C", "action_type": "send",
         "irreversibility_class": "IRREVERSIBLE", "proof_obligations": []}
    assert INVALID_ACTION_SAFETY_CONTRACT in _k(validate_action_contract(c))


def test_valid_action_contract():
    c = {"contract_id": "C", "action_type": "send",
         "irreversibility_class": "IRREVERSIBLE", "proof_obligations": ["PO-TARGET"],
         "revalidation_triggers": ["target"]}
    assert not validate_action_contract(c)


# ---- trajectory automaton (AC-0005-027..029) -------------------------------
def _auto():
    return {"automaton_id": "A", "transitions": [
        {"from": "UNVERIFIED", "action": "verify", "to": "APPROVED"},
        {"from": "APPROVED", "action": "effect", "to": "EFFECT"}],
        "forbidden_transitions": [["UNVERIFIED", "effect"]]}


def test_safe_atomic_actions_unsafe_trajectory():
    au = _auto()
    # verify then effect: OK
    assert not validate_run(au, ["UNVERIFIED", "APPROVED", "EFFECT"],
                            ["verify", "effect"])
    # effect straight from unverified: forbidden
    assert TRAJECTORY_SAFETY_VIOLATION in _k(
        validate_run(au, ["UNVERIFIED", "EFFECT"], ["effect"]))


# ---- proof obligations (AC-0005-030..032) ----------------------------------
def test_mandatory_obligations_close_before_allow():
    ok, _ = closure([{"obligation_type": "PO-AUTHORITY", "status": "SATISFIED"}])
    assert ok


def test_unknown_obligation_cannot_be_satisfied():
    ok, f = closure([{"obligation_type": "PO-AUTHORITY", "status": "UNKNOWN"}])
    assert not ok and PROOF_OBLIGATION_UNKNOWN in _k(f)


def test_unsatisfied_obligation_fails():
    ok, f = closure([{"obligation_type": "PO-TENANT", "status": "UNSATISFIED"}])
    assert not ok and PROOF_OBLIGATION_FAILED in _k(f)


# ---- lease binding + TOCTOU + replay (AC-0005-033..051) --------------------
def _lease(**kw):
    base = dict(action=_action(), tenant="t", actor="u", authority={"r": 1},
                context={"target": "X", "consent": "yes"}, trajectory_state={"s": 1},
                policy_version="1", semantic_epoch="e1", issued_at="2026-01-01",
                expires_at="2026-12-31")
    base.update(kw)
    return issue_lease(**base)


def test_lease_binds_fingerprint_tenant_target():
    L = _lease()
    assert L["action_fingerprint"] and L["tenant_id"] == "t" and L["target_fingerprint"]


def test_expired_lease_fails():
    L = _lease(expires_at="2026-02-01")
    ok, f = revalidate(L, action=_action(), tenant="t", actor="u",
                       authority={"r": 1}, context={"target": "X", "consent": "yes"},
                       trajectory_state={"s": 1}, now="2026-06-01")
    assert not ok and SAFETY_ADMISSION_LEASE_EXPIRED in _k(f)


def test_target_change_blocks():
    L = _lease()
    ok, f = revalidate(L, action=_action(target="Y"), tenant="t", actor="u",
                       authority={"r": 1}, context={"target": "X", "consent": "yes"},
                       trajectory_state={"s": 1}, now="2026-06-01")
    assert not ok and SAFETY_TOCTOU_MISMATCH in _k(f)


def test_authority_change_blocks():
    L = _lease()
    ok, f = revalidate(L, action=_action(), tenant="t", actor="u",
                       authority={"r": 2}, context={"target": "X", "consent": "yes"},
                       trajectory_state={"s": 1}, now="2026-06-01")
    assert not ok and SAFETY_TOCTOU_MISMATCH in _k(f)


def test_consent_change_blocks():
    L = _lease()
    ok, f = revalidate(L, action=_action(), tenant="t", actor="u",
                       authority={"r": 1}, context={"target": "X", "consent": "no"},
                       trajectory_state={"s": 1}, now="2026-06-01")
    assert not ok and SAFETY_TOCTOU_MISMATCH in _k(f)


def test_tenant_replay_blocked():
    L = _lease()
    ok, f = revalidate(L, action=_action(), tenant="OTHER", actor="u",
                       authority={"r": 1}, context={"target": "X", "consent": "yes"},
                       trajectory_state={"s": 1}, now="2026-06-01")
    assert not ok and SAFETY_ADMISSION_LEASE_INVALID in _k(f)


def test_matching_context_passes():
    L = _lease()
    ok, f = revalidate(L, action=_action(), tenant="t", actor="u",
                       authority={"r": 1}, context={"target": "X", "consent": "yes"},
                       trajectory_state={"s": 1}, now="2026-06-01")
    assert ok and not f


def test_material_context_change_lists_fields():
    changed = material_context_change({"target": "X", "amount": 1},
                                      {"target": "Y", "amount": 1})
    assert "target" in changed and "amount" not in changed


# ---- state vector + lattice (AC-0005-052..061) -----------------------------
def test_dimensions_distinct_and_non_compensatory():
    assert control_class({"irreversibility": "CRITICAL", "consequence": "LOW"}) == "CC4"
    # a low dim does not average away the critical one
    assert control_class({"irreversibility": "CRITICAL"}) == "CC4"


def test_unknown_not_low():
    assert control_class({"consequence": "UNKNOWN"}) == "CC3"  # not CC1


def test_monotonicity_holds():
    x = {"consequence": "LOW"}
    y = {"consequence": "CRITICAL"}
    assert risk_ge(y, x) and monotonicity_holds(x, y)


def test_hard_prohibition_dominates():
    d, f = evaluate(_action(), {"consequence": "LOW"}, prohibited=True)
    assert d == "DENY" and PROHIBITED_ACTION in _k(f)


def test_expected_loss_advisory_and_tail_not_calibrated():
    assert expected_loss(None, None)["status"] == "NOT_CALIBRATED"
    assert expected_loss(0.1, 100)["advisory"] is True
    assert tail_risk(None)["status"] == TAIL_RISK_NOT_CALIBRATED


# ---- containment (AC-0005-068..071) ----------------------------------------
def test_containment_scope_explicit_and_model_independent():
    assert validate_containment({"boundary_id": "B",
                                 "modeled_action_types": ["send"],
                                 "assumptions": ["boundary mediates all effects"],
                                 "depends_on_model_correctness": False}) == []


def test_containment_depending_on_model_flagged():
    assert validate_containment({"boundary_id": "B",
                                 "modeled_action_types": ["send"],
                                 "assumptions": ["x"],
                                 "depends_on_model_correctness": True})


def test_emergency_containment_no_model_cooperation():
    assert validate_emergency({"emergency_id": "E",
                               "requires_primary_model_cooperation": True})
    assert not validate_emergency({"emergency_id": "E", "enforced_by": "kernel",
                                   "requires_primary_model_cooperation": False})


# ---- admission interface (AC-0005-195..204) --------------------------------
def test_admission_outcomes():
    obs = [{"obligation_type": "PO-AUTHORITY", "status": "SATISFIED"}]
    assert evaluate_action(action=_action(), state_vector={"consequence": "LOW"},
                           obligations=obs)["decision"] == "ALLOW"
    assert evaluate_action(action=_action(), state_vector={}, obligations=obs,
                           prohibited=True)["decision"] == "DENY"
    unk = [{"obligation_type": "PO-AUTHORITY", "status": "UNKNOWN"}]
    assert evaluate_action(action=_action(), state_vector={}, obligations=unk)[
        "decision"] == "REQUIRE_MORE_EVIDENCE"
    assert evaluate_action(action=_action(), state_vector={}, obligations=obs,
                           human_required=True)["decision"] == "REQUIRE_HUMAN_REVIEW"


def test_admission_result_has_reason_codes_and_is_evidence():
    r = evaluate_action(action=_action(), state_vector={"consequence": "LOW"},
                        obligations=[{"obligation_type": "PO-AUTHORITY",
                                      "status": "SATISFIED"}])
    assert r["reason_codes"] and r["classification"] == "EVIDENCE_NOT_AUTHORITY"
    assert r["lease"] is None

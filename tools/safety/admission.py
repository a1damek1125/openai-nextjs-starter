"""Future Runtime Safety Admission Interface (SP0005 D-0005-82/83/84, §11.1,
INV-0005-26/27).

Defines the CONTRACT for a future evaluate_action(...) — it does NOT enable
runtime effects (INV-0005-27). Outcomes: ALLOW / DENY / ABSTAIN /
REQUIRE_MORE_EVIDENCE / REQUIRE_HUMAN_REVIEW / REQUIRE_SPECIALIST_REVIEW /
QUARANTINE (AC-0005-196..202). Admission produces EVIDENCE (reason codes, proof
results, lease-or-none); a lease is evidence, not authority by itself
(D-0005-84). This module wires the design-time pieces together to prove the
decision logic without opening any effect.
"""
from __future__ import annotations

from .model import ADMISSION_OUTCOMES
from .statevector import control_class, evaluate as eval_state
from .obligations import closure
from .automaton import validate_run


def evaluate_action(*, action: dict, state_vector: dict, obligations: list[dict],
                    prohibited: bool = False, prohibited_practice: bool = False,
                    trajectory=None, human_required: bool = False,
                    specialist_required: bool = False,
                    unresolved_unknowns: bool = False) -> dict:
    """Deterministic design-time admission decision. Returns the outcome + reason
    codes + proof results (§11.1). No effect is executed."""
    reasons: list[str] = []
    # 1. hard prohibition dominates (INV-0005-10)
    decision_class, state_findings = eval_state(
        action, state_vector, prohibited=prohibited,
        prohibited_practice=prohibited_practice)
    if prohibited:
        return _result("DENY", ["PROHIBITED_ACTION"], obligations, None)
    # 2. trajectory safety
    if trajectory is not None:
        tf = validate_run(trajectory["automaton"], trajectory["states"],
                          trajectory["actions"])
        if tf:
            return _result("DENY", ["TRAJECTORY_SAFETY_VIOLATION"], obligations,
                           None)
    # 3. proof obligation closure
    ok, po_findings = closure(obligations)
    if not ok:
        # UNKNOWN obligations -> need more evidence; failed -> deny
        kinds = {f.kind for f in po_findings}
        if "PROOF_OBLIGATION_FAILED" in kinds:
            return _result("DENY", sorted(kinds), obligations, None)
        return _result("REQUIRE_MORE_EVIDENCE", sorted(kinds), obligations, None)
    # 4. review requirements
    if specialist_required or prohibited_practice:
        return _result("REQUIRE_SPECIALIST_REVIEW", ["SPECIALIST_REVIEW"],
                       obligations, None)
    if human_required:
        return _result("REQUIRE_HUMAN_REVIEW", ["HUMAN_REVIEW"], obligations, None)
    if unresolved_unknowns:
        return _result("ABSTAIN", ["UNRESOLVED_UNKNOWN"], obligations, None)
    # 5. eligible -> allow (a lease would be issued by lease.issue_lease)
    return _result("ALLOW", ["ALL_OBLIGATIONS_SATISFIED",
                             f"CONTROL_CLASS_{decision_class}"], obligations,
                   decision_class)


def _result(outcome: str, reasons: list[str], obligations: list[dict],
            control_class_result) -> dict:
    assert outcome in ADMISSION_OUTCOMES
    return {
        "decision": outcome,
        "reason_codes": reasons,
        "satisfied_obligations": sorted(
            o.get("obligation_type") for o in obligations
            if o.get("status") == "SATISFIED"),
        "failed_obligations": sorted(
            o.get("obligation_type") for o in obligations
            if o.get("status") in ("UNSATISFIED", "UNKNOWN", "STALE")),
        "control_class": control_class_result,
        "lease": None,   # SP0005 issues no runtime lease; contract only
        "classification": "EVIDENCE_NOT_AUTHORITY",
    }

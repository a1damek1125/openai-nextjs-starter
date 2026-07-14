"""Work Admission Gate (SP0006 §9, §11.1, D-0006-04/05). Conjunctive and fail-
closed: Admitted(W) = AND of all predicates; a critical UNKNOWN can never become
PASS. Goal validity does not authorize action (D-0006-05). Outputs one of
ADMITTED / AMBIGUOUS / CONFLICTED / REJECTED / REQUIRES_CLARIFICATION.
"""
from __future__ import annotations

from .model import Finding, P0, P1, Report
from .workorder import validate_work_order
from .ambiguity import analyze_ambiguity, analyze_conflict


# each predicate returns [] when it passes, or findings when it fails.
def _p_identity(w):
    return [] if w.get("work_order_id") and w.get("tenant_id") \
        and w.get("requester_id") else [
            Finding("INVALID_WORK_SCHEMA", P1, w.get("work_order_id", "-"),
                    "identity fields incomplete", {})]


def _p_outcome(w):
    from .model import UNDEFINED_OUTCOME
    return [] if w.get("outcome_contract") else [
        Finding(UNDEFINED_OUTCOME, P1, w.get("work_order_id", "-"),
                "no outcome contract (D-0006-10)", {})]


def _p_owner(w):
    from .model import UNDEFINED_ACCOUNTABLE_OWNER
    return [] if w.get("accountable_owner_id") else [
        Finding(UNDEFINED_ACCOUNTABLE_OWNER, P1, w.get("work_order_id", "-"),
                "no accountable owner", {})]


def _p_purpose(w):
    pp = w.get("privacy_purpose")
    if w.get("processes_data", True) and not pp:
        return [Finding("PURPOSE_BINDING_FAILURE", P1,
                        w.get("work_order_id", "-"),
                        "data-processing work has no privacy purpose", {})]
    return []


def _p_capability_ceiling(w):
    return [] if isinstance(w.get("capability_ceiling", {}), dict) else [
        Finding("INVALID_WORK_SCHEMA", P1, w.get("work_order_id", "-"),
                "capability ceiling malformed", {})]


def _p_budget(w):
    return [] if w.get("budget_vector") is not None else [
        Finding("INVALID_WORK_SCHEMA", P1, w.get("work_order_id", "-"),
                "no budget vector", {})]


def _p_no_context_authority(w):
    from .model import CONTEXT_USED_AS_AUTHORITY, MEMORY_USED_AS_AUTHORITY
    out = []
    if w.get("authority_from_context"):
        out.append(Finding(CONTEXT_USED_AS_AUTHORITY, P0,
                           w.get("work_order_id", "-"),
                           "context used as authority (INV-0006-04)", {}))
    if w.get("authority_from_memory"):
        out.append(Finding(MEMORY_USED_AS_AUTHORITY, P0,
                           w.get("work_order_id", "-"),
                           "memory used as authority (INV-0006-05)", {}))
    return out


PREDICATES = (_p_identity, _p_outcome, _p_owner, _p_purpose,
              _p_capability_ceiling, _p_budget, _p_no_context_authority)


def admit(work: dict, *, sub_findings: list[Finding] | None = None) -> dict:
    """Deterministic work admission. `sub_findings` carries pre-validated
    subsystem findings (delegation/lease/budget/approval/safety/technology/
    dependency) so admission remains conjunctive across the whole envelope."""
    rep = Report()
    rep.extend(validate_work_order(work))
    for p in PREDICATES:
        rep.extend(p(work))
    if sub_findings:
        rep.extend(sub_findings)

    amb = analyze_ambiguity(work)
    con = analyze_conflict(work)

    decision = _decide(rep, amb, con)
    return {
        "work_order_id": work.get("work_order_id"),
        "decision": decision,
        "valid": rep.valid and decision == "ADMITTED",
        "counts": rep.counts(),
        "findings": [f.to_dict() for f in rep.findings],
        "ambiguities": [f.to_dict() for f in amb],
        "conflicts": [f.to_dict() for f in con],
        "classification": "EVIDENCE_NOT_AUTHORITY",
    }


def _decide(rep: Report, amb, con) -> str:
    blocking_amb = [f for f in amb if f.details.get("blocking")]
    blocking_con = [f for f in con if f.details.get("blocking")]
    if blocking_con:
        return "CONFLICTED"
    if blocking_amb:
        # undefined-outcome / undefined-owner style gaps are clarifiable
        return "REQUIRES_CLARIFICATION"
    if not rep.valid:
        return "REJECTED"
    return "ADMITTED"

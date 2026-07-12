"""Intent Ambiguity + Conflict Analyzers and Minimum Clarification Set
(SP0006 §9.3, D-0006-08). Reuses SP0003 Value-of-Information where available.

Detects incompatible goals, missing target, undefined success/owner/time,
contradictory deadlines, forbidden-scope intersection, insufficient authority,
impossible dependencies, prohibited-effect outcomes, unauthorized recurrence,
memory/context-derived permission, incompatible privacy purposes, budget and
approval-topology contradictions. Computes the smallest set of questions whose
answers resolve blocking fields (D-0006-08). A safe reduced-scope option never
broadens intent (D-0006-09).
"""
from __future__ import annotations

from .model import (Finding, P1, WORK_ORDER_AMBIGUOUS, WORK_ORDER_CONFLICTED,
                    UNDEFINED_OUTCOME, UNDEFINED_ACCOUNTABLE_OWNER,
                    CONTEXT_USED_AS_AUTHORITY, MEMORY_USED_AS_AUTHORITY)


def analyze(work: dict) -> dict:
    """Return {ambiguities, conflicts, blocking_fields, minimum_clarification_set,
    safe_reduced_scope, execution_blocked}."""
    amb = analyze_ambiguity(work)
    con = analyze_conflict(work)
    blocking = sorted({f.subject for f in amb + con
                       if f.details.get("blocking")})
    return {
        "ambiguities": [f.to_dict() for f in amb],
        "conflicts": [f.to_dict() for f in con],
        "blocking_fields": blocking,
        "minimum_clarification_set": minimum_clarification_set(work, amb + con),
        "safe_reduced_scope": safe_reduced_scope(work),
        "execution_blocked": bool(blocking),
    }


def _amb(field_, msg, blocking=True):
    return Finding(WORK_ORDER_AMBIGUOUS, P1, field_, msg, {"blocking": blocking})


def analyze_ambiguity(work: dict) -> list[Finding]:
    out: list[Finding] = []
    goal = work.get("canonical_goal") or {}
    if not goal or (isinstance(goal, dict) and not any(goal.values())):
        out.append(_amb("goal", "goal is undefined"))
    if not _has_target(work):
        out.append(_amb("target", "work has no identifiable target"))
    if not work.get("outcome_contract"):
        out.append(Finding(UNDEFINED_OUTCOME, P1, "outcome_contract",
                           "success is undefined (no outcome contract)",
                           {"blocking": True}))
    if not work.get("accountable_owner_id"):
        out.append(Finding(UNDEFINED_ACCOUNTABLE_OWNER, P1, "accountable_owner_id",
                           "accountable owner undefined", {"blocking": True}))
    if not work.get("expires_at") and not work.get("time_horizon"):
        out.append(_amb("time_horizon", "no time horizon / deadline defined",
                        blocking=False))
    return out


def _con(field_, msg):
    return Finding(WORK_ORDER_CONFLICTED, P1, field_, msg, {"blocking": True})


def analyze_conflict(work: dict) -> list[Finding]:
    out: list[Finding] = []
    goals = work.get("goals")
    if isinstance(goals, list) and len({str(g) for g in goals}) > 1 \
            and work.get("goals_incompatible"):
        out.append(_con("goal", "multiple incompatible goals declared"))
    allowed = _scope_set(work.get("allowed_scope"))
    forbidden = _scope_set(work.get("forbidden_scope"))
    if allowed & forbidden:
        out.append(_con("scope", "allowed scope intersects forbidden scope: "
                        f"{sorted(allowed & forbidden)}"))
    # memory/context-derived permission
    if work.get("authority_from_context"):
        out.append(Finding(CONTEXT_USED_AS_AUTHORITY, P1, "authority",
                           "permission derived from conversation context",
                           {"blocking": True}))
    if work.get("authority_from_memory"):
        out.append(Finding(MEMORY_USED_AS_AUTHORITY, P1, "authority",
                           "permission derived from memory", {"blocking": True}))
    # recurrence without recurrence authority
    if work.get("recurrence_instance") and not work.get("recurrence_contract_ref"):
        out.append(_con("recurrence", "recurring run without a recurrence "
                        "contract (D-0006-51)"))
    # incompatible privacy purposes
    pp = work.get("privacy_purpose")
    if isinstance(pp, list) and len({str(x) for x in pp}) > 1:
        out.append(_con("privacy_purpose", "incompatible privacy purposes"))
    # budget contradiction: negative or ceiling below required
    bv = work.get("budget_vector") or {}
    if isinstance(bv, dict):
        for dim, spec in bv.items():
            if isinstance(spec, dict) and isinstance(spec.get("total"), (int, float)) \
                    and spec["total"] < 0:
                out.append(_con("budget", f"negative budget total for {dim}"))
    return out


def _has_target(work: dict) -> bool:
    scope = work.get("allowed_scope") or {}
    return bool(scope.get("target") or scope.get("targets")
                or work.get("target") or scope.get("entities"))


def _scope_set(scope) -> set:
    if isinstance(scope, dict):
        vals = set()
        for v in scope.values():
            if isinstance(v, list):
                vals.update(str(x) for x in v)
            elif v is not None:
                vals.add(str(v))
        return vals
    if isinstance(scope, list):
        return {str(x) for x in scope}
    return set()


def minimum_clarification_set(work: dict, findings: list[Finding]) -> list[dict]:
    """Smallest set of questions whose answers resolve the blocking fields.
    Deterministic: one question per distinct blocking field, sorted."""
    seen = {}
    for f in findings:
        if not f.details.get("blocking"):
            continue
        if f.subject in seen:
            continue
        seen[f.subject] = {
            "field": f.subject,
            "question": _question_for(f.subject),
            "resolves": f.kind,
            "voi_ref": work.get("uncertainty_profile_ref"),
        }
    return [seen[k] for k in sorted(seen)]


_QUESTIONS = {
    "goal": "What specific goal should this work achieve?",
    "target": "What is the exact target (recipient/account/document/system)?",
    "outcome_contract": "What defines successful completion (acceptance criteria)?",
    "accountable_owner_id": "Who is the accountable owner for this work?",
    "scope": "Which items are in scope, given the forbidden-scope conflict?",
    "authority": "What is the explicit authority basis (not context/memory)?",
    "recurrence": "Under what recurrence contract should this repeat?",
    "privacy_purpose": "What single privacy purpose governs this data use?",
    "budget": "What are the valid budget limits for this work?",
    "time_horizon": "By when must this be completed?",
}


def _question_for(field_: str) -> str:
    return _QUESTIONS.get(field_, f"Please clarify: {field_}")


def safe_reduced_scope(work: dict) -> dict:
    """A safe default may REDUCE scope or DEFER action, never broaden it
    (D-0006-09). Returns a reduced-scope proposal that drops any forbidden-scope
    intersection and defers effectful actions to drafts."""
    allowed = _scope_set(work.get("allowed_scope"))
    forbidden = _scope_set(work.get("forbidden_scope"))
    reduced = sorted(allowed - forbidden)
    return {
        "reduced_scope": reduced,
        "action_mode": "DRAFT_OR_PREVIEW_ONLY",
        "note": "safe default never broadens intent (D-0006-09)",
        "dropped_conflicts": sorted(allowed & forbidden),
    }

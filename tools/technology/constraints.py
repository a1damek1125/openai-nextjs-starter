"""Hard Requirement Gate (SP0004 D-0004-05/06, §11.2, INV-0004-07).

Hard constraints precede optimization: only candidates that PASS every hard
requirement are feasible. A critical UNKNOWN is NOT a PASS (D-0004-06,
AC-0004-028) — it may block selection. A hard-requirement failure can never be
offset by a score (§12.6).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, CONSTRAINT_RESULTS,
                    HARD_REQUIREMENT_FAILED, MISSING_HARD_REQUIREMENT)


def candidate_feasible(candidate: dict, hard_requirements: list[str]
                       ) -> tuple[bool, list[str], list[str]]:
    """Return (feasible, failed, unknown). A candidate is feasible iff every hard
    requirement is explicitly PASS. FAIL or UNKNOWN → infeasible."""
    results = candidate.get("hard_constraint_results", {})
    failed, unknown = [], []
    for req in hard_requirements:
        r = results.get(req, "UNKNOWN")
        if r == "FAIL":
            failed.append(req)
        elif r != "PASS":   # UNKNOWN or anything not PASS
            unknown.append(req)
    return (not failed and not unknown), failed, unknown


def feasible_set(candidates: list[dict], hard_requirements: list[str]
                 ) -> list[dict]:
    return [c for c in candidates
            if candidate_feasible(c, hard_requirements)[0]]


def evaluate_hard_constraints(decision: dict) -> list[Finding]:
    out: list[Finding] = []
    hard = decision.get("hard_constraints", [])
    did = decision.get("decision_id", "-")
    sel = decision.get("selected_candidate")
    for c in decision.get("candidates", []):
        cid = c.get("candidate_id", "-")
        results = c.get("hard_constraint_results", {})
        for req in hard:
            if req not in results:
                out.append(Finding(MISSING_HARD_REQUIREMENT, P1, f"{did}:{cid}",
                                   f"candidate does not evaluate hard "
                                   f"requirement {req!r}", {}))
        feasible, failed, unknown = candidate_feasible(c, hard)
        # the SELECTED candidate must be feasible; a failed/unknown hard
        # requirement on the selected candidate is a hard error (INV-0004-07)
        if cid == sel and not feasible:
            out.append(Finding(HARD_REQUIREMENT_FAILED, P0, f"{did}:{cid}",
                               f"selected candidate fails/leaves-unknown hard "
                               f"requirements failed={failed} unknown={unknown}",
                               {"failed": failed, "unknown": unknown}))
    return out

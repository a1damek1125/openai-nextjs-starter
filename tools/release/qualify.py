"""Hard qualification and the unknown budget (SP0009 §11.5, §12.1, D-0009-06,
AC-0009-070/071).

CandidateQualifiable = AND(every required hard gate PASS, every non-waivable
obligation CLOSED, hard-scope unknown budget == 0, artifact closure COMPLETE,
no open blocking defeater). A pure conjunction — nothing compensates, nothing
averages, UNKNOWN blocks. The unknown budget makes epistemic debt explicit:
every unresolved fact is counted and classed; hard-scope unknowns must be ZERO
before qualification (D-0009-06).
"""
from __future__ import annotations

from .model import Finding, P0

HARD_UNKNOWN_CLASSES = frozenset({
    "tenant", "authority", "safety", "proof", "supply_chain",
    "artifact_identity", "trust_root",
})


def unknown_budget(unknowns: list) -> dict:
    """unknowns: [{class, subject, description}]. Counts by class; hard-scope
    unknowns are those in HARD_UNKNOWN_CLASSES."""
    by_class: dict = {}
    for u in unknowns:
        by_class.setdefault(u.get("class", "unclassified"), []).append(
            u.get("subject"))
    hard = {c: subs for c, subs in by_class.items()
            if c in HARD_UNKNOWN_CLASSES}
    return {"total": len(unknowns),
            "by_class": {c: len(s) for c, s in sorted(by_class.items())},
            "hard_scope_count": sum(len(s) for s in hard.values()),
            "hard_scope": {c: sorted(filter(None, s))
                           for c, s in sorted(hard.items())}}


def qualify(*, gate_verdict: dict, dod_closure: dict, unknown_budget: dict,
            artifact_closures: list, open_defeaters: list) -> dict:
    """The §11.5 conjunction. Each conjunct is evaluated strictly (`is True`
    where boolean; explicit status strings elsewhere) so a truthy-string can
    never satisfy a hard requirement."""
    conjuncts = {
        "all_required_hard_gates_pass":
            gate_verdict.get("qualifiable") is True,
        "all_non_waivable_obligations_closed":
            dod_closure.get("done") is True
            or (not dod_closure.get("open_hard")
                and not dod_closure.get("invalid_waivers")),
        "hard_scope_unknowns_zero":
            unknown_budget.get("hard_scope_count") == 0,
        "artifact_closure_complete":
            all(c.get("closure_status") == "COMPLETE"
                for c in artifact_closures) and bool(artifact_closures),
        "no_open_blocking_defeater":
            not any(d.get("status") == "BLOCKING" for d in open_defeaters),
    }
    return {"qualifiable": all(v is True for v in conjuncts.values()),
            "conjuncts": conjuncts}


def qualification_findings(result: dict, subject: str) -> list[Finding]:
    out: list[Finding] = []
    for name, ok in sorted(result.get("conjuncts", {}).items()):
        if ok is not True:
            out.append(Finding(
                "RELEASE_INVALIDATED", P0, subject,
                f"qualification conjunct failed: {name} — no automation may "
                "turn unknown, stale or failed hard evidence into permission",
                {"conjunct": name}))
    return out

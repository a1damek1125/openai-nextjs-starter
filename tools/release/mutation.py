"""Mutation campaign accounting (SP0009 §11.10, D-0009-23, AC-0009-116..120).

Adequacy counts ONLY non-equivalent mutants: kill rate = killed non-equivalent
/ total non-equivalent. Equivalent mutants (semantically identical to the
original — unkillable in principle) and subsumed mutants (killed by exactly the
same test set as another mutant) are recorded SEPARATELY, never folded into the
denominator to inflate adequacy, and never used to hide a surviving mutant.
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P1

MUTANT_STATUSES = ("KILLED", "SURVIVED", "EQUIVALENT", "INVALID", "SUBSUMED")


def mutant(*, mutant_id: str, target: str, operator: str, status: str,
           killed_by=None, equivalent_reason=None, subsumed_by=None) -> dict:
    if status not in MUTANT_STATUSES:
        raise ValueError(f"unknown mutant status {status!r}")
    return {"mutant_id": mutant_id, "target": target, "operator": operator,
            "status": status, "killed_by": killed_by,
            "equivalent_reason": equivalent_reason,
            "subsumed_by": subsumed_by}


def adequacy(mutants: list) -> dict:
    """§11.10 kill rate over the non-equivalent, non-invalid population."""
    killed = [m for m in mutants if m["status"] == "KILLED"]
    survived = [m for m in mutants if m["status"] == "SURVIVED"]
    equivalent = [m for m in mutants if m["status"] == "EQUIVALENT"]
    invalid = [m for m in mutants if m["status"] == "INVALID"]
    subsumed = [m for m in mutants if m["status"] == "SUBSUMED"]
    non_equiv_total = len(killed) + len(survived) + len(subsumed)
    kill_rate = ((len(killed) + len(subsumed)) / non_equiv_total) \
        if non_equiv_total else None
    result = {
        "total": len(mutants),
        "killed": len(killed),
        "survived": [m["mutant_id"] for m in survived],
        "equivalent": [m["mutant_id"] for m in equivalent],
        "invalid": [m["mutant_id"] for m in invalid],
        "subsumed": [m["mutant_id"] for m in subsumed],
        "non_equivalent_total": non_equiv_total,
        "kill_rate": round(kill_rate, 6) if kill_rate is not None else None,
        "adequate": non_equiv_total > 0 and not survived,
    }
    result["adequacy_hash"] = hash_obj(result)
    return result


def adequacy_findings(result: dict) -> list[Finding]:
    out: list[Finding] = []
    for mid in result.get("survived", []):
        out.append(Finding(
            "MUTATION_SURVIVED", P1, mid,
            "non-equivalent mutant survived the test suite: the guarded "
            "behavior is not actually locked (D-0009-23)", {}))
    return out

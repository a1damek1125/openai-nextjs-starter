"""Assurance resilience — N-1 / N-K removal analysis (SP0010 FUNCTION M, §10.9,
§11.12, §12.9, D-0010-21/22, AC-0010-128..140).

Diagnostic (unless policy marks it mandatory): for each critical claim, what
happens when one — or a bounded k — assurance element is removed (a verifier, an
evidence trust domain, a provider adapter, a registry projection, a control)?
A claim whose support collapses on any single removal is a SINGLE_POINT_OF_
ASSURANCE. Redundancy is NOT correctness (D-0010-21); this measures fragility,
not truth. Exact enumeration and bounded sampling are kept distinct — exactness
is claimed only when the full removal set was enumerated.
"""
from __future__ import annotations

from itertools import combinations

from .canon import hash_obj
from .model import Finding, P2, RESILIENCE_CLASSES

MAX_ENUM = 200


def analyze_claim(claim_id: str, support_sets: list, *,
                  element_domains: dict, remove_class: str,
                  k: int = 1) -> dict:
    """support_sets: list of evidence-atom-id sets that each independently
    support the claim. element_domains: atom_id -> element (of remove_class).
    Removing a set X of elements kills a support set iff the set contains an
    atom mapped to a removed element. The claim survives X iff >=1 support set
    is untouched."""
    elements = sorted({element_domains[a] for s in support_sets for a in s
                       if a in element_domains})
    if not support_sets:
        return {"claim_id": claim_id, "classification": "NOT_EVALUATED",
                "remove_class": remove_class}

    def survives(removed: set) -> bool:
        for s in support_sets:
            if not any(element_domains.get(a) in removed for a in s):
                return True
        return False

    combos = list(combinations(elements, k)) if len(elements) >= k else []
    exact = len(combos) <= MAX_ENUM
    tested = combos[:MAX_ENUM]
    fragile = [sorted(c) for c in tested if not survives(set(c))]
    if not tested:
        cls = "NOT_EVALUATED"
    elif not fragile:
        cls = ("RESILIENT_TO_CONFIGURED_K_LOSS" if k > 1
               else "RESILIENT_TO_ONE_DOMAIN_LOSS")
    else:
        cls = "SINGLE_POINT_OF_ASSURANCE" if k == 1 else \
            "RESILIENT_TO_CONFIGURED_K_LOSS"
    if not exact:
        cls = "LIMIT_REACHED"
    assert cls in RESILIENCE_CLASSES
    return {"claim_id": claim_id, "remove_class": remove_class,
            "configured_k": k, "elements": elements,
            "fragile_removals": fragile, "exact": exact,
            "classification": cls}


def resilience_findings(results: list, *, mandatory: bool = False
                        ) -> list[Finding]:
    """Diagnostic P2 unless a policy marks resilience mandatory."""
    out: list[Finding] = []
    for rec in results:
        if rec["classification"] == "SINGLE_POINT_OF_ASSURANCE":
            out.append(Finding(
                "ASSURANCE_SINGLE_POINT_OF_FAILURE", P2, rec["claim_id"],
                f"claim support collapses on removing one "
                f"{rec['remove_class']}: single point of assurance "
                "(diagnostic; redundancy is not correctness, D-0010-21)", rec))
    return out


def resilience_root(results: list) -> str:
    return hash_obj([(r["claim_id"], r.get("classification")) for r in results])

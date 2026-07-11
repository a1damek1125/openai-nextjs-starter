"""World Assumption contract (SP0002 D-0002-09, §20.4).

OPEN_WORLD: absence of a fact does NOT imply false (unknown).
CLOSED_WORLD: under an explicitly bounded scope, not-known => false.
PARTIAL_WORLD: completeness is conditional/domain-scoped — needs a declared scope.
Critical for LGGT, completion rules, eligibility, compliance, retrieval.
"""
from __future__ import annotations

from typing import Any

TRUE, FALSE, UNKNOWN = "TRUE", "FALSE", "UNKNOWN"


def evaluate_absence(world_assumption: str, present: bool, *,
                     scope_declared: bool = False) -> str:
    """Interpret the ABSENCE of a positive fact under a world assumption."""
    if present:
        return TRUE
    if world_assumption == "OPEN_WORLD":
        return UNKNOWN                       # absence != false
    if world_assumption == "CLOSED_WORLD":
        return FALSE                         # bounded scope: not known => false
    if world_assumption == "PARTIAL_WORLD":
        return FALSE if scope_declared else UNKNOWN
    return UNKNOWN


def requires_scope(world_assumption: str) -> bool:
    return world_assumption == "PARTIAL_WORLD"


def validate_world_use(concept: dict) -> list[str]:
    """PARTIAL_WORLD concepts must declare a scope in temporal/state semantics."""
    errs: list[str] = []
    wa = concept.get("world_assumption")
    if wa == "PARTIAL_WORLD":
        ss = concept.get("state_semantics", {})
        ts = concept.get("temporal_semantics", {})
        inv = concept.get("semantic_invariants", [])
        text = " ".join(str(x) for x in (list(ss.values()) + list(ts.values()) + inv))
        if "scope" not in text.lower() and "bounded" not in text.lower() \
                and "conditional" not in text.lower():
            # advisory: partial-world without an explicit declared scope
            errs.append(f"{concept['canonical_key']}: PARTIAL_WORLD without a "
                        f"declared scope")
    return errs

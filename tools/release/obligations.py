"""Obligation hypergraph and Definition-of-Done closure (SP0009 §10.5,
FUNCTION O, D-0009-10/46, AC-0009-059, 206..211).

The hypergraph: one obligation may require several evidence items and one
evidence item may support several obligations, but evidence support never
merges obligation MEANINGS — each obligation closes only when ITS OWN
requirements are individually satisfied. DONE is proof-obligation closure over
every applicable obligation for the change type; a merge event is merely one
possible implementation signal and never implies Done (INV-0009-7).
"""
from __future__ import annotations

from .model import Finding, P0, P1

# Change-type DoD profiles (AC-0009-045): which obligation types apply.
DOD_OBLIGATION_TYPES = (
    "IMPLEMENTATION", "CONTRACT", "SEMANTICS", "TESTS", "COMPATIBILITY",
    "SAFETY", "AUTHORITY", "TENANT_ISOLATION", "MIGRATION", "DOCUMENTATION",
    "OBSERVABILITY", "SUPPLY_CHAIN", "ROLLBACK_OR_FORWARD_FIX",
    "KNOWN_LIMITATIONS", "OWNERSHIP", "PROOF",
)

DOD_PROFILES = {
    "CONTRACT_CHANGE": ("IMPLEMENTATION", "CONTRACT", "SEMANTICS", "TESTS",
                        "COMPATIBILITY", "DOCUMENTATION",
                        "ROLLBACK_OR_FORWARD_FIX", "OWNERSHIP", "PROOF"),
    "AUTHORITY_CHANGE": ("IMPLEMENTATION", "AUTHORITY", "TENANT_ISOLATION",
                         "SAFETY", "TESTS", "DOCUMENTATION", "OWNERSHIP",
                         "PROOF"),
    "MIGRATION_CHANGE": ("IMPLEMENTATION", "MIGRATION", "TESTS",
                         "ROLLBACK_OR_FORWARD_FIX", "DOCUMENTATION",
                         "OWNERSHIP", "PROOF"),
    "DEPENDENCY_CHANGE": ("IMPLEMENTATION", "SUPPLY_CHAIN", "TESTS",
                          "OWNERSHIP", "PROOF"),
    "CI_WORKFLOW_CHANGE": ("IMPLEMENTATION", "SUPPLY_CHAIN", "TESTS",
                           "OWNERSHIP", "PROOF"),
    "AI_CLOSURE_CHANGE": ("IMPLEMENTATION", "TESTS", "DOCUMENTATION",
                          "KNOWN_LIMITATIONS", "OWNERSHIP", "PROOF"),
    "SEMANTIC_CHANGE": ("IMPLEMENTATION", "SEMANTICS", "TESTS",
                        "DOCUMENTATION", "OWNERSHIP", "PROOF"),
    "GOVERNANCE_TOOLING_CHANGE": ("IMPLEMENTATION", "TESTS", "DOCUMENTATION",
                                  "OWNERSHIP", "PROOF"),
    "TEST_CHANGE": ("IMPLEMENTATION", "TESTS", "OWNERSHIP"),
    "DOCS_CHANGE": ("DOCUMENTATION", "OWNERSHIP"),
    "UNKNOWN_CHANGE": DOD_OBLIGATION_TYPES,   # unknown = everything applies
}

# non-waivable obligation types (INV-0009-42)
NON_WAIVABLE_OBLIGATIONS = frozenset({
    "AUTHORITY", "TENANT_ISOLATION", "SAFETY", "PROOF", "MIGRATION",
})


def obligations_for(change_classes: list, candidate_genome: str) -> list:
    """Instantiate the DoD obligation set for a classified change."""
    types: set = set()
    for cls in change_classes:
        types.update(DOD_PROFILES.get(cls, ()))
    out = []
    for t in sorted(types):
        out.append({
            "obligation_id": f"OB-{t}",
            "candidate_genome": candidate_genome,
            "obligation_type": t,
            "required_by": sorted(c for c in change_classes
                                  if t in DOD_PROFILES.get(c, ())),
            "evidence_requirements": [f"evidence:{t.lower()}"],
            "status": "OPEN",
            "evidence_refs": [],
            "owner": "release",
            "waivable": t not in NON_WAIVABLE_OBLIGATIONS,
            "closed_at": None,
        })
    return out


def close_obligation(ob: dict, evidence_refs: list, *, closed_at: str) -> dict:
    """Close one obligation with its own evidence. Requirements must each be
    matched by at least one evidence ref (the hypergraph edge); shared evidence
    is fine, missing evidence is not."""
    missing = [r for r in ob["evidence_requirements"]
               if not any(r in (e.get("supports") or []) or e.get("ref") == r
                          for e in evidence_refs)]
    if missing:
        raise ValueError(f"obligation {ob['obligation_id']} evidence "
                         f"requirements unmet: {missing}")
    after = dict(ob)
    after["status"] = "CLOSED"
    after["evidence_refs"] = [e.get("ref") for e in evidence_refs]
    after["closed_at"] = closed_at
    return after


def dod_closure(obligations: list, *, waivers: dict | None = None) -> dict:
    """DoD closure (§12.11): every required non-waived obligation CLOSED, every
    waiver valid, no non-waivable obligation open or waived."""
    waivers = waivers or {}
    open_hard, open_soft, bad_waivers = [], [], []
    for ob in obligations:
        if ob["status"] == "CLOSED":
            continue
        if ob["status"] == "WAIVED" or ob["obligation_id"] in waivers:
            if not ob.get("waivable", False):
                bad_waivers.append(ob["obligation_id"])
            elif (waivers.get(ob["obligation_id"]) or {}).get("status") \
                    != "ACTIVE":
                bad_waivers.append(ob["obligation_id"])
            continue
        if ob.get("waivable", False):
            open_soft.append(ob["obligation_id"])
        else:
            open_hard.append(ob["obligation_id"])
    closed = not open_hard and not open_soft and not bad_waivers
    return {"done": closed, "open_hard": sorted(open_hard),
            "open": sorted(open_soft),
            "invalid_waivers": sorted(bad_waivers)}


def dod_findings(closure: dict, *, merged: bool = False) -> list[Finding]:
    out: list[Finding] = []
    for ob in closure.get("open_hard", []):
        out.append(Finding(
            "DOD_OBLIGATION_OPEN", P0, ob,
            "non-waivable DoD obligation is open; DONE is blocked "
            "(merge does not imply Done, AC-0009-209)", {"merged": merged}))
    for ob in closure.get("open", []):
        out.append(Finding(
            "DOD_OBLIGATION_OPEN", P1, ob,
            "DoD obligation is open; DONE is blocked", {"merged": merged}))
    for ob in closure.get("invalid_waivers", []):
        out.append(Finding(
            "NON_WAIVABLE_WAIVER_REJECTED", P0, ob,
            "obligation waiver invalid or obligation is non-waivable", {}))
    return out


def hypergraph(obligations: list, evidence_items: list) -> dict:
    """The explicit bipartite obligation<->evidence hypergraph (AC-0009-059)."""
    edges = []
    for ob in obligations:
        for req in ob["evidence_requirements"]:
            for ev in evidence_items:
                if req in (ev.get("supports") or []) or ev.get("ref") == req:
                    edges.append({"obligation": ob["obligation_id"],
                                  "evidence": ev.get("ref"),
                                  "requirement": req})
    return {"obligations": [o["obligation_id"] for o in obligations],
            "evidence": sorted({e.get("ref") for e in evidence_items}),
            "edges": sorted(edges, key=lambda e: (e["obligation"],
                                                  str(e["evidence"])))}

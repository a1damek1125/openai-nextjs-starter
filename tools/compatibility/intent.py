"""Compatibility Change Intent and the cross-graph Impact Cone
(SP0007 §11.12, D-0007-65/66, AC-0007-189/190).

A material contract evolution is declared BEFORE it lands (D-0007-65): the
intent names the changed surface, both versions, the compatibility directions
under evaluation, the known consumers, and its migration / deprecation /
rollback / proof / security posture — fail-closed, every field declared. The
impact cone (D-0007-66) projects the change across the producer-consumer
graph and the sibling governance graphs (architecture, semantics, program,
technology, safety, governed work, proofs). The cone is ADVISORY reach
analysis, never a gate by itself.
"""
from __future__ import annotations

from .model import Finding, P1, DIRECTIONS, INVALID_COMPAT_SCHEMA

_INTENT_REQUIRED = ("surface", "old_version", "new_version", "consumers",
                    "migration_plan_ref", "proof_impact", "security_impact")
_CROSS_GRAPH_REFS = ("architecture_refs", "semantic_refs", "program_refs",
                     "technology_refs", "safety_refs", "governed_work_refs",
                     "proof_refs")


def validate_intent(ci: dict) -> list[Finding]:
    """A material evolution declares its full compatibility posture up front
    (D-0007-65, AC-0007-189). Missing declarations fail closed as P1."""
    out: list[Finding] = []
    iid = str(ci.get("intent_id") or ci.get("contract_id") or "-")
    for fld in _INTENT_REQUIRED:
        if ci.get(fld) in (None, ""):
            out.append(Finding(INVALID_COMPAT_SCHEMA, P1, iid,
                               f"change intent missing {fld} (D-0007-65)",
                               {"missing": fld}))
    directions = ci.get("compatibility_directions")
    if not directions or not isinstance(directions, list):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, iid,
                           "change intent declares no compatibility "
                           "directions — compatibility is directional "
                           "(D-0007-01/65)", {}))
    else:
        for d in directions:
            if d not in DIRECTIONS:
                out.append(Finding(INVALID_COMPAT_SCHEMA, P1, iid,
                                   f"unknown compatibility direction {d!r}",
                                   {"direction": d}))
    if not isinstance(ci.get("consumers"), list):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, iid,
                           "change intent consumers must be a list", {}))
    if "deprecation_ref" not in ci:
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, iid,
                           "change intent must carry a deprecation_ref key "
                           "(null is allowed; absence is not) (D-0007-65)",
                           {}))
    if not (ci.get("rollback_ref") or ci.get("forward_fix_ref")):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, iid,
                           "change intent declares neither rollback_ref nor "
                           "forward_fix_ref (D-0007-65)", {}))
    return out


def impact_cone(ci: dict, *, graph: dict, bindings: list[dict]) -> dict:
    """Impact cone of a declared change (D-0007-66, AC-0007-190): direct and
    transitive consumers via the producer-consumer adjacency, plus the
    cross-graph references the intent carries. ADVISORY reach analysis."""
    graph = graph or {}
    consumers_of = graph.get("consumers_of") or {}
    contract_id = ci.get("contract_id") or ci.get("surface")

    direct = list(consumers_of.get(contract_id, []))
    transitive: list = []
    seen = {contract_id, *direct}
    frontier = list(direct)
    while frontier:
        node = frontier.pop(0)
        for downstream in consumers_of.get(node, []):
            if downstream not in seen:
                seen.add(downstream)
                transitive.append(downstream)
                frontier.append(downstream)

    affected = set(direct) | set(transitive)
    critical = [b.get("consumer_id") for b in (bindings or [])
                if b.get("consumer_id") in affected
                and b.get("criticality") in ("C3", "C4")]

    cone = {"contract_id": contract_id,
            "direct_consumers": direct,
            "transitive_consumers": transitive,
            "critical_consumers": critical,
            "classification": "ADVISORY"}
    for ref in _CROSS_GRAPH_REFS:
        cone[ref] = list(ci.get(ref) or [])
    return cone

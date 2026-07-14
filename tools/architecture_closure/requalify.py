"""Incremental requalification (SP0010 FUNCTION Q, §11.14, D-0010-25/27,
AC-0010-177..179).

When a predecessor root changes: identify the changed leaves, compute the
AFFECTED assurance cone (claims transitively depending on the changed
constitution's guarantees), stale only those claims, recompute the affected
closure, and compare with a FULL recompute. The incremental result must equal
the full recompute on reference fixtures (D-0010-25) — otherwise the impact
analysis is unsound (INCREMENTAL_FULL_MISMATCH). No old seal silently remains
current after a material root change (D-0010-27).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0


def affected_cone(changed_constitution: str, interfaces: dict,
                  hyperedges: list) -> dict:
    """Claims transitively downstream of the changed constitution's guarantees.
    Reverse-reachability over the hyperedge premise->conclusion relation."""
    seeds = set(interfaces.get(changed_constitution, {}).get(
        "guarantee_refs", []))
    seeds |= {f"CL-{changed_constitution}-evidence-present"}
    # build premise -> [conclusions] adjacency
    downstream = {}
    for e in hyperedges:
        for p in e["premise_claim_refs"]:
            downstream.setdefault(p, []).append(e["conclusion_claim_ref"])
    affected = set()
    stack = list(seeds)
    while stack:
        c = stack.pop()
        for nxt in downstream.get(c, []):
            if nxt not in affected:
                affected.add(nxt)
                stack.append(nxt)
    return {"changed": changed_constitution, "seeds": sorted(seeds),
            "affected_claims": sorted(affected)}


def incremental_recompute(supported_full: set, affected: set,
                          new_supported: set) -> dict:
    """Stale the affected claims, then apply the fresh support decision only to
    them; unaffected claims keep their prior state."""
    result = (set(supported_full) - set(affected)) | (
        set(new_supported) & set(affected))
    return {"incremental_supported": sorted(result)}


def compare_full(incremental: dict, full_supported: set) -> list[Finding]:
    """The incremental cone result must equal the full recompute (D-0010-25)."""
    out: list[Finding] = []
    if set(incremental["incremental_supported"]) != set(full_supported):
        missing = sorted(set(full_supported) - set(
            incremental["incremental_supported"]))
        extra = sorted(set(incremental["incremental_supported"]) - set(
            full_supported))
        out.append(Finding(
            "INCREMENTAL_FULL_MISMATCH", P0, "requalification",
            "incremental requalification result differs from the full "
            "recompute reference oracle (D-0010-25)",
            {"missing": missing, "extra": extra}))
    return out


def requalification_report(changed_constitution: str, interfaces: dict,
                           hyperedges: list, supported_full: set,
                           new_supported: set) -> dict:
    cone = affected_cone(changed_constitution, interfaces, hyperedges)
    inc = incremental_recompute(supported_full, set(cone["affected_claims"]),
                                new_supported)
    report = {"cone": cone, "incremental": inc}
    report["requalification_hash"] = hash_obj(report)
    return report

"""Constitutional assurance hypergraph + fixed-point activation (SP0010
FUNCTION D, §10.2, §11.1/11.2, §12.2/12.3, D-0010-01, AC-0010-041..043).

A guarantee often requires a CONJUNCTION of prerequisite assumptions. That is
one hyperedge {A1,A2,A3} -> G, NOT three simple edges: a single satisfied
premise must NEVER activate a multi-premise guarantee (INV-0010-12). Positive
support is the least fixed point over active hyperedges starting from anchored
claims (guarantees whose own evidence is present and whose premise set is
empty or already supported). Everything here is deterministic; the iteration
count is bounded and reported.
"""
from __future__ import annotations

from pathlib import Path

from .canon import core_hash, hash_obj
from .model import Finding, P0, SUPPORTED_ONLY
from .interfaces import CONSTITUTIONS


def build_hypergraph(interfaces: dict) -> dict:
    """One hyperedge per guarantee: premises = the constitution's assumption
    claims (predecessor guarantees); an extra grounding premise is the
    constitution's evidence-present fact, modeled as an anchored claim."""
    edges = []
    anchored = []          # claims grounded directly by present evidence
    for sp, iface in sorted(interfaces.items()):
        ev_present = any(e["present"] for e in iface["evidence_refs"])
        ground_claim = f"CL-{sp}-evidence-present"
        if ev_present:
            anchored.append(ground_claim)
        for g in iface["guarantee_refs"]:
            premises = sorted(set(iface["assumption_refs"]) | {ground_claim})
            edges.append({
                "hyperedge_id": "HE-" + hash_obj({"c": g, "p": premises})[:16],
                "premise_claim_refs": premises,
                "conclusion_claim_ref": g,
                "conjunctive": True,
                "source_refs": [sp],
            })
    for e in edges:
        e["edge_hash"] = core_hash(e)
    return {"edges": edges, "anchored": sorted(anchored)}


def positive_support_closure(hg: dict) -> dict:
    """Least fixed point (§11.2/§12.3): S0 = anchored claims; a hyperedge fires
    only when EVERY premise is already supported (conjunctive activation,
    §11.1)."""
    supported = set(hg["anchored"])
    edges = hg["edges"]
    iterations = 0
    changed = True
    while changed:
        changed = False
        iterations += 1
        for e in edges:
            if e["conclusion_claim_ref"] in supported:
                continue
            if all(p in supported for p in e["premise_claim_refs"]):
                supported.add(e["conclusion_claim_ref"])
                changed = True
        if iterations > 1000:           # bounded backstop (never real)
            break
    return {"supported": sorted(supported), "iterations": iterations}


def activation_findings(hg: dict) -> list[Finding]:
    """A conjunctive hyperedge with an empty premise set (other than anchoring)
    or a premise that no edge/anchor can ever provide is structurally invalid.
    Also: guard against a single-premise substitution for a declared
    multi-premise guarantee."""
    out: list[Finding] = []
    providable = set(hg["anchored"]) | {e["conclusion_claim_ref"]
                                        for e in hg["edges"]}
    for e in hg["edges"]:
        if not e["premise_claim_refs"]:
            out.append(Finding(
                "ASSURANCE_HYPEREDGE_INVALID", P0, e["hyperedge_id"],
                "hyperedge has no premises", {}))
        for p in e["premise_claim_refs"]:
            if p not in providable:
                out.append(Finding(
                    "HYPEREDGE_PREMISE_MISSING", P0, e["hyperedge_id"],
                    f"premise {p!r} can never be provided by any anchor or "
                    "hyperedge conclusion (dangling premise, D-0010-06)",
                    {"premise": p}))
        # declared-conjunctive edges keep all premises; a downstream mutation
        # dropping premises is caught by comparing against the interface
        if e["conjunctive"] is not True:
            out.append(Finding(
                "ASSURANCE_HYPEREDGE_INVALID", P0, e["hyperedge_id"],
                "conjunctive premise set must remain conjunctive "
                "(INV-0010-11)", {}))
    return out


def hypergraph_root(hg: dict) -> str:
    return hash_obj([e["edge_hash"] for e in sorted(
        hg["edges"], key=lambda e: e["hyperedge_id"])])

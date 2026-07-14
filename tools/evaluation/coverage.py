"""Evaluation Coverage Hypergraph (SP0011 §2.1.E, §11.4/11.5, §10.5, D-0011-038/
039/040, AC-0011-061..070).

Coverage is a HYPERGRAPH, not a task count (D-0011-039). Each hyperedge binds a
claim to the scenarios / failure modes / contract surfaces / languages /
providers / packs / state transitions that must be exercised to close it. A
MANDATORY critical edge that is uncovered blocks closure of its claim (fail-
closed). Interaction coverage uses a pairwise covering array over the declared
configuration factors; critical interactions may require higher order.
"""
from __future__ import annotations

from itertools import combinations

from .canon import hash_obj
from .model import Finding, P1, P0

# the configuration factors interaction coverage ranges over
FACTORS = {
    "language": ["PL", "EN", "DE", "ES"],
    "provider_account": ["personal", "shared"],
    "risk_class": ["low", "protected"],
    "effect_class": ["read", "write"],
}


def build_hyperedges(claims: dict) -> list:
    """One coverage hyperedge per claim, binding it to its domain's dimensions.
    Mandatory iff the claim is critical."""
    edges = []
    for cid, claim in sorted(claims.items()):
        edges.append({
            "coverage_edge_id": "COV-" + cid,
            "claim_refs": [cid],
            "scenario_refs": [f"SCN-{claim['domain_id']}"],
            "failure_mode_refs": [f"FM-{claim['domain_id']}"],
            "contract_surface_refs": [f"CS-{claim['domain_id']}"],
            "language_refs": FACTORS["language"],
            "provider_refs": FACTORS["provider_account"],
            "state_transition_refs": [f"ST-{claim['domain_id']}"],
            "mandatory": bool(claim["critical"]),
            # covered iff the claim has repository grounding (achieved >= M1)
            "coverage_state": "COVERED" if claim["achieved_maturity"] != "M0"
            else "UNKNOWN",
        })
    return edges


def pairwise_covering_array(factors: dict = None) -> list:
    """A deterministic pairwise (strength-2) covering array over the factors: a
    greedy set of tuples covering every pair of factor-values at least once."""
    factors = factors or FACTORS
    keys = sorted(factors)
    required = set()
    for a, b in combinations(keys, 2):
        for va in factors[a]:
            for vb in factors[b]:
                required.add((a, va, b, vb))
    rows = []
    # greedy: repeatedly emit a full assignment covering the most uncovered pairs
    import itertools
    all_assignments = list(itertools.product(*[factors[k] for k in keys]))
    covered = set()
    for assignment in all_assignments:
        row = dict(zip(keys, assignment))
        gain = 0
        for a, b in combinations(keys, 2):
            pair = (a, row[a], b, row[b])
            if pair in required and pair not in covered:
                gain += 1
        if gain > 0:
            rows.append(row)
            for a, b in combinations(keys, 2):
                covered.add((a, row[a], b, row[b]))
        if covered >= required:
            break
    return rows


def coverage_findings(edges: list) -> list[Finding]:
    out: list[Finding] = []
    for e in edges:
        if e["mandatory"] and e["coverage_state"] != "COVERED":
            out.append(Finding(
                "CRITICAL_COVERAGE_INCOMPLETE", P0, e["claim_refs"][0],
                "mandatory critical coverage edge is not COVERED: claim cannot "
                "close (D-0011-038)", {"edge": e["coverage_edge_id"]}))
    return out


def coverage_summary(edges: list) -> dict:
    covered = sum(1 for e in edges if e["coverage_state"] == "COVERED")
    return {"nodes": len({c for e in edges for c in e["claim_refs"]}),
            "edges": len(edges), "covered": covered,
            "mandatory": sum(1 for e in edges if e["mandatory"]),
            "critical_gaps": sorted(e["claim_refs"][0] for e in edges
                                    if e["mandatory"]
                                    and e["coverage_state"] != "COVERED"),
            "coverage_root": hash_obj(sorted(
                (e["coverage_edge_id"], e["coverage_state"]) for e in edges))}

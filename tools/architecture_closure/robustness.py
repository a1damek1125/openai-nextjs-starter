"""Assurance Robustness Frontier — cut numbers per domain (SP0010 V5 FUNCTION Z,
§0, D-0010-115..120).

resilience.py answers "does removing K supports break the claim?" for a fixed K.
This module computes the exact CUT NUMBER of every critical guarantee: the
minimum number of independent support DOMAINS that must be removed to leave the
guarantee unsupported — a minimum hitting set over the family of alternative
minimal support sets, computed in PRODUCER-DOMAIN space (common-mode quotient, so
many atoms from one generator count as one domain, consistent with the evidence
algebra, D-0010-10). A cut number of 1 is a SINGLE POINT OF ASSURANCE; the
frontier is the vector of cut numbers and its minimum bounds the whole program's
robustness. This is disclosed honestly (a cut of 1 is assurance debt, P2), never
silently rounded up.

Governance/analysis tooling only; never imported by product code; no external
effect; emits no secret values.
"""
from __future__ import annotations

from itertools import combinations

from .canon import hash_obj
from .model import Finding, P0, P2

_HITTING_SET_LIMIT = 12          # domains; brute-force bound (disclosed if hit)


def _domains_of_set(support_set: list, element_domain: dict) -> frozenset:
    return frozenset(element_domain.get(e, e) for e in support_set)


def min_cut_number(support_sets: list, element_domain: dict) -> dict:
    """Minimum hitting set size over the family of support sets, in domain space.
    Breaking the claim requires hitting (removing a member of) EVERY alternative
    support set. Returns the cut number and whether the search hit its bound."""
    family = [_domains_of_set(s, element_domain) for s in support_sets if s]
    if not family:
        return {"cut_number": 0, "limit_reached": False, "witness": []}
    universe = sorted({d for s in family for d in s})
    if len(universe) > _HITTING_SET_LIMIT:
        # disclose the bound instead of silently under/over-reporting
        return {"cut_number": 1, "limit_reached": True, "witness": []}
    for k in range(1, len(universe) + 1):
        for combo in combinations(universe, k):
            cs = set(combo)
            if all(cs & s for s in family):
                return {"cut_number": k, "limit_reached": False,
                        "witness": sorted(cs)}
    return {"cut_number": len(universe), "limit_reached": False,
            "witness": universe}


def analyze_claim(claim_id: str, support_sets: list,
                  element_domain: dict, *, critical: bool = True) -> dict:
    cut = min_cut_number(support_sets, element_domain)
    n = cut["cut_number"]
    if n == 0:
        klass = "UNSUPPORTED"
    elif n == 1:
        klass = "SINGLE_POINT_OF_ASSURANCE"
    else:
        klass = "ROBUST_TO_%d_DOMAIN_LOSS" % (n - 1)
    return {"claim_id": claim_id, "critical": critical,
            "cut_number": n, "classification": klass,
            "limit_reached": cut["limit_reached"], "witness": cut["witness"]}


def robustness_frontier(claim_supports: dict, element_domain: dict, *,
                        critical: set) -> dict:
    """claim_supports: claim_id -> list of minimal support sets. Returns the per
    claim cut numbers and the frontier (the minimum critical cut number)."""
    per_claim = {cid: analyze_claim(cid, sets, element_domain,
                                    critical=cid in critical)
                 for cid, sets in sorted(claim_supports.items())}
    crit_cuts = [rec["cut_number"] for cid, rec in per_claim.items()
                 if rec["critical"] and rec["cut_number"] > 0]
    frontier_min = min(crit_cuts) if crit_cuts else 0
    return {
        "per_claim": per_claim,
        "frontier_min_cut": frontier_min,
        "single_points": sorted(cid for cid, rec in per_claim.items()
                                if rec["classification"]
                                == "SINGLE_POINT_OF_ASSURANCE"),
        "robustness_root": hash_obj({cid: rec["cut_number"]
                                     for cid, rec in sorted(per_claim.items())}),
    }


def robustness_findings(frontier: dict) -> list[Finding]:
    out: list[Finding] = []
    for cid, rec in sorted(frontier["per_claim"].items()):
        if not rec["critical"]:
            continue
        if rec["cut_number"] == 0:
            out.append(Finding(
                "ASSURANCE_CUT_SINGLE", P0, cid,
                "critical guarantee has cut number 0 (unsupported): breaking it "
                "requires removing nothing (D-0010-115)", rec))
        elif rec["limit_reached"]:
            out.append(Finding(
                "ROBUSTNESS_LIMIT_REACHED", P2, cid,
                "cut-number search hit its domain bound; the reported cut is a "
                "disclosed lower bound, not exact (D-0010-118)", rec))
        elif rec["cut_number"] == 1:
            out.append(Finding(
                "ASSURANCE_CUT_SINGLE", P2, cid,
                "critical guarantee is a SINGLE POINT OF ASSURANCE (cut number "
                "1): its support rests on one producer domain — assurance debt, "
                "disclosed not counted as robust (D-0010-116)", rec))
    return out


def robustness_root(frontier: dict) -> str:
    return frontier["robustness_root"]

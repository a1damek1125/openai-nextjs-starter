"""Risk Correlation Graph — advisory only, NEVER a dependency (SP0003 D-0003-14,
INV-0003-06/§17).

Two nodes may share an immature-technology assumption, a provider risk, an
unverified research assumption or a regulatory interpretation. That correlation
is modeled as RISK_CORRELATION and is advisory: it must never be converted into a
false hard dependency.
"""
from __future__ import annotations

from itertools import combinations

from .model import Finding, P1, INVALID_PROGRAM_SCHEMA


def validate_risk(program: dict) -> list[Finding]:
    out: list[Finding] = []
    nodes = {n["node_id"] for n in program.get("nodes", [])}
    for c in program.get("risk_correlations", []):
        for nid in c.get("nodes", []):
            if nid not in nodes:
                out.append(Finding(INVALID_PROGRAM_SCHEMA, P1,
                                   c.get("risk_id", "-"),
                                   f"risk correlation references unknown node "
                                   f"{nid!r}", {}))
    return out


def correlated_pairs(program: dict) -> list[tuple[str, str, str]]:
    """(node_a, node_b, risk_id) for every co-membership in a risk cluster."""
    out: set[tuple[str, str, str]] = set()
    for c in program.get("risk_correlations", []):
        rid = c.get("risk_id", "-")
        for a, b in combinations(sorted(c.get("nodes", [])), 2):
            out.add((a, b, rid))
    return sorted(out)


def shared_risk(program: dict, node_id: str) -> dict[str, list[str]]:
    """risk_id -> co-members that share a risk with node_id."""
    out: dict[str, list[str]] = {}
    for c in program.get("risk_correlations", []):
        members = c.get("nodes", [])
        if node_id in members:
            out[c.get("risk_id", "-")] = sorted(m for m in members
                                                if m != node_id)
    return out

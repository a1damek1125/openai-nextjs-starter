"""Resource / Conflict Graph — SEPARATE from dependency precedence
(SP0003 D-0003-13, §11.17, INV-0003-05/06).

Two nodes sharing an exclusive resource (a migration lane, an authority-core
write lane, a single human reviewer, an exclusive test environment) must NOT run
in the same parallel batch — but NO dependency edge is created to serialize them
(INV-0003-06). Absence of a hard dependency does NOT prove safe parallelism
(INV-0003-05): resource conflicts are applied during scheduling, not readiness.
"""
from __future__ import annotations

from itertools import combinations

from .model import Finding, P1, RESOURCE_CONFLICT, INVALID_PROGRAM_SCHEMA


def resource_map(program: dict) -> dict[str, set[str]]:
    """resource_key -> set of node_ids that use it (from node.resource_keys and
    explicit conflict entries)."""
    m: dict[str, set[str]] = {}
    for n in program.get("nodes", []):
        for r in n.get("resource_keys", []):
            m.setdefault(r, set()).add(n["node_id"])
    for c in program.get("conflicts", []):
        r = c.get("resource_key")
        if r:
            for nid in c.get("nodes", []):
                m.setdefault(r, set()).add(nid)
    return m


def resource_capacity(program: dict) -> dict[str, int]:
    caps: dict[str, int] = {}
    for c in program.get("conflicts", []):
        r = c.get("resource_key")
        if r is not None:
            caps[r] = int(c.get("capacity", 1))
    return caps


def conflicting_pairs(program: dict) -> list[tuple[str, str]]:
    """Node pairs that share an exclusive (capacity-1) resource."""
    caps = resource_capacity(program)
    out: set[tuple[str, str]] = set()
    for r, nodes in resource_map(program).items():
        if caps.get(r, 1) <= 1:
            for a, b in combinations(sorted(nodes), 2):
                out.add((a, b))
    return sorted(out)


def conflicts_with(program: dict, node_id: str) -> set[str]:
    out: set[str] = set()
    for a, b in conflicting_pairs(program):
        if a == node_id:
            out.add(b)
        elif b == node_id:
            out.add(a)
    return out


def validate_conflicts(program: dict) -> list[Finding]:
    out: list[Finding] = []
    nodes = {n["node_id"] for n in program.get("nodes", [])}
    for c in program.get("conflicts", []):
        for nid in c.get("nodes", []):
            if nid not in nodes:
                out.append(Finding(INVALID_PROGRAM_SCHEMA, P1,
                                   c.get("resource_key", "-"),
                                   f"conflict references unknown node {nid!r}",
                                   {}))
    return out


def resource_batch_ok(program: dict, batch: set[str]) -> tuple[bool, list[Finding]]:
    """Does a proposed parallel batch respect exclusive resources + capacities?"""
    caps = resource_capacity(program)
    findings: list[Finding] = []
    ok = True
    for r, users in resource_map(program).items():
        used = [n for n in batch if n in users]
        cap = caps.get(r, 1)
        if len(used) > cap:
            ok = False
            findings.append(Finding(RESOURCE_CONFLICT, P1, r,
                                    f"{len(used)} nodes need resource {r!r} "
                                    f"(capacity {cap}): {sorted(used)}",
                                    {"nodes": sorted(used), "capacity": cap}))
    return ok, findings

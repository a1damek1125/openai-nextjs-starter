"""Migration Graph + Path Selection (SP0007 §11.5, §12.7, D-0007-35/36,
AC-0007-126..145).

Migrations are edges in a directed version graph (D-0007-35); a missing path is
MIGRATION_PATH_MISSING, never an implicit ad-hoc conversion (AC-0007-126). Path
selection is LEXICOGRAPHIC over non-compensatory criteria (§11.5, D-0007-36):
prohibited edges, then irreversibility, then critical loss, then operational
risk, downtime, cost — never collapsed into one scalar. Migration progress must
conserve records: Processed + Pending + Failed == Total with disjoint sets
(§12.7). A REVERSIBLE claim without an inverse transformer is an unproven claim
(D-0007-37/41); a ONE_WAY edge must declare its last safe rollback point
(D-0007-41/51). Enumeration is bounded and truncation is reported honestly
(ANALYSIS_LIMIT_REACHED), never silently ignored.
"""
from __future__ import annotations

from .model import (Finding, P0, P1, P2, REVERSIBILITY,
                    CRITICAL_LOSS_DIMENSIONS, MIGRATION_PATH_MISSING,
                    ROLLBACK_NOT_AVAILABLE, INVALID_COMPAT_SCHEMA,
                    ANALYSIS_LIMIT_REACHED)

MAX_PATHS = 64
MAX_DEPTH = 16

_EDGE_REQUIRED = ("migration_edge_id", "contract_id", "from_version",
                  "to_version", "transformer_ref")

_DOWNTIME_RANKS = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "TOTAL": 4,
                   "UNKNOWN": 4}


def validate_edge(edge: dict) -> list[Finding]:
    """A migration edge is a first-class artifact (D-0007-35): identity,
    endpoints, transformer, pre/postconditions, loss vector, reversibility."""
    out: list[Finding] = []
    eid = edge.get("migration_edge_id", "-")
    for f in _EDGE_REQUIRED:
        if not edge.get(f):
            out.append(Finding(INVALID_COMPAT_SCHEMA, P1, eid,
                               f"migration edge missing {f} (D-0007-35)", {}))
    if not isinstance(edge.get("preconditions"), list):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, eid,
                           "migration edge preconditions must be a list", {}))
    if not isinstance(edge.get("postconditions"), list):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, eid,
                           "migration edge postconditions must be a list", {}))
    if not isinstance(edge.get("loss_vector"), dict):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, eid,
                           "migration edge missing loss_vector dict "
                           "(D-0007-38)", {}))
    rev = edge.get("reversibility")
    if rev not in REVERSIBILITY:
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, eid,
                           f"unknown reversibility {rev!r}", {}))
    # a REVERSIBLE claim without an inverse transformer is a claim without
    # proof material — up migration does not prove rollback (D-0007-37,
    # INV-0007-31)
    if rev == "REVERSIBLE" and edge.get("inverse_transformer_ref") is None:
        out.append(Finding(ROLLBACK_NOT_AVAILABLE, P0, eid,
                           "edge claims REVERSIBLE but has no "
                           "inverse_transformer_ref (D-0007-37)", {}))
    # defense-in-depth: a REVERSIBLE edge whose inverse is present but not
    # VERIFIED is still not a proven rollback (SWARM-M E10; D-0007-37)
    elif rev == "REVERSIBLE" and edge.get("inverse_verified") is not True:
        out.append(Finding(ROLLBACK_NOT_AVAILABLE, P0, eid,
                           "edge claims REVERSIBLE but its inverse transformer "
                           "is not verified (inverse_verified is not True) "
                           "(D-0007-37)", {}))
    # a ONE_WAY edge must declare where safety ends (D-0007-41/51)
    if rev == "ONE_WAY" and not edge.get("last_safe_rollback_point"):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P1, eid,
                           "ONE_WAY edge declares no last_safe_rollback_point "
                           "(D-0007-41/51)", {}))
    return out


def _relevant(edges: list[dict], contract_id: str | None) -> list[dict]:
    if contract_id is None:
        return list(edges)
    return [e for e in edges if e.get("contract_id") == contract_id]


def find_path(edges: list[dict], from_v: str, to_v: str, *,
              contract_id: str | None = None) -> dict:
    """BFS over the directed version graph (D-0007-36). Returns the shortest
    path by hop count, or {"found": False} when no path exists."""
    pool = _relevant(edges, contract_id)
    if from_v == to_v:
        return {"found": True, "path": [from_v], "edge_ids": []}
    adj: dict[str, list[dict]] = {}
    for e in pool:
        adj.setdefault(e.get("from_version"), []).append(e)
    queue: list[tuple[str, list[str], list[str]]] = [(from_v, [from_v], [])]
    seen = {from_v}
    while queue:
        node, path, eids = queue.pop(0)
        for e in sorted(adj.get(node, []),
                        key=lambda x: str(x.get("migration_edge_id"))):
            nxt = e.get("to_version")
            if nxt in seen:
                continue
            npath = path + [nxt]
            neids = eids + [e.get("migration_edge_id")]
            if nxt == to_v:
                return {"found": True, "path": npath, "edge_ids": neids}
            seen.add(nxt)
            queue.append((nxt, npath, neids))
    return {"found": False}


def path_findings(edges: list[dict], from_v: str, to_v: str, *,
                  contract_id: str | None = None) -> list[Finding]:
    """No declared migration path between deployed versions is
    MIGRATION_PATH_MISSING (P1) — data cannot be moved by wishing
    (AC-0007-126)."""
    if find_path(edges, from_v, to_v, contract_id=contract_id)["found"]:
        return []
    subject = f"{contract_id or '-'}:{from_v}->{to_v}"
    return [Finding(MIGRATION_PATH_MISSING, P1, subject,
                    f"no migration path from {from_v!r} to {to_v!r} "
                    "(AC-0007-126)", {})]


def _edge_has_critical_loss(edge: dict) -> bool:
    lv = edge.get("loss_vector") or {}
    # fail-closed: an undeclared critical dimension is UNKNOWN, not NONE
    return any(lv.get(d, "UNKNOWN") != "NONE" for d in CRITICAL_LOSS_DIMENSIONS)


def _downtime_rank(edge: dict) -> float:
    v = edge.get("downtime", 0)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    return _DOWNTIME_RANKS.get(v, 4)


def _criteria(path_edges: list[dict], prohibited: frozenset) -> tuple:
    """The lexicographic criterion tuple of §11.5 — evaluated in strict order,
    never collapsed into a compensatory scalar (D-0007-36)."""
    return (
        sum(1 for e in path_edges
            if e.get("migration_edge_id") in prohibited),
        sum(1 for e in path_edges
            if e.get("reversibility") != "REVERSIBLE"),
        sum(1 for e in path_edges if _edge_has_critical_loss(e)),
        sum(e.get("operational_risk", 0) for e in path_edges),
        sum(_downtime_rank(e) for e in path_edges),
        sum(e.get("cost", 0) for e in path_edges),
    )


def select_path(edges: list[dict], from_v: str, to_v: str, *,
                prohibited: frozenset = frozenset()) -> dict:
    """Enumerate simple paths (bounded: MAX_PATHS/MAX_DEPTH, truncation
    reported via ANALYSIS_LIMIT_REACHED) and choose LEXICOGRAPHICALLY (§11.5):
    fewest prohibited edges, then fewest ONE_WAY/irreversible edges, then
    fewest critical-loss edges, then minimum operational risk, downtime rank,
    cost. Criteria are never averaged (D-0007-36)."""
    adj: dict[str, list[dict]] = {}
    for e in edges:
        adj.setdefault(e.get("from_version"), []).append(e)
    for k in adj:
        adj[k].sort(key=lambda x: str(x.get("migration_edge_id")))

    paths: list[list[dict]] = []
    truncated = False

    def dfs(node: str, visited: set, acc: list[dict]) -> None:
        nonlocal truncated
        if len(paths) >= MAX_PATHS:
            truncated = True
            return
        if node == to_v and acc:
            paths.append(list(acc))
            return
        if len(acc) >= MAX_DEPTH:
            truncated = True
            return
        for e in adj.get(node, []):
            nxt = e.get("to_version")
            if nxt in visited:
                continue
            visited.add(nxt)
            acc.append(e)
            dfs(nxt, visited, acc)
            acc.pop()
            visited.discard(nxt)

    dfs(from_v, {from_v}, [])

    findings: list[Finding] = []
    if truncated:
        findings.append(Finding(ANALYSIS_LIMIT_REACHED, P2,
                                f"{from_v}->{to_v}",
                                "path enumeration truncated at bound "
                                f"(max {MAX_PATHS} paths, depth {MAX_DEPTH}); "
                                "selection is over the enumerated subset only",
                                {"max_paths": MAX_PATHS,
                                 "max_depth": MAX_DEPTH}))
    if not paths:
        return {"found": False, "candidates": 0, "truncated": truncated,
                "findings": findings}

    scored = [( _criteria(p, prohibited), p) for p in paths]
    scored.sort(key=lambda sp: (sp[0],
                                [str(e.get("migration_edge_id"))
                                 for e in sp[1]]))
    best_criteria, best = scored[0]
    versions = [from_v] + [e.get("to_version") for e in best]
    return {
        "found": True,
        "path": versions,
        "edge_ids": [e.get("migration_edge_id") for e in best],
        "criteria": {
            "prohibited_edges": best_criteria[0],
            "irreversible_edges": best_criteria[1],
            "critical_loss_edges": best_criteria[2],
            "operational_risk": best_criteria[3],
            "downtime_rank": best_criteria[4],
            "cost": best_criteria[5],
        },
        "criteria_tuple": best_criteria,
        "candidates": len(paths),
        "truncated": truncated,
        "findings": findings,
    }


def progress_conservation(progress: dict) -> list[Finding]:
    """Processed + Pending + Failed == Total with disjoint sets (§12.7) — a
    record can never silently vanish or be double-counted during migration."""
    out: list[Finding] = []
    subject = progress.get("plan_id", "-")
    processed = list(progress.get("processed", []))
    pending = list(progress.get("pending", []))
    failed = list(progress.get("failed", []))
    total = progress.get("total")
    p_set, n_set, f_set = set(processed), set(pending), set(failed)
    disjoint = (p_set.isdisjoint(n_set) and p_set.isdisjoint(f_set)
                and n_set.isdisjoint(f_set))
    conserved = True
    if isinstance(total, (int, float)) and not isinstance(total, bool):
        conserved = (len(processed) + len(pending) + len(failed)) == total
    elif total is not None:
        conserved = (p_set | n_set | f_set) == set(total) and \
            (len(processed) + len(pending) + len(failed)) == len(list(total))
    else:
        conserved = False
    if not (disjoint and conserved):
        out.append(Finding(INVALID_COMPAT_SCHEMA, P0, subject,
                           "migration progress conservation violated",
                           {"processed": len(processed),
                            "pending": len(pending), "failed": len(failed),
                            "disjoint": disjoint}))
    return out


def no_transitive_edge(edges: list[dict], from_v: str, to_v: str) -> bool:
    """True iff a DIRECT edge from_v -> to_v exists. A composite path is never
    a verified single edge — transitivity is not assumed (INV-0007-06)."""
    return any(e.get("from_version") == from_v and e.get("to_version") == to_v
               for e in edges)

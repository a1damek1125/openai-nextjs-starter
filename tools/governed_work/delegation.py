"""Delegation Graph + Authority Verifier + Non-Amplification (SP0006 §9.6, §11.4,
D-0006-13/14/15, INV-0006-07..14).

The authority-bearing delegation graph MUST be a directed acyclic graph
(D-0006-13): authority flows strictly from parent to child and can never loop
back to amplify itself. Edges flagged ``coordination_only`` carry no authority
and are excluded from the acyclicity check. Bounded delegation shape is enforced
by a capability ceiling: maximum delegation depth, direct fan-out and total
descendant count. Every child capability lease must be a structural ATTENUATION
of its parent lease (delegated authority is a subset, never a superset); any
expansion is DELEGATION_AUTHORITY_AMPLIFICATION (P0). Every delegation edge binds
existing execution identities that share the parent's work order (INV-0006-14).

Governance tooling only; product runtime must never import it (INV-0006-46).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, INVALID_WORK_SCHEMA,
                    DELEGATION_CYCLE_DETECTED, DELEGATION_DEPTH_EXCEEDED,
                    DELEGATION_FANOUT_EXCEEDED,
                    DELEGATION_AUTHORITY_AMPLIFICATION)
from .canon import core_hash
from .lease import is_attenuation, validate_child_lease
from .identity import validate_identity

# capability-ceiling defaults for delegation shape (D-0006-14)
DEFAULT_MAX_DEPTH = 8
DEFAULT_MAX_FANOUT = 16
DEFAULT_MAX_DESCENDANTS = 256


def _is_authority_edge(edge: dict) -> bool:
    """An edge propagates authority unless it is explicitly coordination-only.
    Fail-closed: only the boolean True marks an edge non-authority — a truthy
    string such as "false" must NOT drop the edge from the DAG check
    (SWARM-M E1; D-0006-13)."""
    return edge.get("coordination_only") is not True


def _authority_pairs(edges: list[dict]) -> list[tuple[str, str]]:
    """(parent_identity, child_identity) pairs for authority-bearing edges only."""
    pairs: list[tuple[str, str]] = []
    for e in edges:
        if not _is_authority_edge(e):
            continue
        p, c = e.get("parent_identity"), e.get("child_identity")
        if p is not None and c is not None:
            pairs.append((str(p), str(c)))
    return pairs


def build_graph(edges: list[dict]) -> dict:
    """Adjacency map (parent_identity -> sorted unique child_identities) over the
    AUTHORITY-bearing delegation edges. Coordination-only edges are excluded
    because they cannot propagate authority (D-0006-13)."""
    adj: dict[str, list[str]] = {}
    for p, c in _authority_pairs(edges):
        adj.setdefault(p, [])
        adj.setdefault(c, [])
        if c not in adj[p]:
            adj[p].append(c)
    for p in adj:
        adj[p].sort()
    return adj


def _reverse_graph(edges: list[dict]) -> dict:
    """child_identity -> sorted unique parent_identities (authority edges)."""
    rev: dict[str, list[str]] = {}
    for p, c in _authority_pairs(edges):
        rev.setdefault(p, [])
        rev.setdefault(c, [])
        if p not in rev[c]:
            rev[c].append(p)
    for c in rev:
        rev[c].sort()
    return rev


def find_cycle(edges: list[dict]) -> list[str] | None:
    """Return one authority cycle as an ordered identity list (closing on its
    first node), or None when the authority graph is acyclic. Deterministic:
    nodes and neighbours are visited in sorted order."""
    adj = build_graph(edges)
    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in adj}
    parent: dict[str, str | None] = {n: None for n in adj}

    def _walk(start: str) -> list[str] | None:
        stack = [(start, iter(adj.get(start, [])))]
        color[start] = GREY
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                if color[nxt] == GREY:
                    # back-edge: reconstruct the cycle path
                    cycle = [nxt, node]
                    cur = parent.get(node)
                    while cur is not None and cur != nxt:
                        cycle.append(cur)
                        cur = parent.get(cur)
                    cycle.append(nxt)
                    cycle.reverse()
                    return cycle
                if color[nxt] == WHITE:
                    color[nxt] = GREY
                    parent[nxt] = node
                    stack.append((nxt, iter(adj.get(nxt, []))))
                    advanced = True
                    break
            if not advanced:
                color[node] = BLACK
                stack.pop()
        return None

    for n in sorted(adj):
        if color[n] == WHITE:
            found = _walk(n)
            if found is not None:
                return found
    return None


def has_cycle(edges: list[dict]) -> bool:
    """True iff the authority-bearing delegation graph contains a cycle."""
    return find_cycle(edges) is not None


def depth_of(edges: list[dict], identity: str) -> int:
    """Delegation depth of ``identity`` = length (in authority edges) of the
    longest chain from a root to it. A root (no authority parent) has depth 0.
    Cycle-safe: a node on a cycle is bounded rather than recursed infinitely."""
    identity = str(identity)
    rev = _reverse_graph(edges)
    if identity not in rev:
        return 0
    memo: dict[str, int] = {}

    def _d(node: str, on_path: frozenset[str]) -> int:
        if node in memo:
            return memo[node]
        parents = [p for p in rev.get(node, []) if p not in on_path]
        if not parents:
            return 0  # root (do not memoize while a cycle prunes parents)
        best = 1 + max(_d(p, on_path | {node}) for p in parents)
        memo[node] = best
        return best

    return _d(identity, frozenset())


def fanout_of(edges: list[dict], identity: str) -> int:
    """Number of DIRECT authority-bearing children of ``identity``."""
    return len(build_graph(edges).get(str(identity), []))


def descendant_count(edges: list[dict], identity: str) -> int:
    """Total distinct authority descendants reachable from ``identity`` (the node
    itself excluded). Cycle-safe via a visited set."""
    adj = build_graph(edges)
    identity = str(identity)
    seen: set[str] = set()
    stack = list(adj.get(identity, []))
    while stack:
        n = stack.pop()
        if n in seen or n == identity:
            continue
        seen.add(n)
        stack.extend(adj.get(n, []))
    return len(seen)


def non_amplification_holds(parent_lease: dict, child_lease: dict) -> bool:
    """True iff the child lease is a structural attenuation of its parent lease
    (INV-0006-08). Delegated authority may narrow but never expand rights."""
    ok, _reasons = is_attenuation(parent_lease, child_lease)
    return ok


def _resolve_parent_lease(child: dict, parent_refs: list, leases_by_id: dict):
    """Resolve a child lease's parent: prefer its recorded parent_lease_id, else
    fall back to a single unambiguous parent_lease_ref on the edge."""
    pid = child.get("parent_lease_id")
    if pid and pid in leases_by_id:
        return leases_by_id[pid]
    refs = [r for r in (parent_refs or []) if r in leases_by_id]
    if pid is None and len(refs) == 1:
        return leases_by_id[refs[0]]
    return None


def validate_delegation(work_order: dict, edges: list[dict],
                        identities: list[dict], leases_by_id: dict) \
        -> list[Finding]:
    """Verify the delegation graph for a work order (D-0006-13/14/15). Emits:

    * DELEGATION_CYCLE_DETECTED (P0) if the authority graph is not a DAG;
    * DELEGATION_DEPTH_EXCEEDED (P1) for any child deeper than the ceiling;
    * DELEGATION_FANOUT_EXCEEDED (P1) for excess direct fan-out or descendants;
    * DELEGATION_AUTHORITY_AMPLIFICATION + LEASE_ATTENUATION_FAILURE (P0) when a
      child lease is not an attenuation of its parent lease;
    * INVALID_WORK_SCHEMA (P1) for unknown identities, work-order mismatch, or
      unresolvable lease references.
    """
    out: list[Finding] = []
    wid = work_order.get("work_order_id", "-")
    ceiling = work_order.get("capability_ceiling", {}) or {}
    max_depth = ceiling.get("max_delegation_depth", DEFAULT_MAX_DEPTH)
    max_fanout = ceiling.get("max_direct_fanout", DEFAULT_MAX_FANOUT)
    max_desc = ceiling.get("max_descendant_count", DEFAULT_MAX_DESCENDANTS)

    # --- 1. authority graph must be a DAG (D-0006-13) -----------------------
    cycle = find_cycle(edges)
    if cycle is not None:
        out.append(Finding(DELEGATION_CYCLE_DETECTED, P0, wid,
                           "authority-bearing delegation graph contains a cycle "
                           f"(INV-0006-11): {' -> '.join(cycle)}",
                           {"cycle": cycle,
                            "graph_hash": core_hash(build_graph(edges))}))

    adj = build_graph(edges)
    nodes = sorted(adj)

    # --- 2. bounded delegation shape (D-0006-14) ----------------------------
    for node in nodes:
        d = depth_of(edges, node)
        if d > max_depth:
            out.append(Finding(DELEGATION_DEPTH_EXCEEDED, P1, node,
                               f"delegation depth {d} exceeds ceiling "
                               f"{max_depth} (AC-0006-052)",
                               {"depth": d, "max": max_depth}))
        fo = fanout_of(edges, node)
        if fo > max_fanout:
            out.append(Finding(DELEGATION_FANOUT_EXCEEDED, P1, node,
                               f"direct fan-out {fo} exceeds ceiling "
                               f"{max_fanout} (AC-0006-099)",
                               {"fanout": fo, "max": max_fanout}))
        dc = descendant_count(edges, node)
        if dc > max_desc:
            out.append(Finding(DELEGATION_FANOUT_EXCEEDED, P1, node,
                               f"descendant count {dc} exceeds ceiling "
                               f"{max_desc} (D-0006-14)",
                               {"descendant_count": dc, "max": max_desc}))

    # --- 3. identities exist and share the work order (INV-0006-14) ---------
    by_id = {i.get("execution_identity_id"): i for i in identities}
    for e in edges:
        p = e.get("parent_identity")
        c = e.get("child_identity")
        for role, ident in (("parent", p), ("child", c)):
            if ident is not None and ident not in by_id:
                out.append(Finding(INVALID_WORK_SCHEMA, P1, str(ident),
                                   f"delegation {role} identity is not "
                                   "registered", {"edge": e.get("work_order_id")}))
        if p in by_id and c in by_id:
            pw = by_id[p].get("work_order_id")
            cw = by_id[c].get("work_order_id")
            if pw != cw:
                out.append(Finding(INVALID_WORK_SCHEMA, P1, str(c),
                                   "child work_order differs from parent's "
                                   "(INV-0006-14)",
                                   {"parent_work_order": pw,
                                    "child_work_order": cw}))
    for idn in identities:
        out.extend(validate_identity(idn))

    # --- 4. per-edge non-amplification via lease attenuation (D-0006-15) -----
    for e in edges:
        if not _is_authority_edge(e):
            continue  # coordination-only edges convey no leased authority
        parent_refs = e.get("parent_lease_refs") or []
        child_refs = e.get("child_lease_refs") or []
        subj = e.get("child_identity", "-")
        for cref in child_refs:
            child = leases_by_id.get(cref)
            if child is None:
                out.append(Finding(INVALID_WORK_SCHEMA, P1, str(cref),
                                   "child lease reference does not resolve", {}))
                continue
            parent = _resolve_parent_lease(child, parent_refs, leases_by_id)
            if parent is None:
                out.append(Finding(INVALID_WORK_SCHEMA, P1, str(cref),
                                   "parent lease for child could not be "
                                   "resolved (fail-closed)",
                                   {"child_identity": subj}))
                continue
            out.extend(validate_child_lease(parent, child))
    return out

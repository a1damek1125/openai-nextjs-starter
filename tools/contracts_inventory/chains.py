"""Contract chains, external-effect reachability, dominators and minimal cut
sets (SP0008 §chains, D-0008-26/27/28; reuses SP0003 graph algorithms).

A contract surface rarely stands alone: an HTTP route reads/writes tables, emits
events, and can reach an external effect. This module derives a REAL dependency
graph from source — a route handler's body is scanned for the table names and
event literals it references — and answers three governance questions
deterministically:

  * effect reachability: can this surface reach an external/irreversible effect,
    and by which path (EXACT when fully resolved, UNKNOWN when a hop cannot be
    established — fail-closed, never assumed unreachable);
  * dominators: which surface, if removed, cuts ALL paths from a route to an
    effect (a single point of control);
  * minimal cut sets: the smallest sets of surfaces whose removal severs every
    route→effect path, reported EXACT / BOUNDED / LIMIT_REACHED so a truncated
    search is never mistaken for a complete one.
"""
from __future__ import annotations

import ast
from itertools import combinations
from pathlib import Path
from typing import Iterable

from .model import (Finding, P1, P2, EFFECT_BEARING_KINDS,
                    EFFECT_REACHABILITY_UNKNOWN, CHAIN_BROKEN,
                    CUT_SET_LIMIT_REACHED)

CUT_SET_LIMIT = 200          # bound on cut-set enumeration
MAX_CUT_SIZE = 3             # search minimal cuts up to this size


# ---------------------------------------------------------------------------
# edge derivation — a route handler that references a table/event name in its
# body has a real dependency edge to that surface (source-grounded).
# ---------------------------------------------------------------------------
def derive_edges(root: Path, surfaces) -> dict:
    """Return {surface_id: set(surface_id)} edges derived from handler bodies.

    For each HTTP route, resolve its handler in app.py and collect the table
    names (db.insert/update("t"...), FROM/INTO t) and event literals it mentions;
    each becomes an outgoing edge to that surface. Deterministic.
    """
    by_kind_name = {}
    for s in surfaces:
        by_kind_name[(s.surface_kind, s.canonical_name)] = s.surface_id
    table_ids = {name: sid for (k, name), sid in by_kind_name.items()
                 if k == "DB_TABLE"}
    event_ids = {name: sid for (k, name), sid in by_kind_name.items()
                 if k in ("AUDIT_EVENT",)}
    ledger_ids = {name: sid for (k, name), sid in by_kind_name.items()
                  if k == "RUN_LEDGER_EVENT"}

    edges: dict[str, set] = {s.surface_id: set() for s in surfaces}
    unresolved: set = set()          # routes with an effectful ref we could
    #                                  not resolve to a surface (red-team P1)
    handler_line = {}
    for s in surfaces:
        if s.surface_kind == "HTTP_ROUTE":
            handler_line[s.evidence[0][1]] = s.surface_id

    app_path = root / "finalis" / "portal" / "app.py"
    if not app_path.exists():
        return edges, unresolved
    tree = ast.parse(app_path.read_text(encoding="utf-8", errors="replace"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        dec_lines = {d.lineno for d in node.decorator_list}
        route_ids = [handler_line[ln] for ln in dec_lines if ln in handler_line]
        if not route_ids:
            continue
        refs_tables, refs_events = set(), set()
        has_unresolved = False
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                attr = sub.func.attr
                # write to a table
                if attr in ("insert", "update") and sub.args:
                    a0 = sub.args[0]
                    if isinstance(a0, ast.Constant) and isinstance(a0.value,
                                                                   str):
                        if a0.value in table_ids:
                            refs_tables.add(table_ids[a0.value])
                    else:
                        has_unresolved = True   # dynamic table name
                # a potential external/network/subprocess call
                if attr in ("post", "get", "put", "delete", "patch", "request",
                            "send", "sendall", "urlopen", "run", "call",
                            "check_output", "connect"):
                    has_unresolved = True
                # event emission with a dynamic (non-literal) event_type
                for kw in sub.keywords:
                    if kw.arg == "event_type" and not (
                            isinstance(kw.value, ast.Constant)
                            and isinstance(kw.value.value, str)):
                        has_unresolved = True
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                v = sub.value
                if v in event_ids:
                    refs_events.add(event_ids[v])
                elif v in ledger_ids:
                    refs_events.add(ledger_ids[v])
        for rid in route_ids:
            edges[rid] |= refs_tables | refs_events
            if has_unresolved:
                unresolved.add(rid)
    return edges, unresolved


def effect_sinks(surfaces) -> set:
    """Surfaces that ARE an external/irreversible effect (the reachability
    targets). DB writes, events, migrations, providers, jobs."""
    return {s.surface_id for s in surfaces
            if s.surface_kind in EFFECT_BEARING_KINDS}


# ---------------------------------------------------------------------------
# reachability
# ---------------------------------------------------------------------------
def reachable(edges: dict, start: str) -> set:
    seen, stack = set(), [start]
    while stack:
        n = stack.pop()
        for m in sorted(edges.get(n, ())):
            if m not in seen:
                seen.add(m)
                stack.append(m)
    return seen


def effect_reachability(edges: dict, surfaces, *, unresolved=None) -> dict:
    """For each surface, which effect sinks it can reach and an exactness tag.

    `unresolved` (from derive_edges) is the set of surfaces whose handler had an
    effectful reference we could NOT resolve to a surface. Exactness is EXACT
    only when the surface is a sink, OR it has resolved edges AND nothing about
    it was left unresolved — one resolved edge never masks an unresolved hop
    (red-team P1)."""
    unresolved = unresolved or set()
    sinks = effect_sinks(surfaces)
    out = {}
    for s in surfaces:
        r = reachable(edges, s.surface_id)
        hit = sorted(r & sinks)
        self_sink = s.surface_id in sinks
        has_edges = bool(edges.get(s.surface_id))
        if self_sink:
            exactness = "EXACT"
        elif s.surface_id in unresolved:
            exactness = "UNKNOWN"        # an unresolved effect hop remains
        elif has_edges:
            exactness = "EXACT"
        else:
            exactness = "UNKNOWN"        # no derived edges => cannot prove none
        out[s.surface_id] = {
            "reaches_effect": bool(hit) or self_sink,
            "effect_sinks": hit,
            "self_sink": self_sink,
            "exactness": exactness,
        }
    return out


def reachability_findings(reach: dict, surfaces) -> list[Finding]:
    out: list[Finding] = []
    kind = {s.surface_id: s.surface_kind for s in surfaces}
    for sid, info in sorted(reach.items()):
        # a route whose effect reachability could not be resolved is UNKNOWN,
        # never silently "no effect" (fail-closed, D-0008-26)
        if kind.get(sid) == "HTTP_ROUTE" and info["exactness"] == "UNKNOWN":
            out.append(Finding(
                EFFECT_REACHABILITY_UNKNOWN, P2, sid,
                "route has no statically resolvable effect edges; effect "
                "reachability is UNKNOWN, not proven absent", {}))
    return out


# ---------------------------------------------------------------------------
# dominators (iterative data-flow; reuse of SP0003 algorithm)
# ---------------------------------------------------------------------------
def dominators(edges: dict, root_nodes: Iterable[str], all_nodes: Iterable[str]):
    """Classic iterative dominators from a synthetic ROOT that points at every
    root node. Returns {node: set(dominators)}."""
    ROOT = "\x00ROOT"
    succ = {n: set(edges.get(n, ())) for n in all_nodes}
    succ[ROOT] = set(root_nodes)
    nodes = set(all_nodes) | {ROOT}
    # predecessors
    pred = {n: set() for n in nodes}
    for n in nodes:
        for m in succ.get(n, ()):
            pred.setdefault(m, set()).add(n)
    dom = {n: set(nodes) for n in nodes}
    dom[ROOT] = {ROOT}
    changed = True
    while changed:
        changed = False
        for n in sorted(nodes):
            if n == ROOT:
                continue
            preds = pred.get(n, set())
            if not preds:
                new = {n}
            else:
                inter = None
                for p in preds:
                    inter = dom[p] if inter is None else (inter & dom[p])
                new = {n} | (inter or set())
            if new != dom[n]:
                dom[n] = new
                changed = True
    dom.pop(ROOT, None)
    return {n: (d - {"\x00ROOT"}) for n, d in dom.items()}


# ---------------------------------------------------------------------------
# minimal cut sets between route sources and effect sinks
# ---------------------------------------------------------------------------
def minimal_cut_sets(edges: dict, sources: Iterable[str],
                     sinks: set, *, max_size: int = MAX_CUT_SIZE,
                     limit: int = CUT_SET_LIMIT) -> dict:
    """Find minimal sets of intermediate nodes whose removal severs every
    source->sink path. Bounded search: EXACT if it completes under the limit,
    LIMIT_REACHED if truncated. Intermediate nodes only (never a source/sink)."""
    sources = list(sources)
    # candidate cut nodes: reachable intermediates that are not sources/sinks
    inter: set = set()
    for s in sources:
        inter |= reachable(edges, s)
    inter -= set(sources)
    inter -= sinks
    inter = sorted(inter)

    def severed(removed: set) -> bool:
        for s in sources:
            r = reachable({k: (v - removed) for k, v in edges.items()
                           if k not in removed}, s)
            if r & sinks:
                return False
        return True

    # if with nothing removed no source reaches a sink, cut set is empty
    if severed(set()):
        return {"exactness": "EXACT", "cut_sets": [], "reason": "no path"}

    found: list[list] = []
    truncated = False
    tried = 0
    for size in range(1, max_size + 1):
        for combo in combinations(inter, size):
            tried += 1
            if tried > limit:
                truncated = True
                break
            cs = set(combo)
            # skip supersets of an already-found minimal cut
            if any(set(f) <= cs for f in found):
                continue
            if severed(cs):
                found.append(sorted(cs))
        if truncated:
            break
    exact = "LIMIT_REACHED" if truncated else "EXACT"
    return {"exactness": exact, "cut_sets": sorted(found),
            "candidates": len(inter), "tried": tried}


def cut_set_findings(result: dict, subject: str) -> list[Finding]:
    out: list[Finding] = []
    if result.get("exactness") == "LIMIT_REACHED":
        out.append(Finding(
            CUT_SET_LIMIT_REACHED, P2, subject,
            "minimal cut-set search hit its bound; the reported cut sets are a "
            "lower bound, not a proven-complete set", {"result": result}))
    return out

"""Longest-prefix ownership resolution shared by bootstrap + conformance.

Maps an observed module/route/table to its declared canonical owner capability.
Deterministic: exactly one owner (longest matching prefix wins); ties across
capabilities at equal specificity are an ownership conflict (INV-0001-01).
"""
from __future__ import annotations

from typing import Any


def _match(value: str, capability_paths: list[tuple[str, list[str]]],
           kind: str) -> tuple[str | None, list[str]]:
    """Return (owner_id, conflicting_ids) by longest-prefix match.

    kind: 'path' matches module file paths / dotted; 'route' matches route
    string prefix; 'table' matches table-name prefix.
    """
    best_len = -1
    best_ids: list[str] = []
    for cap_id, prefixes in capability_paths:
        for pfx in prefixes:
            if _prefix_hit(value, pfx, kind):
                n = len(pfx)
                if n > best_len:
                    best_len = n
                    best_ids = [cap_id]
                elif n == best_len and cap_id not in best_ids:
                    best_ids.append(cap_id)
    if not best_ids:
        return None, []
    if len(best_ids) > 1:
        return None, sorted(best_ids)
    return best_ids[0], []


def _prefix_hit(value: str, prefix: str, kind: str) -> bool:
    if kind == "path":
        # value is a dotted module (finalis.crm.foo); prefix is a repo path
        # (finalis/crm/ or finalis/portal/crm_store.py). Normalize both.
        v = value.replace(".", "/")
        p = prefix[:-3] if prefix.endswith(".py") else prefix.rstrip("/")
        return v == p or v.startswith(p + "/") or value == prefix
    if kind == "route":
        return value == prefix or value.startswith(prefix.rstrip("/") + "/") \
            or value.startswith(prefix + "/") or value == prefix.rstrip("/")
    # table: exact or prefix
    return value == prefix or value.startswith(prefix)


def module_owner(module: str, caps: list[dict],
                 shared: dict[str, str]) -> tuple[str | None, list[str]]:
    if module in shared:
        return shared[module], []
    idx = [(c["id"], c["paths"]) for c in caps]
    return _match(module, idx, "path")


def _cid(c: dict) -> str:
    return c.get("id") or c["capability_id"]


def route_owner(route: str, caps: list[dict]) -> tuple[str | None, list[str]]:
    idx = [(_cid(c), c.get("routes", c.get("route_namespaces", []))) for c in caps]
    return _match(route, idx, "route")


def table_owner(table: str, caps: list[dict]) -> tuple[str | None, list[str]]:
    idx = [(_cid(c), c.get("tables", c.get("table_namespaces", []))) for c in caps]
    return _match(table, idx, "table")


def coverage_report(caps: list[dict], shared: dict[str, str],
                    modules: list[str]) -> dict[str, Any]:
    unowned: list[str] = []
    conflicts: list[dict[str, Any]] = []
    owned: dict[str, str] = {}
    for m in modules:
        owner, conf = module_owner(m, caps, shared)
        if conf:
            conflicts.append({"module": m, "candidates": conf})
        elif owner is None:
            unowned.append(m)
        else:
            owned[m] = owner
    return {"owned": owned, "unowned": sorted(unowned),
            "conflicts": conflicts}

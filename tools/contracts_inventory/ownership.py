"""Ownership + producer/consumer resolution with certainty typing (SP0008
§ownership, D-0008-13/14/15).

Ownership is inferred from the repository's real signal: the capability tag
(CORE|TOOL|EMP)-<X><N> on the first line of a module's docstring (SWARM-A §11).
Producers are the source sites that create a surface; consumers are the sites
that depend on it. Crucially, a consumer that cannot be established is UNKNOWN,
NOT zero (D-0008-15): "no consumer found" is a dark-consumer risk, never a
license to treat the surface as unused. A producer with no resolvable consumer
is an ORPHAN_PRODUCER candidate — surfaced, not deleted.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterable

from .model import (Finding, P1, P2, STATIC_CONFIRMED, DECLARED, UNKNOWN,
                    DARK_CONSUMER, ORPHAN_PRODUCER, OWNERSHIP_UNRESOLVED,
                    CONSUMER_CERTAINTY_UNKNOWN)

_CAP_TAG = re.compile(r"\b((?:CORE|TOOL|EMP)-[A-Z][0-9]+)\b")


def owner_of_module(root: Path, rel_path: str) -> str | None:
    """The owning capability = first cap tag in the module docstring, else None
    (OWNERSHIP_UNRESOLVED). Path-convention fallback keeps it deterministic."""
    path = root / rel_path
    if not path.exists() or not rel_path.endswith(".py"):
        return _path_convention_owner(rel_path)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return _path_convention_owner(rel_path)
    doc = ast.get_docstring(tree) or ""
    m = _CAP_TAG.search(doc)
    if m:
        return m.group(1)
    return _path_convention_owner(rel_path)


def _path_convention_owner(rel_path: str) -> str | None:
    if "ai_employee/tool_" in rel_path:
        return "TOOL-*"
    if "employee_work_inbox" in rel_path:
        return "EMP-A1"
    if "ai_employee/" in rel_path:
        return "CORE-*"
    return None


def resolve_owner(root: Path, surface) -> dict:
    """Owner for a surface = owner of its primary evidence module."""
    primary = surface.evidence[0][0] if surface.evidence else ""
    owner = owner_of_module(root, primary)
    return {"surface_id": surface.surface_id, "owner": owner,
            "primary_source": primary,
            "resolved": owner is not None and not owner.endswith("*")}


def ownership_findings(owner_rec: dict) -> list[Finding]:
    out: list[Finding] = []
    # OWNERSHIP_UNRESOLVED whenever ownership was not resolved to a SPECIFIC
    # capability — a wildcard path-convention owner ("CORE-*"/"TOOL-*") is not
    # a resolved owner (red-team P2), and neither is a missing one.
    if not owner_rec.get("resolved"):
        detail = ("no capability tag on the owning module and no path "
                  "convention matched; owner UNKNOWN"
                  if owner_rec["owner"] is None else
                  f"owner resolved only to a non-specific path convention "
                  f"{owner_rec['owner']!r}; not a specific capability")
        out.append(Finding(
            OWNERSHIP_UNRESOLVED, P2, owner_rec["surface_id"], detail,
            {"source": owner_rec["primary_source"],
             "owner": owner_rec["owner"]}))
    return out


# ---------------------------------------------------------------------------
# producer / consumer resolution with certainty typing
# ---------------------------------------------------------------------------
def resolve_producers(surface) -> list[dict]:
    """Producers = the grounded evidence sites that create the surface."""
    return [{"path": p, "line": ln, "certainty": STATIC_CONFIRMED}
            for p, ln in surface.evidence]


def resolve_consumers(root: Path, surface, *, name_index: dict) -> dict:
    """Resolve consumers of a surface with certainty typing (D-0008-13).

    name_index maps a searchable token -> set of (path, line) references found
    across the tree (built once by build_name_index). STATIC_CONFIRMED when a
    real reference exists; UNKNOWN when none is found (never "zero").
    """
    token = _consumer_token(surface)
    refs = sorted(name_index.get(token, set())) if token else []
    # exclude the surface's own producer sites
    prod = {(p, ln) for p, ln in surface.evidence}
    refs = [(p, ln) for (p, ln) in refs if (p, ln) not in prod]
    if refs:
        certainty = STATIC_CONFIRMED
    elif token:
        certainty = UNKNOWN
    else:
        certainty = DECLARED
    return {
        "surface_id": surface.surface_id,
        "consumer_token": token,
        "consumer_refs": [{"path": p, "line": ln} for p, ln in refs],
        "consumer_count_observed": len(refs),
        "certainty": certainty,
    }


def _consumer_token(surface) -> str | None:
    """The literal a consumer would reference. For events/tables that's the
    name; for routes it's the path (referenced by UI fetch / tests)."""
    kind = surface.surface_kind
    if kind in ("AUDIT_EVENT", "RUN_LEDGER_EVENT", "DB_TABLE",
                "CONFIG_KEY", "PROOF_ARTIFACT"):
        return surface.canonical_name.split(":")[-1]
    if kind == "HTTP_ROUTE":
        # the path portion after the method
        parts = surface.canonical_name.split(" ", 1)
        return parts[1] if len(parts) == 2 else None
    return None


def build_name_index(root: Path, tokens: Iterable[str]) -> dict:
    """One pass over the tree: for each interesting token, the (path,line) sites
    that mention it as a string literal. Deterministic and bounded to tokens."""
    tokset = {t for t in tokens if t}
    index: dict[str, set] = {t: set() for t in tokset}
    for path in sorted((root / "finalis").rglob("*.py")):
        rel = str(path.relative_to(root))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and node.value in index:
                index[node.value].add((rel, node.lineno))
    return index


def consumer_findings(surface, consumer_rec: dict) -> list[Finding]:
    out: list[Finding] = []
    if consumer_rec["certainty"] == UNKNOWN:
        # dark consumer: a surface with no resolvable consumer is a risk, not
        # a proven-unused surface (D-0008-15, fail-closed)
        out.append(Finding(
            DARK_CONSUMER, P2, surface.surface_id,
            "no static consumer reference found; consumer certainty is UNKNOWN "
            "(dark consumer risk), never treated as zero",
            {"token": consumer_rec["consumer_token"]}))
    return out


def orphan_producer_findings(surface, consumer_rec: dict) -> list[Finding]:
    """An effect-bearing surface produced but with no resolvable consumer is an
    orphan-producer candidate (surfaced for review, not removed)."""
    out: list[Finding] = []
    if surface.surface_kind in ("AUDIT_EVENT", "RUN_LEDGER_EVENT") \
            and consumer_rec["consumer_count_observed"] == 0:
        out.append(Finding(
            ORPHAN_PRODUCER, P2, surface.surface_id,
            "event surface is produced but has no resolvable consumer; "
            "orphan-producer candidate (review, do not delete)",
            {"token": consumer_rec["consumer_token"]}))
    return out

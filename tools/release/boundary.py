"""SP0009 change-boundary invariants (INV-0009-66/67 and the mission's default
boundary).

The release tooling itself must be inert: no live deployment, no product
migration (frontier stays v27), no external effect (fail-closed import
allowlist — a denylist of "known bad" calls is bypassable, the SP0008 red-team
P0 lesson), and it is never imported by product code (finalis/).
"""
from __future__ import annotations

import ast
from pathlib import Path

from .model import Finding, P0

PACKAGE = "tools.release"
FRONTIER_VERSION = 27

# Pure fail-closed allowlist. `os` is deliberately NOT here: the release
# tooling imports no `os` at all, so any os import (and thus every effectful
# os.* call — os.execlp/rename/chmod/putenv/... that a denylist would miss)
# is a boundary violation. An allowlist cannot be bypassed by an unenumerated
# call the way the SP0008-lesson denylist could (red-team #4).
ALLOWED_IMPORTS = frozenset({
    "__future__", "ast", "re", "json", "hashlib", "pathlib", "dataclasses",
    "typing", "itertools", "argparse", "sys", "collections", "functools",
    "math", "string", "enum",
})


def check_no_product_import(root: Path) -> list[Finding]:
    out: list[Finding] = []
    for path in sorted((root / "finalis").rglob("*.py")):
        rel = str(path.relative_to(root))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8",
                                            errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""]
            for m in mods:
                if m.startswith(PACKAGE):
                    out.append(Finding(
                        "BOUNDARY_VIOLATION", P0, rel,
                        f"product module imports {m!r}: release tooling is "
                        "never imported by product code", {"line": node.lineno}))
    return out


def check_no_external_effect(root: Path) -> list[Finding]:
    """Fail-closed import allowlist over tools/release/ (SP0008 lesson: never
    a call denylist)."""
    out: list[Finding] = []
    for path in sorted((root / "tools" / "release").rglob("*.py")):
        rel = str(path.relative_to(root))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8",
                                            errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top not in ALLOWED_IMPORTS:
                        out.append(Finding(
                            "BOUNDARY_VIOLATION", P0, rel,
                            f"tooling imports {alias.name!r}: not on the "
                            "fail-closed safe-import allowlist",
                            {"line": node.lineno}))
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue
                top = (node.module or "").split(".")[0]
                if top and top not in ALLOWED_IMPORTS:
                    out.append(Finding(
                        "BOUNDARY_VIOLATION", P0, rel,
                        f"tooling imports from {node.module!r}: not on the "
                        "allowlist", {"line": node.lineno}))
    return out


def check_frontier_unchanged(root: Path) -> list[Finding]:
    """Frontier stays v27, read from the AST MIGRATIONS list (quote-style
    robust — the SP0008 red-team P0 lesson)."""
    out: list[Finding] = []
    db = root / "finalis" / "portal" / "db.py"
    if not db.exists():
        return out
    try:
        tree = ast.parse(db.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return out
    versions = []
    for node in ast.walk(tree):
        value = None
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "MIGRATIONS"
                for t in node.targets):
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(
                node.target, ast.Name) and node.target.id == "MIGRATIONS":
            value = node.value
        if isinstance(value, (ast.List, ast.Tuple)):
            for elt in value.elts:
                if isinstance(elt, ast.Tuple) and elt.elts and isinstance(
                        elt.elts[0], ast.Constant) and isinstance(
                        elt.elts[0].value, int):
                    versions.append(elt.elts[0].value)
    top = max(versions) if versions else 0
    if top != FRONTIER_VERSION:
        out.append(Finding(
            "BOUNDARY_VIOLATION", P0, "finalis/portal/db.py",
            f"product DB frontier is v{top}, expected v{FRONTIER_VERSION}: "
            "SP0009 adds no product migration", {"frontier": top}))
    return out


def check_boundary(root: Path) -> list[Finding]:
    out: list[Finding] = []
    out.extend(check_no_product_import(root))
    out.extend(check_no_external_effect(root))
    out.extend(check_frontier_unchanged(root))
    return out

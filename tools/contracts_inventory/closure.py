"""Change-boundary closure invariants (SP0008 hard boundary, INV-0008-52/53/54).

The mission's non-negotiable boundary: this tooling makes ZERO product-runtime
behavior changes, opens ZERO external effects, adds ZERO product DB migrations
(the frontier stays v27), and is NEVER imported by product code (finalis/). This
module checks those invariants against the actual tree so a violation surfaces as
a P0 finding instead of shipping silently.
"""
from __future__ import annotations

import ast
from pathlib import Path

from .model import Finding, P0, BOUNDARY_VIOLATION

PACKAGE = "tools.contracts_inventory"
PRODUCT_ROOT = "finalis"
FRONTIER_VERSION = 27


def check_no_product_import(root: Path) -> list[Finding]:
    """No file under finalis/ may import tools.contracts_inventory (INV-53)."""
    out: list[Finding] = []
    for path in sorted((root / PRODUCT_ROOT).rglob("*.py")):
        rel = str(path.relative_to(root))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""]
            for m in mods:
                if m.startswith(PACKAGE) or m.startswith(
                        "tools.contracts_inventory"):
                    out.append(Finding(
                        BOUNDARY_VIOLATION, P0, rel,
                        f"product module imports {m!r}: governance tooling must "
                        "never be imported by product code (INV-0008-53)",
                        {"line": node.lineno}))
    return out


# Fail-closed ALLOWLIST of top-level modules the tooling may import. Anything
# outside this set (network, subprocess, ctypes, …) is a boundary violation by
# default — a denylist of "known bad" calls can never be complete (red-team P0).
ALLOWED_IMPORTS = frozenset({
    "__future__", "ast", "re", "json", "hashlib", "pathlib", "dataclasses",
    "typing", "itertools", "argparse", "sys", "collections", "functools",
    "math", "string", "enum",
})
# os is allowed ONLY for path/read helpers; these os attributes reach effects.
FORBIDDEN_OS_ATTRS = frozenset({
    "system", "popen", "execv", "execve", "execvp", "execvpe", "execl",
    "execle", "execlp", "spawnv", "spawnl", "fork", "kill", "remove",
    "unlink", "rmdir", "removedirs",
})


def check_no_external_effect(root: Path) -> list[Finding]:
    """The tooling must open NO external effect (INV-0008-52). Fail-closed:
    (1) it may import only stdlib-safe modules on the allowlist (any other
    import — socket, subprocess, urllib, requests, httpx, ctypes, … — is a
    violation), and (2) it may not call effect-bearing os.* functions."""
    out: list[Finding] = []
    pkg_dir = root / "tools" / "contracts_inventory"
    for path in sorted(pkg_dir.rglob("*.py")):
        rel = str(path.relative_to(root))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            # (1) import allowlist
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top != "os" and top not in ALLOWED_IMPORTS:
                        out.append(Finding(
                            BOUNDARY_VIOLATION, P0, rel,
                            f"tooling imports {alias.name!r}, which is not on "
                            "the fail-closed safe-import allowlist "
                            "(INV-0008-52)", {"line": node.lineno}))
            elif isinstance(node, ast.ImportFrom):
                # relative imports (from . / from .x) are always in-package
                if node.level and node.level > 0:
                    continue
                top = (node.module or "").split(".")[0]
                if top and top != "os" and top not in ALLOWED_IMPORTS:
                    out.append(Finding(
                        BOUNDARY_VIOLATION, P0, rel,
                        f"tooling imports from {node.module!r}, not on the "
                        "fail-closed safe-import allowlist (INV-0008-52)",
                        {"line": node.lineno}))
            # (2) forbidden os.* effect calls
            elif isinstance(node, ast.Call) and isinstance(node.func,
                                                           ast.Attribute):
                if node.func.attr in FORBIDDEN_OS_ATTRS:
                    out.append(Finding(
                        BOUNDARY_VIOLATION, P0, rel,
                        f"tooling calls .{node.func.attr}(): an effect-bearing "
                        "operation forbidden by the change boundary "
                        "(INV-0008-52)", {"line": node.lineno}))
    return out


def _migration_versions(root: Path) -> list:
    """Every migration version, read from the AST MIGRATIONS list (robust to
    quote style / constant SQL — a regex on `(N, \"\"\"` misses `(28, '...'`
    or `(28, SQL_CONST)`; red-team P0)."""
    db = root / "finalis" / "portal" / "db.py"
    if not db.exists():
        return []
    try:
        tree = ast.parse(db.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    versions = []
    for node in ast.walk(tree):
        target_names = []
        if isinstance(node, ast.Assign):
            target_names = [t.id for t in node.targets
                            if isinstance(t, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target,
                                                            ast.Name):
            target_names = [node.target.id]
            value = node.value
        else:
            continue
        if "MIGRATIONS" not in target_names or not isinstance(
                value, (ast.List, ast.Tuple)):
            continue
        for elt in value.elts:
            if isinstance(elt, ast.Tuple) and elt.elts and isinstance(
                    elt.elts[0], ast.Constant) and isinstance(
                    elt.elts[0].value, int):
                versions.append(elt.elts[0].value)
    return versions


def check_frontier_unchanged(root: Path) -> list[Finding]:
    """The product DB frontier must remain v27 — tooling adds no migration."""
    out: list[Finding] = []
    versions = _migration_versions(root)
    top = max(versions) if versions else 0
    if top != FRONTIER_VERSION:
        out.append(Finding(
            BOUNDARY_VIOLATION, P0, "finalis/portal/db.py",
            f"product DB frontier is v{top}, expected v{FRONTIER_VERSION}: "
            "the inventory tooling must add no product migration",
            {"frontier": top}))
    return out


def check_boundary(root: Path) -> list[Finding]:
    """All boundary invariants together."""
    out: list[Finding] = []
    out.extend(check_no_product_import(root))
    out.extend(check_no_external_effect(root))
    out.extend(check_frontier_unchanged(root))
    return out

"""Change-boundary check (SP0011 §2.1, D-0011, INV-113/114).

The evaluation tooling must never import product runtime (finalis/), must open no
external effect (no network / subprocess / live provider), must consume no product
migration, and must not be imported BY product code. This is a fail-closed
allowlist scan over the evaluation package's own imports.
"""
from __future__ import annotations

import ast
from pathlib import Path

from .model import Finding, P0

_PKG = "tools/evaluation"
# modules the evaluation kernel is allowed to import (std-lib + itself)
_FORBIDDEN_PREFIXES = ("finalis",)
_FORBIDDEN_EFFECT_MODULES = ("socket", "subprocess", "urllib", "requests",
                             "http.client", "smtplib", "ftplib", "asyncio")


def _imports(path: Path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    mods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.append(node.module)
    return mods


def check_boundary(root: Path) -> list[Finding]:
    root = Path(root)
    pkg = root / _PKG
    out: list[Finding] = []
    if not pkg.is_dir():
        return out
    for py in sorted(pkg.glob("*.py")):
        for mod in _imports(py):
            top = mod.split(".")[0]
            if any(mod == p or mod.startswith(p + ".")
                   for p in _FORBIDDEN_PREFIXES):
                out.append(Finding("BOUNDARY_VIOLATION", P0, py.name,
                                   f"evaluation module imports product code: "
                                   f"{mod}", {}))
            if mod in _FORBIDDEN_EFFECT_MODULES or top in \
                    ("socket", "subprocess", "smtplib", "ftplib"):
                out.append(Finding("BOUNDARY_VIOLATION", P0, py.name,
                                   f"evaluation module imports external-effect "
                                   f"module: {mod}", {}))
    return out

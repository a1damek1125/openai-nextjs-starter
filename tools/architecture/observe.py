"""Observed Architecture Digital Twin — deterministic repository scanner.

Reads reality from the filesystem via static analysis only (Python AST + text
parsing). It NEVER imports application modules to inspect them (SP0001 §11.1).
Fail-closed: a file that should be scanned but cannot be parsed becomes a
SCAN_ERROR, never a silent skip (§17.2, AC-0001-39). Unknown languages under a
scanned tree surface as UNSUPPORTED_LANGUAGE, never ignored (§18.1, AC-0001-49).
"""
from __future__ import annotations

import ast
import os
import re
from typing import Any

from .canon import sha256_hex
from .model import ObservedSnapshot

SCAN_PACKAGE = "finalis"
ROUTE_METHODS = {"get", "post", "put", "delete", "patch"}
# Outbound / real-external-effect primitives. Presence in non-test product code
# is an effect-gate observation (the current closed gate expects zero).
EFFECT_MODULES = {
    "requests", "httpx", "aiohttp", "urllib.request", "http.client",
    "smtplib", "socket", "ftplib", "telnetlib", "boto3", "paramiko",
    "websocket", "websockets",
}
DYNAMIC_IMPORT_NAMES = {"__import__"}
# Source languages we know how to architecturally scan. Others -> UNSUPPORTED.
KNOWN_SOURCE_EXT = {".py"}
FOREIGN_SOURCE_EXT = {".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java"}


def _module_name(repo_root: str, path: str) -> str:
    rel = os.path.relpath(path, repo_root)
    return rel[:-3].replace(os.sep, ".") if rel.endswith(".py") else rel


def _iter_py_files(root: str) -> list[str]:
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def _internal_import_edges(module: str, tree: ast.AST) -> list[list[str]]:
    edges: list[list[str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == SCAN_PACKAGE:
                    edges.append([module, alias.name])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # relative import -> resolve against the module's package
                pkg = module.rsplit(".", node.level)[0]
                target = f"{pkg}.{node.module}" if node.module else pkg
                edges.append([module, target])
            elif node.module and node.module.split(".")[0] == SCAN_PACKAGE:
                edges.append([module, node.module])
    return edges


def _effect_observations(module: str, path: str,
                         tree: ast.AST) -> list[dict[str, Any]]:
    obs: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in EFFECT_MODULES or \
                        alias.name.split(".")[0] in EFFECT_MODULES:
                    obs.append({"module": module, "path": path,
                                "kind": "import", "target": alias.name,
                                "line": node.lineno})
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            full = base
            if full in EFFECT_MODULES or base.split(".")[0] in EFFECT_MODULES:
                obs.append({"module": module, "path": path,
                            "kind": "from_import", "target": base,
                            "line": node.lineno})
            if base == "urllib" and any(a.name == "request" for a in node.names):
                obs.append({"module": module, "path": path,
                            "kind": "from_import", "target": "urllib.request",
                            "line": node.lineno})
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in DYNAMIC_IMPORT_NAMES:
            obs.append({"module": module, "path": path,
                        "kind": "dynamic_import", "target": node.func.id,
                        "line": node.lineno})
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            base = node.func.value.id if isinstance(node.func.value, ast.Name) else ""
            # importlib.import_module(...) — dynamic import blind spot
            if attr == "import_module":
                obs.append({"module": module, "path": path,
                            "kind": "dynamic_import", "target": "importlib.import_module",
                            "line": node.lineno})
            # subprocess.* / os.system / os.popen — potential shell-out egress
            elif (base == "subprocess" and attr in
                  ("run", "Popen", "call", "check_output", "check_call")) \
                    or (base == "os" and attr in ("system", "popen")):
                obs.append({"module": module, "path": path,
                            "kind": "subprocess_exec", "target": f"{base}.{attr}",
                            "line": node.lineno})
    return obs


def _route_edges(module: str, tree: ast.AST) -> list[list[str]]:
    edges: list[list[str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            f = dec.func
            if isinstance(f, ast.Attribute) and f.attr in ROUTE_METHODS \
                    and isinstance(f.value, ast.Name) and f.value.id == "app":
                if dec.args and isinstance(dec.args[0], ast.Constant) \
                        and isinstance(dec.args[0].value, str):
                    edges.append([dec.args[0].value, module])
    return edges


_MIG_TUPLE = re.compile(r"CREATE TABLE IF NOT EXISTS\s+([a-z_][a-z0-9_]*)",
                        re.IGNORECASE)


def _parse_migrations(repo_root: str) -> tuple[list[list[str]], list[list[str]],
                                               list[dict[str, Any]]]:
    """Return (migration_digests, data_ownership, scan_errors).

    Extracts the MIGRATIONS list from finalis/portal/db.py by AST + literal_eval
    (never executes the module). Each (version, sql) yields a digest and its
    owned tables.
    """
    db_path = os.path.join(repo_root, "finalis", "portal", "db.py")
    digests: list[list[str]] = []
    ownership: list[list[str]] = []
    errors: list[dict[str, Any]] = []
    try:
        src = open(db_path, encoding="utf-8").read()
        tree = ast.parse(src)
    except (OSError, SyntaxError) as e:  # fail-closed
        return [], [], [{"path": db_path, "error": f"{type(e).__name__}: {e}"}]
    migrations_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "MIGRATIONS":
                    migrations_node = node.value
        elif isinstance(node, ast.AnnAssign):  # MIGRATIONS: list[...] = [...]
            if isinstance(node.target, ast.Name) and \
                    node.target.id == "MIGRATIONS" and node.value is not None:
                migrations_node = node.value
    if migrations_node is None:
        return [], [], [{"path": db_path, "error": "MIGRATIONS not found"}]
    try:
        migrations = ast.literal_eval(migrations_node)
    except Exception as e:  # noqa: BLE001 - fail-closed on malformed literal
        return [], [], [{"path": db_path,
                         "error": f"MIGRATIONS literal: {e}"}]
    for entry in migrations:
        version, sql = int(entry[0]), str(entry[1])
        digests.append([str(version), sha256_hex(sql)])
        for table in _MIG_TUPLE.findall(sql):
            if table != "schema_version":
                ownership.append([table, str(version)])
    return sorted(digests, key=lambda d: int(d[0])), sorted(ownership), errors


def _git_head(repo_root: str) -> str:
    head = os.path.join(repo_root, ".git", "HEAD")
    try:
        ref = open(head, encoding="utf-8").read().strip()
        if ref.startswith("ref:"):
            ref_path = os.path.join(repo_root, ".git", ref[5:].strip())
            return open(ref_path, encoding="utf-8").read().strip()
        return ref
    except OSError:
        return "UNKNOWN"


def build_observed(repo_root: str, commit: str | None = None) -> ObservedSnapshot:
    scan_root = os.path.join(repo_root, SCAN_PACKAGE)
    modules: list[str] = []
    import_edges: list[list[str]] = []
    route_edges: list[list[str]] = []
    effect_obs: list[dict[str, Any]] = []
    scan_errors: list[dict[str, Any]] = []

    for path in _iter_py_files(scan_root):
        module = _module_name(repo_root, path)
        modules.append(module)
        try:
            src = open(path, encoding="utf-8").read()
            tree = ast.parse(src, filename=path)
        except (OSError, SyntaxError, ValueError) as e:  # fail-closed
            scan_errors.append({"path": os.path.relpath(path, repo_root),
                                "error": f"{type(e).__name__}: {e}"})
            continue
        import_edges.extend(_internal_import_edges(module, tree))
        effect_obs.extend(_effect_observations(
            module, os.path.relpath(path, repo_root), tree))
        if module.endswith("portal.app"):
            route_edges.extend(_route_edges(module, tree))

    # unsupported foreign languages under the scan tree (surface, never ignore)
    for dirpath, dirnames, filenames in os.walk(scan_root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            ext = os.path.splitext(fn)[1]
            if ext in FOREIGN_SOURCE_EXT:
                scan_errors.append({
                    "path": os.path.relpath(os.path.join(dirpath, fn),
                                            repo_root),
                    "error": f"UNSUPPORTED_LANGUAGE ({ext}): no ScannerAdapter"})

    digests, ownership, mig_errors = _parse_migrations(repo_root)
    scan_errors.extend(mig_errors)

    metrics = {
        "files_scanned": len(modules),
        "modules": len(modules),
        "import_edges": len(import_edges),
        "routes": len(route_edges),
        "tables": len(ownership),
        "migrations": len(digests),
        "effect_observations": len(effect_obs),
        "scan_errors": len(scan_errors),
    }
    return ObservedSnapshot(
        commit=commit or _git_head(repo_root),
        modules=modules,
        capabilities=[],   # filled by conformance from the declared twin
        import_edges=import_edges,
        route_edges=route_edges,
        data_ownership=ownership,
        migration_digests=digests,
        effect_observations=effect_obs,
        metrics=metrics,
        scan_errors=scan_errors,
    )

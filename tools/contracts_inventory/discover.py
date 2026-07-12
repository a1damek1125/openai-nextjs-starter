"""Real discovery of contract surfaces from the actual repository (SP0008 §5,
§6, D-0008-02/03/04).

This is the point the mission turns on: the inventory records the surfaces that
ARE implemented in the tree, evidenced by their source location, not schemas,
examples, or mocks. Each detector is a deterministic reader over a specific code
pattern and returns raw *observations* — (surface_kind, canonical_name, evidence
location, structural shape) — that carry the exact file+line they were read from.
Reconciliation, identity resolution and criticality happen downstream; a detector
only reports what it can literally see, and records its own blind spots.

Every observation is grounded: `evidence.path` + `evidence.line` point at real
source. Detectors never invent a surface they cannot cite (D-0008-16,
INV-0008-17). Governance tooling only; never imported by product code.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .canon import surface_id, structural_fingerprint, sha256_hex
from .model import SURFACE_KINDS


def _sha(text: str) -> str:
    return sha256_hex(text)


# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Observation:
    """One raw sighting of a surface by one detector, grounded in source."""
    detector: str
    surface_kind: str
    canonical_name: str
    evidence_path: str
    evidence_line: int
    shape: dict = field(default_factory=dict)

    @property
    def surface_id(self) -> str:
        return surface_id(self.surface_kind, self.canonical_name)

    def as_dict(self) -> dict:
        return {
            "detector": self.detector,
            "surface_kind": self.surface_kind,
            "canonical_name": self.canonical_name,
            "surface_id": self.surface_id,
            "evidence": {"path": self.evidence_path, "line": self.evidence_line},
            "shape": self.shape,
            "structural_fingerprint": structural_fingerprint(self.shape),
        }


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# detector: HTTP routes — @app.<method>("path") decorators (finalis/portal/app.py)
# ---------------------------------------------------------------------------
_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")


def _decorator_method_path(dec: ast.expr):
    """Return (METHOD, path) for an @app.<method>("path") decorator, else None."""
    if not isinstance(dec, ast.Call):
        return None
    fn = dec.func
    if not (isinstance(fn, ast.Attribute) and fn.attr in _HTTP_METHODS):
        return None
    if not dec.args:
        return None
    a0 = dec.args[0]
    if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
        return fn.attr.upper(), a0.value
    return None


def _add_api_route(call: ast.Call):
    """Return list of (METHOD, path) for app.add_api_route("path", h,
    methods=[...]) with a LITERAL path; else []. Concatenated paths are a
    known blind spot (recorded in BLIND_SPOTS), not silently dropped."""
    fn = call.func
    if not (isinstance(fn, ast.Attribute) and fn.attr == "add_api_route"):
        return []
    if not call.args or not isinstance(call.args[0], ast.Constant) \
            or not isinstance(call.args[0].value, str):
        return []
    route = call.args[0].value
    methods = ["GET"]
    for kw in call.keywords:
        if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
            got = [e.value for e in kw.value.elts
                   if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if got:
                methods = got
    return [(m.upper(), route) for m in methods]


def detect_http_routes(root: Path) -> list[Observation]:
    out: list[Observation] = []
    for relpath in ("finalis/portal/app.py", "finalis/portal/ui.py"):
        path = root / relpath
        if not path.exists():
            continue
        rel = _rel(path, root)
        tree = ast.parse(_read(path))
        for node in ast.walk(tree):
            # (a) decorator routes @app.<method>("path") (incl. stacked)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    mp = _decorator_method_path(dec)
                    if mp is None:
                        continue
                    method, route = mp
                    out.append(Observation(
                        detector="http_routes", surface_kind="HTTP_ROUTE",
                        canonical_name=f"{method} {route}", evidence_path=rel,
                        evidence_line=dec.lineno,
                        shape={"method": method, "path": route,
                               "handler": node.name, "registration": "decorator",
                               "path_params": re.findall(r"\{(\w+)\}", route)}))
            # (b) dynamic app.add_api_route("path", handler, methods=[...])
            if isinstance(node, ast.Call):
                for method, route in _add_api_route(node):
                    out.append(Observation(
                        detector="http_routes", surface_kind="HTTP_ROUTE",
                        canonical_name=f"{method} {route}", evidence_path=rel,
                        evidence_line=node.lineno,
                        shape={"method": method, "path": route,
                               "registration": "add_api_route",
                               "path_params": re.findall(r"\{(\w+)\}", route)}))
    return out


# ---------------------------------------------------------------------------
# detector: DB migrations + tables — MIGRATIONS list[tuple[int, sql]] (db.py)
# ---------------------------------------------------------------------------
_CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE)
# capture the table name + its parenthesized column body so a MATERIAL DDL
# change (e.g. dropping tenant_id) moves the surface fingerprint (red-team P1)
_CREATE_TABLE_BODY = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\((.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL)


def _normalize_ddl(body: str) -> str:
    """Whitespace-normalize a CREATE TABLE column body for a stable, material
    fingerprint (collapses formatting, preserves column/constraint content)."""
    return re.sub(r"\s+", " ", body).strip()


def _migrations_node(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "MIGRATIONS":
                    return node.value
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "MIGRATIONS":
                return node.value
    return None


def detect_db(root: Path) -> list[Observation]:
    out: list[Observation] = []
    path = root / "finalis" / "portal" / "db.py"
    if not path.exists():
        return out
    rel = _rel(path, root)
    tree = ast.parse(_read(path))
    mig = _migrations_node(tree)
    if not isinstance(mig, (ast.List, ast.Tuple)):
        return out
    seen_tables: dict[str, int] = {}
    for elt in mig.elts:
        if not (isinstance(elt, ast.Tuple) and len(elt.elts) >= 2):
            continue
        ver_node, sql_node = elt.elts[0], elt.elts[1]
        if not (isinstance(ver_node, ast.Constant)
                and isinstance(ver_node.value, int)):
            continue
        version = ver_node.value
        line = elt.lineno
        sql = sql_node.value if isinstance(sql_node, ast.Constant) else None
        # the migration's SQL is material: a DDL change at a fixed version must
        # move this surface's fingerprint (red-team P1). Non-literal SQL is
        # recorded as such, never silently treated as empty.
        if isinstance(sql, str):
            sql_material = _sha(_normalize_ddl(sql))
        else:
            sql_material = "NON_LITERAL_SQL"
        out.append(Observation(
            detector="db_migrations", surface_kind="DB_MIGRATION",
            canonical_name=f"migration:{version}", evidence_path=rel,
            evidence_line=line,
            shape={"version": version, "sql_material": sql_material}))
        if not isinstance(sql, str):
            continue
        for m in _CREATE_TABLE_BODY.finditer(sql):
            table, body = m.group(1), m.group(2)
            if table not in seen_tables:
                seen_tables[table] = version
                out.append(Observation(
                    detector="db_migrations", surface_kind="DB_TABLE",
                    canonical_name=table, evidence_path=rel, evidence_line=line,
                    shape={"created_in_migration": version,
                           "ddl_material": _sha(_normalize_ddl(body))}))
        # tables matched by the name-only pattern but not the body pattern
        # (unusual DDL) are still recorded, with the DDL marked unresolved
        for m in _CREATE_TABLE.finditer(sql):
            table = m.group(1)
            if table not in seen_tables:
                seen_tables[table] = version
                out.append(Observation(
                    detector="db_migrations", surface_kind="DB_TABLE",
                    canonical_name=table, evidence_path=rel, evidence_line=line,
                    shape={"created_in_migration": version,
                           "ddl_material": "DDL_BODY_UNRESOLVED"}))
    return out


# ---------------------------------------------------------------------------
# detector: run-ledger events — EVENT_SCHEMA dict keys (run_ledger.py)
# ---------------------------------------------------------------------------
def detect_run_ledger_events(root: Path) -> list[Observation]:
    out: list[Observation] = []
    path = root / "finalis" / "ai_employee" / "run_ledger.py"
    if not path.exists():
        return out
    rel = _rel(path, root)
    tree = ast.parse(_read(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if not (isinstance(tgt, ast.Name) and tgt.id == "EVENT_SCHEMA"):
                continue
            if not isinstance(node.value, ast.Dict):
                continue
            for k in node.value.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    out.append(Observation(
                        detector="run_ledger_events",
                        surface_kind="RUN_LEDGER_EVENT",
                        canonical_name=k.value, evidence_path=rel,
                        evidence_line=k.lineno, shape={"event_type": k.value}))
    return out


# ---------------------------------------------------------------------------
# detector: audit events — string literals passed as event_type=... (whole tree)
# audit event families are dotted strings; capture literal call keywords.
# ---------------------------------------------------------------------------
# audit event names come in two real conventions (SWARM-A §3): dotted-lowercase
# families ("case.state_changed") and UPPER_SNAKE literals ("CASE_CREATED").
_DOTTED_EVENT = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
_UPPER_EVENT = re.compile(r"^[A-Z][A-Z0-9_]{2,}$")


def _audit_event_name(value: str):
    if _DOTTED_EVENT.match(value):
        return ("dotted", value)
    if _UPPER_EVENT.match(value):
        return ("upper", value)
    return None


def detect_audit_events(root: Path) -> list[Observation]:
    out: list[Observation] = []
    seen: set[str] = set()
    for path in sorted((root / "finalis").rglob("*.py")):
        rel = _rel(path, root)
        try:
            tree = ast.parse(_read(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg != "event_type":
                    continue
                v = kw.value
                if not (isinstance(v, ast.Constant)
                        and isinstance(v.value, str)):
                    continue
                named = _audit_event_name(v.value)
                if named is None or v.value in seen:
                    continue
                seen.add(v.value)
                out.append(Observation(
                    detector="audit_events", surface_kind="AUDIT_EVENT",
                    canonical_name=v.value, evidence_path=rel,
                    evidence_line=v.lineno,
                    shape={"event_type": v.value, "convention": named[0]}))
    return out


# ---------------------------------------------------------------------------
# detector: state machines — Enum subclasses + a TRANSITIONS mapping
# ---------------------------------------------------------------------------
def _is_enum_base(base: ast.expr) -> bool:
    if isinstance(base, ast.Name):
        return base.id in ("Enum", "IntEnum", "StrEnum")
    if isinstance(base, ast.Attribute):
        return base.attr in ("Enum", "IntEnum", "StrEnum")
    return False


def detect_state_machines(root: Path) -> list[Observation]:
    out: list[Observation] = []
    for path in sorted((root / "finalis").rglob("*.py")):
        rel = _rel(path, root)
        try:
            tree = ast.parse(_read(path))
        except SyntaxError:
            continue
        module = rel[:-3].replace("/", ".")
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not any(_is_enum_base(b) for b in node.bases):
                continue
            members = [n.target.id for n in node.body
                       if isinstance(n, ast.AnnAssign)
                       and isinstance(n.target, ast.Name)]
            members += [t.id for n in node.body if isinstance(n, ast.Assign)
                        for t in n.targets if isinstance(t, ast.Name)]
            if not members:
                continue
            canonical = f"{module}:{node.name}"
            out.append(Observation(
                detector="state_machines", surface_kind="STATE_MACHINE",
                canonical_name=canonical, evidence_path=rel,
                evidence_line=node.lineno,
                shape={"class": node.name, "states": sorted(set(members))}))
            for member in sorted(set(members)):
                out.append(Observation(
                    detector="state_machines", surface_kind="STATE_TRANSITION",
                    canonical_name=f"{canonical}.{member}", evidence_path=rel,
                    evidence_line=node.lineno,
                    shape={"machine": canonical, "state": member}))
    return out


# ---------------------------------------------------------------------------
# detector: proof artifacts — hashlib.sha256 / *_hash defs / merkle references
# ---------------------------------------------------------------------------
_PROOF_HINT = re.compile(r"(sha256|merkle|proof|envelope|digest)", re.IGNORECASE)


def detect_proof_artifacts(root: Path) -> list[Observation]:
    out: list[Observation] = []
    seen: set[str] = set()
    for path in sorted((root / "finalis").rglob("*.py")):
        rel = _rel(path, root)
        try:
            tree = ast.parse(_read(path))
        except SyntaxError:
            continue
        module = rel[:-3].replace("/", ".")
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and _PROOF_HINT.search(node.name):
                canonical = f"{module}:{node.name}"
                if canonical in seen:
                    continue
                seen.add(canonical)
                out.append(Observation(
                    detector="proof_artifacts", surface_kind="PROOF_ARTIFACT",
                    canonical_name=canonical, evidence_path=rel,
                    evidence_line=node.lineno,
                    shape={"function": node.name}))
    return out


# ---------------------------------------------------------------------------
# detector: config keys — os.environ[...] / os.getenv(...) / os.environ.get(...)
# ---------------------------------------------------------------------------
def _env_key(node: ast.AST):
    # os.getenv("KEY") / os.environ.get("KEY")
    if isinstance(node, ast.Call):
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr in ("getenv", "get"):
            if node.args and isinstance(node.args[0], ast.Constant) \
                    and isinstance(node.args[0].value, str):
                # only treat os.environ.get / os.getenv
                base = fn.value
                is_env = (isinstance(base, ast.Attribute)
                          and base.attr == "environ") or \
                         (isinstance(base, ast.Name) and base.id == "os")
                if fn.attr == "getenv" or is_env:
                    return node.args[0].value
    # os.environ["KEY"]
    if isinstance(node, ast.Subscript):
        val = node.value
        if isinstance(val, ast.Attribute) and val.attr == "environ":
            sl = node.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                return sl.value
    return None


def detect_config_keys(root: Path) -> list[Observation]:
    out: list[Observation] = []
    seen: set[str] = set()
    for path in sorted((root / "finalis").rglob("*.py")):
        rel = _rel(path, root)
        try:
            tree = ast.parse(_read(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            key = _env_key(node)
            if key and key not in seen:
                seen.add(key)
                out.append(Observation(
                    detector="config_keys", surface_kind="CONFIG_KEY",
                    canonical_name=key, evidence_path=rel,
                    evidence_line=getattr(node, "lineno", 0),
                    shape={"env_key": key}))
    return out


# ---------------------------------------------------------------------------
# detector: CLI commands — argparse add_parser / click/typer command decorators
# ---------------------------------------------------------------------------
def detect_cli_commands(root: Path) -> list[Observation]:
    out: list[Observation] = []
    seen: set[str] = set()
    for path in sorted((root / "finalis").rglob("*.py")):
        rel = _rel(path, root)
        try:
            tree = ast.parse(_read(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "add_parser" and node.args \
                    and isinstance(node.args[0], ast.Constant) \
                    and isinstance(node.args[0].value, str):
                name = node.args[0].value
                if name in seen:
                    continue
                seen.add(name)
                out.append(Observation(
                    detector="cli_commands", surface_kind="CLI_COMMAND",
                    canonical_name=name, evidence_path=rel,
                    evidence_line=node.lineno, shape={"command": name}))
    return out


# ---------------------------------------------------------------------------
# detector: proof/contract version envelopes — module constants of the form
# NAME = "finalis-<slug>-v<N>" (SWARM-A §6: 349 versioned envelope constants).
# These ARE contract surfaces: a versioned proof/envelope identifier.
# ---------------------------------------------------------------------------
_VERSION_ENVELOPE = re.compile(r"^finalis-[a-z0-9-]+-v[0-9]+$")


def detect_proof_versions(root: Path) -> list[Observation]:
    out: list[Observation] = []
    seen: set[str] = set()
    for path in sorted((root / "finalis").rglob("*.py")):
        rel = _rel(path, root)
        try:
            tree = ast.parse(_read(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not (isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                    and _VERSION_ENVELOPE.match(node.value.value)):
                continue
            token = node.value.value
            if token in seen:
                continue
            seen.add(token)
            out.append(Observation(
                detector="proof_versions", surface_kind="PROOF_ARTIFACT",
                canonical_name=token, evidence_path=rel,
                evidence_line=node.lineno,
                shape={"envelope_version": token, "kind": "version_constant"}))
    return out


# ---------------------------------------------------------------------------
# detector: declared config keys from .env.example (declared-but-optional set;
# SWARM-A §9). Declared surfaces even when never read in code — the negative
# space between declared and read is exactly what the inventory must expose.
# ---------------------------------------------------------------------------
_ENV_LINE = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]+)\s*=")


def detect_declared_config(root: Path) -> list[Observation]:
    out: list[Observation] = []
    path = root / ".env.example"
    if not path.exists():
        return out
    rel = _rel(path, root)
    seen: set[str] = set()
    for i, line in enumerate(_read(path).splitlines(), start=1):
        m = _ENV_LINE.match(line)
        if not m:
            continue
        key = m.group(1)
        if key in seen:
            continue
        seen.add(key)
        commented = line.lstrip().startswith("#")
        out.append(Observation(
            detector="declared_config", surface_kind="CONFIG_KEY",
            canonical_name=key, evidence_path=rel, evidence_line=i,
            shape={"env_key": key, "source": "env_example",
                   "declared_only": commented}))
    return out


# ---------------------------------------------------------------------------
# the detector registry (order fixed for determinism)
# ---------------------------------------------------------------------------
DETECTORS = (
    ("http_routes", detect_http_routes),
    ("db_migrations", detect_db),
    ("run_ledger_events", detect_run_ledger_events),
    ("audit_events", detect_audit_events),
    ("state_machines", detect_state_machines),
    ("proof_artifacts", detect_proof_artifacts),
    ("proof_versions", detect_proof_versions),
    ("config_keys", detect_config_keys),
    ("declared_config", detect_declared_config),
    ("cli_commands", detect_cli_commands),
)


# Known, DECLARED detector blind spots (SWARM-A caveats). Recording a blind
# spot is a first-class inventory output: it bounds the negative space and feeds
# residual estimation. A blind spot is never a silent omission (D-0008-16/34).
BLIND_SPOTS = (
    {"detector": "http_routes", "kind": "HTTP_ROUTE",
     "blind_to": "add_api_route paths built by string concatenation "
                 "(e.g. '/ai-employee/work-inbox/' + path); only literal "
                 "arg0 paths are recovered",
     "under_reports": True},
    {"detector": "state_machines", "kind": "STATE_TRANSITION",
     "blind_to": "transitions synthesized at runtime — lifecycle._build_edges "
                 "universal edges, employee_work_inbox set-unions and "
                 "dict-comprehension splats; only enum members are recovered",
     "under_reports": True},
    {"detector": "audit_events", "kind": "AUDIT_EVENT",
     "blind_to": "event_type values built from f-strings / variables rather "
                 "than string literals",
     "under_reports": True},
    {"detector": "config_keys", "kind": "CONFIG_KEY",
     "blind_to": "keys read via indirection or a settings object rather than "
                 "a direct os.environ/os.getenv literal",
     "under_reports": True},
    {"detector": "cli_commands", "kind": "CLI_COMMAND",
     "blind_to": "the product package finalis/ exposes no argparse CLI; only "
                 "governance tooling under tools/ does (out of product scope)",
     "under_reports": False},
    {"detector": "http_routes", "kind": "HTTP_ROUTE",
     "blind_to": "routes are read only from finalis/portal/app.py and "
                 "finalis/portal/ui.py; a route defined in any other module "
                 "would not be seen (file-scoped detector)",
     "under_reports": True},
    {"detector": "db_migrations", "kind": "DB_MIGRATION",
     "blind_to": "migrations are read only from finalis/portal/db.py, and a "
                 "migration whose version is a non-literal is skipped (its DDL "
                 "is recorded as NON_LITERAL_SQL rather than dropped)",
     "under_reports": True},
    {"detector": "run_ledger_events", "kind": "RUN_LEDGER_EVENT",
     "blind_to": "run-ledger events are read only from the EVENT_SCHEMA dict "
                 "in finalis/ai_employee/run_ledger.py (file-scoped)",
     "under_reports": True},
)


def run_detector(name: str, root: Path) -> list[Observation]:
    for dn, fn in DETECTORS:
        if dn == name:
            return fn(root)
    raise KeyError(name)


def discover_all(root: Path) -> list[Observation]:
    """Run every detector; return observations in a canonical, deterministic
    order (by kind, canonical_name, detector) so repeated runs are bit-stable."""
    obs: list[Observation] = []
    for _, fn in DETECTORS:
        obs.extend(fn(root))
    obs.sort(key=lambda o: (o.surface_kind, o.canonical_name, o.detector,
                            o.evidence_path, o.evidence_line))
    # every observation kind must be a declared surface kind
    for o in obs:
        assert o.surface_kind in SURFACE_KINDS, o.surface_kind
    return obs


def observations_by_surface(obs: Iterable[Observation]) -> dict:
    """Group observations by surface_id (the union step before reconciliation)."""
    grouped: dict[str, list[Observation]] = {}
    for o in obs:
        grouped.setdefault(o.surface_id, []).append(o)
    return grouped

"""SP0005 baseline & isolation invariants.

Covers AC-0005-001..008 (kernel deterministic, stdlib-only, not imported by
product, no product behavior change, no DB migration) and AC-0005-217..239
(the assembled real safety program validates P0=0/P1=0, is deterministic, and the
committed artifacts equal a fresh deterministic bootstrap).
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

import pytest

from tools.safety.loader import load_program, DOCS, REPO_ROOT
from tools.safety.validate import validate_all
from tools.safety import bootstrap
from tools.safety.canon import canonical_json, core_hash

SAFETY_DIR = os.path.join(REPO_ROOT, "tools", "safety")


def _k(rep):
    return {f.kind for f in rep.findings}


# ---- kernel is stdlib-only & self-contained (AC-0005-001/002) --------------
_STDLIB_OK = {
    "json", "os", "sys", "hashlib", "ast", "subprocess", "argparse", "itertools",
    "dataclasses", "typing", "collections", "functools", "datetime", "re",
    "__future__", "math", "copy", "enum", "textwrap",
}


def _module_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import inside the package — fine
                continue
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def test_kernel_is_stdlib_only():
    for fn in os.listdir(SAFETY_DIR):
        if not fn.endswith(".py"):
            continue
        src = open(os.path.join(SAFETY_DIR, fn), encoding="utf-8").read()
        for name in _module_names(ast.parse(src)):
            assert name in _STDLIB_OK, f"{fn} imports non-stdlib '{name}'"


def test_kernel_does_not_import_product_code():
    for fn in os.listdir(SAFETY_DIR):
        if not fn.endswith(".py"):
            continue
        src = open(os.path.join(SAFETY_DIR, fn), encoding="utf-8").read()
        assert "finalis" not in _module_names(ast.parse(src)), \
            f"{fn} imports product package 'finalis'"


# ---- product code does NOT import the kernel (AC-0005-003, INV-0005-27) -----
def test_product_code_never_imports_safety_tooling():
    hits = []
    for root, _dirs, files in os.walk(os.path.join(REPO_ROOT, "finalis")):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            src = open(os.path.join(root, fn), encoding="utf-8").read()
            if "tools.safety" in src or "from tools import safety" in src:
                hits.append(os.path.join(root, fn))
    assert hits == [], f"product code imports safety tooling: {hits}"


def test_safety_tests_are_the_only_referrers():
    # importing tools.safety must not drag in any product module
    before = set(sys.modules)
    import tools.safety.validate  # noqa: F401
    import tools.safety.cli  # noqa: F401
    leaked = {m for m in set(sys.modules) - before if m.startswith("finalis")}
    assert leaked == set(), f"safety tooling pulled in product modules: {leaked}"


# ---- no DB migration added (AC-0005-004, stays v27) ------------------------
def test_migration_version_unchanged():
    from finalis.portal.db import MIGRATIONS
    assert max(v for v, _ in MIGRATIONS) == 27
    assert len(MIGRATIONS) == 27


# ---- assembled real program validates clean (AC-0005-217..224) -------------
def test_real_program_validates_p0_p1_zero():
    rep = validate_all(load_program())
    assert rep.counts()["P0"] == 0, [f.__dict__ for f in rep.findings]
    assert rep.counts()["P1"] == 0, [f.__dict__ for f in rep.findings]
    assert rep.valid


def test_real_program_is_populated():
    prog = load_program()
    assert len(prog["losses"]) >= 5
    assert len(prog["hazards"]) >= 5
    assert len(prog["controls"]) >= 5
    assert len(prog["sources"]) >= 10
    # every ACTIVE critical hazard already traced (validate proved P0=0)


# ---- deterministic validation (AC-0005-005, 225/226) -----------------------
def test_validation_is_deterministic():
    r1 = validate_all(load_program())
    r2 = validate_all(load_program())
    assert _k(r1) == _k(r2)
    assert r1.counts() == r2.counts()


def test_canonical_hash_is_stable_and_order_independent():
    a = {"b": 1, "a": [3, 2, 1], "c": {"y": 2, "x": 1}}
    b = {"c": {"x": 1, "y": 2}, "a": [3, 2, 1], "b": 1}
    assert canonical_json(a) == canonical_json(b)
    assert core_hash(a) == core_hash(b)


# ---- artifacts equal a fresh deterministic bootstrap (AC-0005-227..233) -----
def test_committed_artifacts_equal_fresh_bootstrap(tmp_path):
    out = str(tmp_path)
    bootstrap.write(out)
    for fn in os.listdir(out):
        fresh = json.load(open(os.path.join(out, fn), encoding="utf-8"))
        committed_path = os.path.join(DOCS, fn)
        assert os.path.exists(committed_path), f"missing committed artifact {fn}"
        committed = json.load(open(committed_path, encoding="utf-8"))
        assert canonical_json(fresh) == canonical_json(committed), \
            f"committed {fn} drifted from deterministic bootstrap"


def test_bootstrap_is_idempotent(tmp_path):
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    os.makedirs(a)
    os.makedirs(b)
    bootstrap.write(a)
    bootstrap.write(b)
    for fn in os.listdir(a):
        assert open(os.path.join(a, fn)).read() == open(os.path.join(b, fn)).read()


# ---- CLI surface exits 0 on the real program (AC-0005-234..239) ------------
@pytest.mark.parametrize("sub", [
    "inventory", "hazards", "regulatory-status", "scenarios", "assurance",
    "drift", "attest", "validate",
])
def test_cli_subcommands_exit_zero(sub):
    r = subprocess.run([sys.executable, "-m", "tools.safety", sub],
                       cwd=REPO_ROOT, capture_output=True, text=True)
    assert r.returncode == 0, f"{sub} exited {r.returncode}: {r.stderr[-500:]}"
    # every subcommand emits JSON (evidence, not prose)
    json.loads(r.stdout)

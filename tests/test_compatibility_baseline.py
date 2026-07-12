"""SP0007 baseline, isolation & roadmap invariants.

Covers AC-0007-001..020 (roadmap identity + baseline) and the constitutional
boundary: deterministic, stdlib-only, product-isolated, no DB migration, no live
migration, the real Compatibility Twin validates P0=0/P1=0, committed artifacts
equal a fresh deterministic bootstrap, and the CLI attests as evidence.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

import pytest

from tools.compatibility.loader import load_program, DOCS, REPO_ROOT
from tools.compatibility.validate import validate_all
from tools.compatibility import bootstrap
from tools.compatibility.canon import canonical_json, core_hash

CD = os.path.join(REPO_ROOT, "tools", "compatibility")

_STDLIB_OK = {
    "json", "os", "sys", "hashlib", "ast", "subprocess", "argparse", "itertools",
    "dataclasses", "typing", "collections", "functools", "datetime", "re",
    "__future__", "math", "copy", "enum", "textwrap", "heapq",
}


def _k(rep):
    return {f.kind for f in rep.findings}


def _module_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if node.module:
                names.add(node.module.split(".")[0])
    return names


# ---- stdlib-only + no product import (INV-0007-47/48) ----------------------
def test_kernel_is_stdlib_only():
    for fn in os.listdir(CD):
        if not fn.endswith(".py"):
            continue
        src = open(os.path.join(CD, fn), encoding="utf-8").read()
        for name in _module_names(ast.parse(src)):
            assert name in _STDLIB_OK, f"{fn} imports non-stdlib {name!r}"


def test_kernel_does_not_import_product_code():
    for fn in os.listdir(CD):
        if not fn.endswith(".py"):
            continue
        src = open(os.path.join(CD, fn), encoding="utf-8").read()
        assert "finalis" not in _module_names(ast.parse(src)), \
            f"{fn} imports product package finalis"


def test_product_never_imports_compatibility():
    hits = []
    for root, _d, files in os.walk(os.path.join(REPO_ROOT, "finalis")):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            src = open(os.path.join(root, fn), encoding="utf-8").read()
            if "tools.compatibility" in src \
                    or "from tools import compatibility" in src:
                hits.append(os.path.join(root, fn))
    assert hits == [], f"product imports compatibility: {hits}"


def test_importing_kernel_pulls_no_product_module():
    before = set(sys.modules)
    import tools.compatibility.validate  # noqa: F401
    import tools.compatibility.cli  # noqa: F401
    leaked = {m for m in set(sys.modules) - before if m.startswith("finalis")}
    assert leaked == set(), f"kernel pulled in product modules: {leaked}"


# ---- no DB migration / migration frontier unchanged (AC-0007-012, INV-49) --
def test_migration_frontier_unchanged():
    from finalis.portal.db import MIGRATIONS
    assert max(v for v, _ in MIGRATIONS) == 27
    assert len(MIGRATIONS) == 27


# ---- roadmap identity (AC-0007-001..005) -----------------------------------
def test_roadmap_identity_report_exists():
    path = os.path.join(DOCS, "SP0007_ROADMAP_IDENTITY_REPORT.md")
    assert os.path.exists(path)
    txt = open(path, encoding="utf-8").read()
    assert "Compatibility" in txt and "SP0011" in txt


def test_evaluation_not_implemented_as_sp0007():
    # the Evaluation charter is at SP0011 (SP0006 reassignment), never SP0007
    reg = json.load(open(os.path.join(REPO_ROOT, "docs", "program",
                                      "FINALIS_1000_PROGRAM_REGISTRY.json")))
    by = {n["node_id"]: n["canonical_name"] for n in reg["nodes"]}
    assert "Compatibility" in by["SP0007"]
    assert "Evaluation" in by["SP0011"]
    assert "Evaluation" not in by["SP0007"]


def test_predecessor_chain_present():
    reg = json.load(open(os.path.join(REPO_ROOT, "docs", "program",
                                      "FINALIS_1000_PROGRAM_REGISTRY.json")))
    ids = {n["node_id"] for n in reg["nodes"]}
    for sp in ("SP0000", "SP0001", "SP0002", "SP0003", "SP0004", "SP0005",
               "SP0006", "SP0007"):
        assert sp in ids


# ---- real program validates clean ------------------------------------------
def test_real_program_validates_p0_p1_zero():
    rep = validate_all(load_program())
    assert rep.counts()["P0"] == 0, [f.to_dict() for f in rep.findings]
    assert rep.counts()["P1"] == 0, [f.to_dict() for f in rep.findings]
    assert rep.valid


def test_real_program_is_populated():
    p = load_program()
    assert len(p["descriptors"]) >= 8
    assert len(p["versions"]) >= 8
    assert len(p["claims"]) >= 3
    assert len(p["fixtures"]) >= 5
    assert len(p["migration_edges"]) >= 1


# ---- determinism -----------------------------------------------------------
def test_validation_is_deterministic():
    r1 = validate_all(load_program())
    r2 = validate_all(load_program())
    assert _k(r1) == _k(r2) and r1.counts() == r2.counts()


def test_canonical_hash_order_independent():
    a = {"b": 1, "a": [3, 2, 1], "c": {"y": 2, "x": 1}}
    b = {"c": {"x": 1, "y": 2}, "a": [3, 2, 1], "b": 1}
    assert canonical_json(a) == canonical_json(b)
    assert core_hash(a) == core_hash(b)


# ---- committed artifacts equal a fresh deterministic bootstrap -------------
def test_committed_artifacts_equal_fresh_bootstrap(tmp_path):
    out = str(tmp_path)
    bootstrap.write(out)
    for fn in os.listdir(out):
        fresh = json.load(open(os.path.join(out, fn), encoding="utf-8"))
        committed_path = os.path.join(DOCS, fn)
        assert os.path.exists(committed_path), f"missing committed {fn}"
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


# ---- CLI surface exits 0 + emits JSON (AC-0007 §15) ------------------------
@pytest.mark.parametrize("sub", [
    "roadmap-identity", "inventory", "validate", "modelcheck", "fitness",
    "observatory", "attest",
])
def test_cli_subcommands_exit_zero(sub):
    r = subprocess.run([sys.executable, "-m", "tools.compatibility", sub],
                       cwd=REPO_ROOT, capture_output=True, text=True)
    assert r.returncode == 0, f"{sub} exited {r.returncode}: {r.stderr[-400:]}"
    json.loads(r.stdout)

"""SP0006 baseline, isolation & roadmap invariants.

Covers AC-0006-001..020 (roadmap identity + baseline) and the constitutional
boundary: deterministic, stdlib-only, product-isolated, no DB migration, the real
bootstrapped program validates P0=0/P1=0, committed artifacts equal a fresh
deterministic bootstrap, and the CLI attests as evidence.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

import pytest

from tools.governed_work.loader import load_program, DOCS, REPO_ROOT
from tools.governed_work.validate import validate_all
from tools.governed_work import bootstrap
from tools.governed_work.canon import canonical_json, core_hash

GW_DIR = os.path.join(REPO_ROOT, "tools", "governed_work")

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


# ---- stdlib-only + no product import (AC-0006-001/002, INV-0006-17) --------
def test_kernel_is_stdlib_only():
    for fn in os.listdir(GW_DIR):
        if not fn.endswith(".py"):
            continue
        src = open(os.path.join(GW_DIR, fn), encoding="utf-8").read()
        for name in _module_names(ast.parse(src)):
            assert name in _STDLIB_OK, f"{fn} imports non-stdlib {name!r}"


def test_kernel_does_not_import_product_code():
    for fn in os.listdir(GW_DIR):
        if not fn.endswith(".py"):
            continue
        src = open(os.path.join(GW_DIR, fn), encoding="utf-8").read()
        assert "finalis" not in _module_names(ast.parse(src)), \
            f"{fn} imports product package finalis"


# ---- product code never imports the kernel (INV-0006-46) -------------------
def test_product_never_imports_governed_work():
    hits = []
    for root, _d, files in os.walk(os.path.join(REPO_ROOT, "finalis")):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            src = open(os.path.join(root, fn), encoding="utf-8").read()
            if "tools.governed_work" in src or "from tools import governed_work" in src:
                hits.append(os.path.join(root, fn))
    assert hits == [], f"product imports governed_work: {hits}"


def test_importing_kernel_pulls_no_product_module():
    before = set(sys.modules)
    import tools.governed_work.validate  # noqa: F401
    import tools.governed_work.cli  # noqa: F401
    leaked = {m for m in set(sys.modules) - before if m.startswith("finalis")}
    assert leaked == set(), f"kernel pulled in product modules: {leaked}"


# ---- no DB migration added (AC-0006-010, INV-0006-48, stays v27) -----------
def test_migration_version_unchanged():
    from finalis.portal.db import MIGRATIONS
    assert max(v for v, _ in MIGRATIONS) == 27
    assert len(MIGRATIONS) == 27


# ---- roadmap identity (AC-0006-001..005) -----------------------------------
def test_roadmap_identity_report_exists_and_names_sp0006():
    path = os.path.join(DOCS, "SP0006_ROADMAP_IDENTITY_REPORT.md")
    assert os.path.exists(path)
    txt = open(path, encoding="utf-8").read()
    assert "Governed Work" in txt and "SP0011" in txt


def test_program_twin_records_sp0006_as_governed_work():
    reg = json.load(open(os.path.join(REPO_ROOT, "docs", "program",
                                      "FINALIS_1000_PROGRAM_REGISTRY.json")))
    by_id = {n["node_id"]: n for n in reg["nodes"]}
    assert "Governed Work" in by_id["SP0006"]["canonical_name"]
    assert by_id["SP0011"]["canonical_name"] == "Evaluation and 1000/1000 Score Charter"


def test_predecessor_chain_present():
    reg = json.load(open(os.path.join(REPO_ROOT, "docs", "program",
                                      "FINALIS_1000_PROGRAM_REGISTRY.json")))
    ids = {n["node_id"] for n in reg["nodes"]}
    for sp in ("SP0000", "SP0001", "SP0002", "SP0003", "SP0004", "SP0005",
               "SP0006"):
        assert sp in ids


# ---- real program validates clean (AC-0006 admission/validity) -------------
def test_real_program_validates_p0_p1_zero():
    rep = validate_all(load_program())
    assert rep.counts()["P0"] == 0, [f.to_dict() for f in rep.findings]
    assert rep.counts()["P1"] == 0, [f.to_dict() for f in rep.findings]
    assert rep.valid


def test_real_program_is_populated():
    p = load_program()
    assert len(p["work_orders"]) >= 1
    assert len(p["leases"]) >= 3
    assert len(p["delegation_edges"]) >= 2
    assert len(p["execution_identities"]) >= 3


# ---- deterministic validation + hashing ------------------------------------
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


# ---- CLI surface exits 0 + emits JSON (AC-0006 §15) ------------------------
@pytest.mark.parametrize("sub", [
    "roadmap-identity", "inventory", "validate", "modelcheck", "attest",
])
def test_cli_subcommands_exit_zero(sub):
    r = subprocess.run([sys.executable, "-m", "tools.governed_work", sub],
                       cwd=REPO_ROOT, capture_output=True, text=True)
    assert r.returncode == 0, f"{sub} exited {r.returncode}: {r.stderr[-400:]}"
    json.loads(r.stdout)

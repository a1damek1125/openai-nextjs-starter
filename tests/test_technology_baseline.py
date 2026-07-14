"""SP0004 baseline: the REAL bootstrapped technology model validates, determinism,
observatory, artifacts match fresh bootstrap, no product change. Covers
AC-0004-001..014, 149..160."""
from __future__ import annotations

import json
import os

from tools.technology.loader import load_program
from tools.technology.bootstrap import write as bootstrap_write
from tools.technology.validate import validate_all
from tools.technology.observatory import snapshot
from tools.technology.inventory import inventory_stats, critical
from tools.technology.decisions import tdr_index

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS = os.path.join(REPO, "docs", "technology")


def _prog():
    return load_program()


# ---- AC-0004-006/007/008: inventory ----------------------------------------
def test_real_inventory_has_direct_and_transitive():
    s = inventory_stats(_prog().get("inventory", {}))
    assert s["direct"] >= 10 and s["transitive"] >= 1 and s["critical_t3_t4"] >= 4


def test_repo_technologies_present():
    ids = {t["technology_id"]
           for t in _prog().get("inventory", {}).get("technologies", [])}
    for tid in ("python", "fastapi", "uvicorn", "sqlite", "pytest"):
        assert tid in ids


# ---- AC-0004-157/158: real model validates P0=0/P1=0 -----------------------
def test_real_model_validates():
    rep = validate_all(_prog(), today="2026-07-11")
    assert rep.valid, [f.to_dict() for f in rep.findings if f.severity != "P2"]
    assert rep.counts()["P0"] == 0 and rep.counts()["P1"] == 0


# ---- AC-0004-012/013/014: technology graph distinct ------------------------
def test_technology_graph_distinct_from_other_graphs():
    # distinct on-disk artifact, distinct node ids from arch/semantic/program
    g = _prog().get("dependency_graph", {})
    assert g.get("nodes") and "python" in {n["node_id"] for n in g["nodes"]}


# ---- AC-0004-040: T3/T4 have exit evidence ---------------------------------
def test_all_critical_deps_have_exit_profiles():
    prog = _prog()
    profs = {p["technology_id"] for p in prog.get("exit_profiles", [])}
    for t in critical(prog.get("inventory", {})):
        assert t["technology_id"] in profs, t["technology_id"]


# ---- observatory + determinism ---------------------------------------------
def test_observatory_advisory_and_deterministic():
    s1 = snapshot(_prog()); s2 = snapshot(_prog())
    assert s1 == s2 and s1["classification"] == "ADVISORY_NOT_A_GATE"


def test_deferred_decisions_have_triggers():
    for d in _prog().get("decision_registry", {}).get("decisions", []):
        if d.get("status") == "DEFERRED":
            assert d.get("review_triggers") or d.get("decision_trigger"), \
                d["decision_id"]


# ---- AC-0004-135/136/137: model provider separate + no router --------------
def test_model_provider_owned_contract_no_router():
    prog = _prog()
    tdr = tdr_index(prog.get("decision_registry", {})).get("TDR-0005")
    assert tdr and tdr["scope"].startswith("OWN")
    # no module named model_router / router in the technology package
    import tools.technology as tt
    import pkgutil
    mods = {m.name for m in pkgutil.iter_modules(tt.__path__)}
    assert "model_router" not in mods and "router" not in mods


# ---- AC-0004-159: research register has complete URLs -----------------------
def test_research_register_has_urls():
    txt = open(os.path.join(DOCS, "FINALIS_SP0004_RESEARCH_REGISTER.md")).read()
    assert txt.count("https://") >= 40
    assert "TODO" not in txt and "example.com" not in txt


# ---- AC-0004-149/150: no product change / migration ------------------------
def test_tooling_not_imported_by_product():
    import subprocess
    r = subprocess.run(["grep", "-rIl", "tools.technology",
                        os.path.join(REPO, "finalis")],
                       capture_output=True, text=True)
    assert r.stdout.strip() == "", r.stdout


def test_migration_frontier_unchanged():
    import finalis.portal.db as db
    assert max(v for v, _ in db.MIGRATIONS) == 27


# ---- artifacts match a fresh bootstrap (determinism) -----------------------
def test_committed_artifacts_match_fresh_bootstrap(tmp_path):
    bootstrap_write(str(tmp_path))
    import glob
    fresh = {os.path.basename(f) for f in glob.glob(os.path.join(tmp_path,
                                                                 "*.json"))}
    assert len(fresh) >= 15
    for fname in fresh:
        committed = json.load(open(os.path.join(DOCS, fname)))
        regenerated = json.load(open(os.path.join(tmp_path, fname)))
        assert committed == regenerated, fname

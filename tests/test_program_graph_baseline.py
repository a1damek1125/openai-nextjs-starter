"""SP0003 baseline: the REAL bootstrapped program validates, twin/drift/envelope
determinism, twin separation, artifacts match a fresh recompute, no product
change. Covers AC-0003-01..08, 78..87, 91..98, 103/104."""
from __future__ import annotations

import json
import os

from tools.program_graph.loader import load_program_bundle
from tools.program_graph.bootstrap import build_program, write_artifacts
from tools.program_graph.validate import validate_program
from tools.program_graph.registry import registry_hash
from tools.program_graph.twin import build_twin
from tools.program_graph.drift import snapshot_vector
from tools.program_graph.envelope import build_envelope
from tools.program_graph.hypergraph import (hyperedge_arity_stats,
                                            alternative_groups)
from tools.program_graph.scenario import compile_scenario

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS = os.path.join(REPO, "docs", "program")


def _prog():
    return load_program_bundle()


# ---- AC-0003-01/02/03: preconditions ---------------------------------------
def test_sp0_layer_present_and_complete():
    p = _prog()
    ids = {n["node_id"]: n for n in p["nodes"]}
    for sp in ("SP0000", "SP0001", "SP0002"):
        assert ids[sp]["status"] == "COMPLETE"
    assert ids["SP0003"]["status"] == "IN_PROGRESS"


# ---- AC-0003-05/06/07: registry, all nodes, no renumbering -----------------
def test_real_program_valid():
    rep = validate_program(_prog(), "BASELINE")
    assert rep.valid, [f.to_dict() for f in rep.findings if f.severity != "P2"]
    assert rep.counts()["P0"] == 0 and rep.counts()["P1"] == 0


def test_historical_ids_present_unrenamed():
    ids = {n["node_id"] for n in _prog()["nodes"]}
    for hid in ("CORE-A1", "TOOL-B9", "TOOL-B9.2", "EMP-A1"):
        assert hid in ids


def test_node_count_reasonable():
    assert len(_prog()["nodes"]) >= 80


# ---- AC-0003-08: typed hypergraph ------------------------------------------
def test_hypergraph_typed_and_has_alternatives_and_threshold():
    p = _prog()
    active, _ = compile_scenario(p, "BASELINE")
    groups = alternative_groups(p, active)
    assert "MESSAGING_PILOT_READY" in groups   # OR alternatives
    assert "VERTICAL_COVERAGE" in groups        # threshold
    assert hyperedge_arity_stats(p)["max_arity"] >= 4


# ---- AC-0003-17/18: scenarios all validate ---------------------------------
def test_all_scenarios_validate():
    p = _prog()
    for s in p["scenarios"]:
        rep = validate_program(p, s["scenario_id"])
        assert rep.valid, s["scenario_id"]


# ---- AC-0003-82/83/84: twin + separation -----------------------------------
def test_twin_distinct_from_other_twins():
    t = build_twin(_prog())
    assert t["twin_kind"] == "PROGRAM_DIGITAL_TWIN"
    assert "ARCHITECTURE_DIGITAL_TWIN" in t["distinct_from"]
    assert "SEMANTIC_DOMAIN_TWIN" in t["distinct_from"]


def test_twin_deterministic():
    assert build_twin(_prog()) == build_twin(_prog())


# ---- AC-0003-85/86/87: canonical vs derived + drift ------------------------
def test_drift_snapshot_advisory():
    dv = snapshot_vector(_prog())
    assert dv["classification"] == "ADVISORY_NOT_A_GATE"
    assert dv["node_count"] >= 80


# ---- AC-0003-91..96: proof envelope ----------------------------------------
def test_envelope_deterministic():
    p = _prog()
    assert build_envelope(p)["envelope_hash"] == build_envelope(p)["envelope_hash"]
    assert build_envelope(p)["classification"] == "EVIDENCE_NOT_AUTHORITY"


def test_envelope_changes_on_hypergraph_change():
    p = _prog()
    h0 = build_envelope(p)["envelope_hash"]
    p2 = json.loads(json.dumps(p))
    p2["hyperedges"].append({"dependency_id": "zzz", "tail_nodes": ["SP0000"],
                             "head_node": "SP0001", "logic": "ALL_OF",
                             "status": "ACTIVE"})
    assert build_envelope(p2)["envelope_hash"] != h0


def test_envelope_changes_on_scenario_change():
    p = _prog()
    h0 = build_envelope(p, scenario_id="BASELINE")["envelope_hash"]
    hT = build_envelope(p, scenario_id="TEMPORAL_RUNTIME_OPTION")["envelope_hash"]
    assert h0 != hT


def test_envelope_changes_on_completion_evidence_change():
    p = _prog()
    h0 = build_envelope(p)["envelope_hash"]
    p2 = json.loads(json.dumps(p))
    p2["completion_evidence"].append({"node_id": "SP0003", "kind": "final_commit",
                                      "ref": "deadbeef"})
    assert build_envelope(p2)["envelope_hash"] != h0


def test_registry_hash_deterministic():
    assert registry_hash(_prog()) == registry_hash(_prog())


# ---- AC-0003-81: committed artifacts match a fresh recompute ----------------
def test_committed_artifacts_match_fresh_bootstrap(tmp_path):
    fresh = build_program()
    write_artifacts(fresh, str(tmp_path))
    from tools.program_graph.bootstrap import write_artifacts as _wa  # noqa
    import glob
    # every canonical JSON artifact must match a fresh recompute exactly
    fresh_files = {os.path.basename(f)
                   for f in glob.glob(os.path.join(tmp_path, "*.json"))}
    assert len(fresh_files) >= 9
    for fname in fresh_files:
        committed = json.load(open(os.path.join(DOCS, fname)))
        regenerated = json.load(open(os.path.join(tmp_path, fname)))
        assert committed == regenerated, fname


# ---- AC-0003-97/98: no product change / migration --------------------------
def test_tooling_not_imported_by_product():
    import subprocess
    r = subprocess.run(
        ["grep", "-rIl", "program_graph",
         os.path.join(REPO, "finalis"), os.path.join(REPO, "app.py")],
        capture_output=True, text=True)
    assert r.stdout.strip() == "", f"product imports program_graph: {r.stdout}"


def test_migration_frontier_unchanged():
    import finalis.portal.db as db
    assert max(v for v, _ in db.MIGRATIONS) == 27

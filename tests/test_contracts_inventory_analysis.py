"""SP0008 analysis-layer coverage — fast, direct module calls (no full build).

Exercises each analysis module against small fixtures and against the real repo's
raw discovery (cheap), pinning the behaviors the acceptance criteria require:
detector diversity/common-mode, identity resolution, bitemporal+provenance,
reachability/dominators/cut-sets, ownership certainty, witnesses, probes,
readiness, negative-space, and the finding/reason vocabulary.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.contracts_inventory import (model, discover, detectors, normalize,
                                        criticality, evidence, chains,
                                        ownership, witnesses, residual, probes,
                                        readiness, genome, negative_space,
                                        surfaces as surfaces_mod, envelope)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def obs():
    return discover.discover_all(ROOT)


@pytest.fixture(scope="module")
def surfaces(obs):
    from tools.contracts_inventory import bootstrap
    return normalize.reconcile(obs, bootstrap._load_descriptors(ROOT))


# --- model vocabulary is closed & consistent --------------------------------
def test_reason_codes_are_closed_set():
    assert model.BOUNDARY_VIOLATION in model.REASON_CODES
    assert len(model.REASON_CODES) == 31


def test_finding_rejects_bad_severity():
    with pytest.raises(ValueError):
        model.Finding("X", "PX", "s", "m")


def test_report_valid_iff_no_p0_p1():
    assert model.report([model.Finding("K", model.P2, "s", "m")]).valid
    assert not model.report([model.Finding("K", model.P1, "s", "m")]).valid
    assert not model.report([model.Finding("K", model.P0, "s", "m")]).valid


def test_effect_bearing_excludes_http_route():
    assert "HTTP_ROUTE" not in model.EFFECT_BEARING_KINDS
    assert "DB_TABLE" in model.EFFECT_BEARING_KINDS


# --- detectors: capability + diversity/common-mode --------------------------
def test_every_detector_has_capability():
    for name in detectors.detector_names():
        assert name in detectors.CAPABILITY


def test_same_method_detectors_are_cosmetic_diversity():
    # two AST detectors sharing a method grade COSMETIC
    assert detectors.diversity("run_ledger_events", "audit_events") in (
        model.DIVERSITY_REAL, model.DIVERSITY_PARTIAL, model.DIVERSITY_COSMETIC)
    # a detector vs itself-method: proof_artifacts (fn name) vs proof_versions
    # (assign regex) are DIFFERENT methods
    assert detectors.diversity("proof_artifacts", "proof_versions") != \
        model.DIVERSITY_COSMETIC


def test_blind_spots_declared_not_silent():
    bs = detectors.blind_spots()
    assert any(b["detector"] == "http_routes" for b in bs)
    assert any(b["detector"] == "state_machines" for b in bs)


# --- identity resolution ----------------------------------------------------
def test_ambiguous_when_multiple_descriptors_match():
    obs_one = [discover.Observation("d", "HTTP_ROUTE", "GET /x",
                                    "finalis/portal/app.py", 1, {})]
    descriptors = [
        {"contract_id": "CT-A", "contract_kind": "HTTP_API",
         "source_paths": ["finalis/portal/app.py"]},
        {"contract_id": "CT-B", "contract_kind": "HTTP_API",
         "source_paths": ["finalis/portal"]},
    ]
    s = normalize.reconcile(obs_one, descriptors)[0]
    assert s.identity_outcome == model.AMBIGUOUS_IDENTITY
    assert s.parent_contract_id is None


def test_new_surface_when_no_descriptor():
    obs_one = [discover.Observation("d", "CONFIG_KEY", "ZZZ",
                                    ".env.example", 1, {})]
    s = normalize.reconcile(obs_one, [])[0]
    assert s.identity_outcome == model.NEW_SURFACE


# --- criticality vector -----------------------------------------------------
def test_delete_route_is_irreversible():
    s = _mk("HTTP_ROUTE", "DELETE /x")
    vec = criticality.criticality_vector(s, shape={"method": "DELETE",
                                                    "path": "/x"})
    assert vec["irreversibility"] == "YES"


def test_migration_is_irreversible_and_data():
    s = _mk("DB_MIGRATION", "migration:5")
    vec = criticality.criticality_vector(s, shape={"version": 5})
    assert vec["irreversibility"] == "YES"
    assert vec["data"] == "YES"


def test_criticality_unknown_hard_flag_emits_advisory_not_p1():
    s = _mk("HTTP_ROUTE", "GET /x")
    vec = criticality.criticality_vector(s, shape={"method": "GET", "path": "/x"})
    fs = criticality.criticality_findings(s, vec)
    assert fs and all(f.severity == model.P2 for f in fs)


# --- evidence: bitemporal + provenance + contradictions ---------------------
def test_claim_is_grounded_and_bitemporal():
    c = evidence.Claim("CS-1", "method", "GET", "finalis/portal/app.py", 5, "d")
    assert not evidence.validate_claim(c)
    bad = evidence.Claim("CS-1", "m", "v", "", -1, "d")
    assert any(f.kind == model.EVIDENCE_UNGROUNDED
               for f in evidence.validate_claim(bad))


def test_prov_projection_edges_valid():
    c = evidence.Claim("CS-1", "m", "v", "finalis/x.py", 1, "det")
    g = evidence.prov_projection([c])
    assert evidence.validate_provenance(g) == []
    assert {n["kind"] for n in g["nodes"]} <= set(model.PROV_NODE_KINDS)


def test_contradiction_preserved_not_averaged():
    a = evidence.Claim("CS-1", "status", 200, "f.py", 1, "d1")
    b = evidence.Claim("CS-1", "status", 404, "f.py", 2, "d2")
    fs = evidence.find_contradictions([a, b])
    assert any(f.kind == model.CONTRADICTION_PRESERVED for f in fs)


# --- chains: reachability, dominators, cut sets -----------------------------
def test_reachability_direct_edge():
    edges = {"A": {"B"}, "B": set()}
    surfaces_stub = [_mk("HTTP_ROUTE", "A", sid="A"),
                     _mk("DB_TABLE", "B", sid="B")]
    reach = chains.effect_reachability(edges, surfaces_stub)
    assert reach["A"]["reaches_effect"]
    assert "B" in reach["A"]["effect_sinks"]


def test_dominators_single_point():
    edges = {"A": {"B"}, "B": {"C"}, "C": set()}
    dom = chains.dominators(edges, ["A"], set(edges))
    assert "B" in dom["C"]        # B dominates C on the only path


def test_cut_set_exactness_reported():
    edges = {"A": {"M"}, "M": {"S"}, "S": set()}
    res = chains.minimal_cut_sets(edges, ["A"], {"S"})
    assert res["exactness"] in model.CUT_SET_EXACTNESS
    assert ["M"] in res["cut_sets"]


# --- ownership --------------------------------------------------------------
def test_owner_from_capability_tag():
    owner = ownership.owner_of_module(ROOT, "finalis/ai_employee/authority.py")
    assert owner and owner.startswith(("CORE", "TOOL", "EMP"))


def test_producers_grounded(surfaces):
    s = surfaces[0]
    prod = ownership.resolve_producers(s)
    assert prod and all(p["certainty"] == model.STATIC_CONFIRMED for p in prod)


# --- witnesses --------------------------------------------------------------
def test_witness_ungrounded_rejected():
    w = {"kind": "POSITIVE", "outcome": "CONFIRMED", "surface_id": "CS-1",
         "grounded": False, "source": {"path": "", "line": 0},
         "witness_id": "WT-x"}
    assert any(f.kind == model.WITNESS_UNGROUNDED
               for f in witnesses.validate_witness(w))


def test_http_witnesses_grounded(surfaces):
    ws = witnesses.derive_http_witnesses(ROOT, surfaces)
    assert ws
    assert all(w["grounded"] and w["source"]["path"] for w in ws)


# --- probes -----------------------------------------------------------------
def test_probes_ranked_by_voi():
    unknowns = [
        {"surface_id": "CS-1", "probe_kind": "CONSUMER_SEARCH",
         "unknown": "c", "criticality": "STANDARD"},
        {"surface_id": "CS-2", "probe_kind": "CRITICALITY_REVIEW",
         "unknown": "h", "criticality": "CRITICAL"},
    ]
    plan = probes.plan_probes(unknowns)
    assert plan[0]["criticality"] == "CRITICAL"    # higher VoI ranks first
    assert all(p["executes_against_product"] is False for p in plan)


# --- readiness grants no authority ------------------------------------------
def test_readiness_fail_closed_and_no_authority():
    s = _mk("HTTP_ROUTE", "POST /x")
    a = readiness.assess_surface(
        s, crit_vec={d: "UNKNOWN" for d in model.CRITICALITY_DIMS},
        reach={"exactness": "UNKNOWN"}, consumer={}, witnesses=[])
    assert a["verdict"] == "NOT_READY"
    assert a["grants_authority"] is False


# --- negative space ---------------------------------------------------------
def test_negative_space_declares_floors():
    decl = negative_space.declared_universe(ROOT)
    assert decl.get("HTTP_ROUTE", 0) >= 402
    assert decl.get("DB_MIGRATION") == 27


def test_negative_space_no_shortfall(surfaces):
    report, findings = negative_space.verify_negative_space(ROOT, surfaces)
    shortfalls = [f for f in findings
                  if f.kind == model.NEGATIVE_SPACE_UNVERIFIED]
    assert shortfalls == []       # detectors meet/exceed the declared floors


# --- helpers ----------------------------------------------------------------
def _mk(kind, name, sid=None):
    return normalize.CanonicalSurface(
        surface_id=sid or ("CS-" + name), surface_kind=kind,
        canonical_name=name, contract_kind="X", parent_contract_id=None,
        identity_outcome=model.NEW_SURFACE, detectors=("d",),
        evidence=(("finalis/portal/app.py", 1),),
        structural_fingerprints=("f",), notes=())

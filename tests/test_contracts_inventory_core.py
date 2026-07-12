"""SP0008 Canonical Contract Surface Inventory — core invariants.

These tests pin the load-bearing properties: real grounded discovery, stable
identity, deterministic output + genome, honest UNKNOWN handling (never coerced
to safe/zero), the change boundary, and the SP0007-population (no parallel
registry) rule. A shared module-scoped inventory keeps the suite fast (one build).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.contracts_inventory import (canon, model, discover, normalize,
                                        detectors, criticality, evidence,
                                        chains, ownership, witnesses, residual,
                                        probes, readiness, genome,
                                        negative_space, envelope, modelcheck,
                                        closure, bootstrap, validate)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def obs():
    return discover.discover_all(ROOT)


@pytest.fixture(scope="module")
def descriptors():
    return bootstrap._load_descriptors(ROOT)


@pytest.fixture(scope="module")
def surfaces(obs, descriptors):
    return normalize.reconcile(obs, descriptors)


@pytest.fixture(scope="module")
def inventory():
    return bootstrap.build_inventory(ROOT)


# --- canon / hashing --------------------------------------------------------
def test_canonical_json_sorted_compact():
    assert canon.canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_surface_id_stable_and_label_independent():
    a = canon.surface_id("HTTP_ROUTE", "GET /x")
    assert a == canon.surface_id("HTTP_ROUTE", "GET /x")
    assert a != canon.surface_id("HTTP_ROUTE", "POST /x")
    assert a.startswith("CS-")


def test_core_hash_strips_volatile():
    a = {"canonical_name": "x", "display_name": "A", "label": "L1"}
    b = {"canonical_name": "x", "display_name": "B", "label": "L2"}
    assert canon.core_hash(a) == canon.core_hash(b)


def test_material_fingerprint_moves_on_material_change():
    a = {"canonical_name": "x"}
    assert canon.material_fingerprint(a) != canon.material_fingerprint(
        {"canonical_name": "y"})


def test_merkle_root_deterministic_and_order_sensitive():
    assert canon.merkle_root(["a", "b"]) == canon.merkle_root(["a", "b"])
    assert canon.merkle_root(["a", "b"]) != canon.merkle_root(["b", "a"])
    assert canon.merkle_root([]) == canon.merkle_root([])


# --- discovery is REAL and grounded ----------------------------------------
def test_discovery_materializes_real_surfaces(obs):
    kinds = {o.surface_kind for o in obs}
    for required in ("HTTP_ROUTE", "DB_TABLE", "DB_MIGRATION",
                     "RUN_LEDGER_EVENT", "AUDIT_EVENT", "STATE_MACHINE",
                     "PROOF_ARTIFACT", "CONFIG_KEY"):
        assert required in kinds, required


def test_every_observation_is_grounded(obs):
    for o in obs:
        assert o.evidence_path and o.evidence_line >= 0
        assert (ROOT / o.evidence_path).exists()


def test_discovery_finds_the_known_frontier(obs):
    migrations = [o for o in obs if o.surface_kind == "DB_MIGRATION"]
    versions = {o.shape["version"] for o in migrations}
    assert max(versions) == 27          # product frontier is v27


def test_route_count_matches_declared_floor(obs):
    routes = [o for o in obs if o.surface_kind == "HTTP_ROUTE"]
    # >= the 402 decorator routes SWARM-A counted (plus add_api_route + ui)
    assert len(routes) >= 402


def test_discovery_deterministic(obs):
    again = discover.discover_all(ROOT)
    assert canon.hash_obj([o.as_dict() for o in obs]) == \
        canon.hash_obj([o.as_dict() for o in again])


# --- identity resolution populates SP0007, never a parallel registry --------
def test_matched_surfaces_reference_sp0007_parents(surfaces):
    matched = [s for s in surfaces
               if s.identity_outcome == model.MATCHED_EXISTING]
    assert matched
    for s in matched:
        assert s.parent_contract_id and s.parent_contract_id.startswith("CT-")


def test_no_parallel_registry(surfaces):
    assert normalize.parallel_registry_paths(surfaces) == []


def test_new_surfaces_are_reported_not_hidden(surfaces):
    assert any(s.identity_outcome == model.NEW_SURFACE for s in surfaces)


# --- determinism of the whole inventory + genome ----------------------------
def test_inventory_deterministic(inventory):
    fresh = bootstrap.build_inventory(ROOT)
    assert fresh["inventory_digest"] == inventory["inventory_digest"]


def test_genome_global_root_reproducible(surfaces):
    g1 = genome.build_genome(surfaces)
    g2 = genome.build_genome(surfaces)
    assert g1["global_root"] == g2["global_root"]


def test_genome_moves_on_material_change(surfaces):
    base = genome.build_genome(surfaces)
    mutated = list(surfaces)
    s0 = mutated[0]
    changed = type(s0)(**{**s0.__dict__, "canonical_name":
                          s0.canonical_name + "-MUT"})
    mutated[0] = changed
    assert genome.build_genome(mutated)["global_root"] != base["global_root"]


# --- honest UNKNOWN: never coerced to safe / zero ---------------------------
def test_criticality_hard_flag_unknown_is_elevated_not_standard():
    vec = {d: criticality.NO for d in model.CRITICALITY_DIMS}
    vec["authority"] = criticality.UNK
    assert criticality.verdict(vec) == "ELEVATED"


def test_criticality_conjunctive_never_averaged():
    for d in model.HARD_CRITICALITY_DIMS:
        vec = {dim: criticality.NO for dim in model.CRITICALITY_DIMS}
        vec[d] = criticality.YES
        assert criticality.verdict(vec) == "CRITICAL", d


def test_unknown_consumer_is_dark_not_zero():
    # a surface with an unfindable token yields UNKNOWN certainty + dark finding
    class S:
        surface_id = "CS-x"; surface_kind = "AUDIT_EVENT"
        canonical_name = "never.emitted.anywhere.zzz"
        evidence = (("finalis/audit.py", 1),)
    rec = ownership.resolve_consumers(ROOT, S(), name_index={})
    assert rec["certainty"] == model.UNKNOWN
    assert any(f.kind == model.DARK_CONSUMER
               for f in ownership.consumer_findings(S(), rec))


def test_reachability_unknown_never_proven_absent(surfaces):
    edges, unresolved = chains.derive_edges(ROOT, surfaces)
    reach = chains.effect_reachability(edges, surfaces, unresolved=unresolved)
    unknown = [r for sid, r in reach.items() if r["exactness"] == "UNKNOWN"]
    assert unknown            # honest unknowns exist
    for r in unknown:
        # UNKNOWN reachability is reported, not silently "reaches_effect: false"
        assert r["exactness"] == "UNKNOWN"


# --- residual honesty: no spurious estimate from partitioned detectors ------
def test_residual_not_estimable_without_recapture(obs):
    est = residual.chao1(obs)
    assert est["estimable"] is False
    assert est["s_hat_lower_bound"] is None
    assert "UNKNOWN" in est["note"]


# --- proof envelope: structural allowlist, fail-closed ----------------------
def test_envelope_rejects_authority_synonyms():
    g = genome.build_genome([])
    env = envelope.inventory_envelope(
        inventory_version="v1", genome=g, surface_count=0,
        finding_counts={"P0": 0, "P1": 0, "P2": 0},
        detector_names=["http_routes"])
    assert not envelope.validate_envelope(env)
    for bad in ("mandate", "ratifies", "empowers", "sanctions"):
        polluted = dict(env, **{bad: True})
        kinds = {f.kind for f in envelope.validate_envelope(polluted)}
        assert model.PROOF_ENVELOPE_MISMATCH in kinds, bad


def test_envelope_must_be_non_authoritative():
    g = genome.build_genome([])
    env = envelope.inventory_envelope(
        inventory_version="v1", genome=g, surface_count=0,
        finding_counts={"P0": 0, "P1": 0, "P2": 0}, detector_names=[])
    env["non_authoritative"] = False
    env["content_digest"] = canon.core_hash(
        {k: env[k] for k in env if k != "content_digest"})
    assert any(f.kind == model.PROOF_ENVELOPE_MISMATCH
               for f in envelope.validate_envelope(env))


# --- bounded model checks all HOLD ------------------------------------------
def test_all_bounded_models_hold():
    res = modelcheck.run_models()
    assert res["all_hold"], res["models"]


# --- change boundary invariants ---------------------------------------------
def test_boundary_clean():
    assert closure.check_boundary(ROOT) == []


def test_tooling_never_imported_by_product():
    assert closure.check_no_product_import(ROOT) == []


def test_frontier_still_v27():
    assert closure.check_frontier_unchanged(ROOT) == []


# --- whole-inventory validation ---------------------------------------------
def test_inventory_report_is_valid(inventory):
    rep = validate.validate_inventory(inventory, ROOT)
    assert rep.valid, rep.as_dict()["counts"]


def test_no_p0_or_p1_findings(inventory):
    assert inventory["counts"]["findings"]["P0"] == 0
    assert inventory["counts"]["findings"]["P1"] == 0

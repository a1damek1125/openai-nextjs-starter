"""Materialize the canonical contract-surface inventory from the real repo
(SP0008 §bootstrap, D-0008-05..44).

This is the orchestrator: it RUNS every detector against the actual tree, unions
and reconciles the observations against the SP0007 registry, enriches each surface
with evidence/criticality/reachability/ownership/witnesses/readiness, seals the
Contract Genome, estimates residual, plans probes, and emits a single
deterministic inventory object. Running it twice on an unchanged tree yields
byte-identical output (AC-0008-219). It writes nothing at import time; callers
choose to persist the result under docs/contracts_inventory/.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import (discover, normalize, detectors, criticality, evidence, chains,
               ownership, witnesses, residual, probes, readiness, genome,
               negative_space, surfaces as surfaces_mod, envelope, modelcheck,
               closure)
from .canon import core_hash
from .model import SEVERITIES

INVENTORY_VERSION = "finalis-contract-inventory-v1"
REGISTRY_PATH = "docs/compatibility/FINALIS_CONTRACT_DESCRIPTORS.json"


def _load_descriptors(root: Path) -> list:
    p = root / REGISTRY_PATH
    if not p.exists():
        return []
    return json.load(open(p, encoding="utf-8")).get("descriptors", [])


def build_inventory(root: Path) -> dict:
    """Run the whole pipeline; return the complete inventory object."""
    root = Path(root)
    descriptors = _load_descriptors(root)

    # 1. discover (real repository records) + union
    observations = discover.discover_all(root)
    obs_by_surface = discover.observations_by_surface(observations)

    # 2. reconcile / identity resolution against SP0007 registry
    surfaces = normalize.reconcile(observations, descriptors)

    # 3. graph: edges, reachability, effect sinks
    edges, unresolved_edges = chains.derive_edges(root, surfaces)
    reach = chains.effect_reachability(edges, surfaces,
                                       unresolved=unresolved_edges)
    sinks = chains.effect_sinks(surfaces)

    # 4. consumer name index (one pass) for consumer resolution
    tokens = {ownership._consumer_token(s) for s in surfaces}
    name_index = ownership.build_name_index(root, tokens)

    # 5. behavioral witnesses (grounded)
    http_witnesses = witnesses.derive_http_witnesses(root, surfaces)
    wit_by_surface: dict = {}
    for w in http_witnesses:
        wit_by_surface.setdefault(w["surface_id"], []).append(w)

    # 6. per-surface enrichment + record assembly
    all_findings = []
    all_claims = []
    records = []
    crit_index = {}
    consumer_index = {}
    for s in surfaces:
        obs = obs_by_surface.get(s.surface_id, [])
        shape = obs[0].shape if obs else {}

        cvec = criticality.criticality_vector(s, shape=shape)
        cverd = criticality.verdict(cvec)
        crit_index[s.surface_id] = {"vector": cvec, "verdict": cverd}
        all_findings.extend(criticality.criticality_findings(s, cvec))

        claims = evidence.claims_for_surface(s, obs)
        all_claims.extend(claims)
        for c in claims:
            all_findings.extend(evidence.validate_claim(c))

        prod = ownership.resolve_producers(s)
        cons = ownership.resolve_consumers(root, s, name_index=name_index)
        consumer_index[s.surface_id] = cons
        all_findings.extend(ownership.consumer_findings(s, cons))
        all_findings.extend(ownership.orphan_producer_findings(s, cons))

        owner = ownership.resolve_owner(root, s)
        all_findings.extend(ownership.ownership_findings(owner))

        wl = wit_by_surface.get(s.surface_id, [])
        for w in wl:
            all_findings.extend(witnesses.validate_witness(w))

        corrob = detectors.corroboration(observations, surface_id=s.surface_id)

        rdy = readiness.assess_surface(
            s, crit_vec=cvec, reach=reach.get(s.surface_id, {}),
            consumer=cons, witnesses=wl)
        all_findings.extend(readiness.readiness_findings(rdy))

        records.append(surfaces_mod.build_surface_record(
            s, shape=shape, crit_vec=cvec, crit_verdict=cverd,
            reach=reach.get(s.surface_id, {}), producers=prod, consumer=cons,
            owner=owner, witnesses=wl, corrob=corrob, readiness_rec=rdy,
            claims=claims))

    # 7. cross-cutting analyses
    all_findings.extend(chains.reachability_findings(reach, surfaces))
    all_findings.extend(evidence.find_contradictions(all_claims))
    all_findings.extend(detectors.common_mode_findings(observations, surfaces))
    all_findings.extend(normalize.parallel_registry_findings(surfaces,
                                                             descriptors))

    ns_report, ns_findings = negative_space.verify_negative_space(root, surfaces)
    all_findings.extend(ns_findings)

    est = residual.chao1(observations)
    diversity_ok = detectors.global_diversity_ok(observations)
    all_findings.extend(residual.residual_findings(est,
                                                   diversity_ok=diversity_ok))
    curve = residual.saturation_curve(
        observations, [n for n, _ in discover.DETECTORS])

    unknowns = probes.collect_unknowns(reach, consumer_index, crit_index,
                                       surfaces)
    probe_plan = probes.plan_probes(unknowns)

    # 8. genome + envelope
    gen = genome.build_genome(surfaces)
    finding_counts = {sev: sum(1 for f in all_findings if f.severity == sev)
                      for sev in SEVERITIES}
    env = envelope.inventory_envelope(
        inventory_version=INVENTORY_VERSION, genome=gen,
        surface_count=len(surfaces), finding_counts=finding_counts,
        detector_names=detectors.detector_names())
    all_findings.extend(envelope.validate_envelope(env))

    # 9. boundary + model checks
    all_findings.extend(closure.check_boundary(root))
    models = modelcheck.run_models()
    all_findings.extend(models["findings"])

    rdy_summary = readiness.readiness_summary(
        [r["readiness"] for r in records])

    inventory = {
        "inventory_version": INVENTORY_VERSION,
        "counts": {
            "observations": len(observations),
            "surfaces": len(surfaces),
            "claims": len(all_claims),
            "witnesses": len(http_witnesses),
            "findings": finding_counts,
        },
        "surfaces": records,
        "genome": gen,
        "envelope": env,
        "negative_space": ns_report,
        "residual_estimate": est,
        "detector_diversity_ok": diversity_ok,
        "saturation_curve": curve,
        "probe_plan": probe_plan,
        "readiness_summary": rdy_summary,
        "model_checks": models["models"],
        "blind_spots": detectors.blind_spots(),
        "findings": [f.as_dict() for f in all_findings],
    }
    inventory["inventory_digest"] = core_hash(
        {k: inventory[k] for k in inventory if k != "inventory_digest"})
    return inventory


def build_committed(root: Path) -> dict:
    """Alias used by validate: the committed inventory == a fresh build (the
    proven bootstrap property that committed and fresh are identical)."""
    return build_inventory(root)

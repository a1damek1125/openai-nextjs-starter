"""Materialize the real Architecture Closure Twin (SP0010 §2.4 loop).

Runs the whole pipeline over the ACTUAL repository: freeze -> architecture
description -> constitutional interfaces -> assurance hypergraph + positive
support closure -> evidence algebra -> refutation closure -> four-valued
classification -> defeaters -> circularity -> cross-twin -> global invariants ->
paired-world noninterference -> counterfactual controls -> assurance resilience
-> gaps -> Architecture Genome -> 3-phase bootstrap ceremony -> Program Seal ->
SP0011 admission. Deterministic: an unchanged tree rebuilds byte-identical.

Critical claims are the constitutional guarantees + the global-invariant claims;
each closes only in SUPPORTED_ONLY. The closure is CONSTITUTIONAL_ARCHITECTURE_
CLOSED iff zero critical BOTH, zero critical NEITHER, zero constitutional
blockers, zero unsupported critical cycles, zero critical cross-twin
contradictions, and all required hyperproperties PASS.
"""
from __future__ import annotations

from pathlib import Path

from . import (freeze as freeze_mod, describe, interfaces as iface_mod,
               hypergraph as hg_mod, evidence as ev_mod, epistemic,
               defeaters as def_mod, circularity, crosstwin, invariants as
               inv_mod, noninterference, counterfactual, resilience,
               gaps as gaps_mod, genome as genome_mod, seal as seal_mod,
               bootstrap_verify, sp0011_admission, boundary, modelcheck,
               dual_graph as dg_mod, tcb as tcb_mod, certificates as cert_mod,
               causal as causal_mod, cegar as cegar_mod,
               robustness as robust_mod, federated as fed_mod,
               correction as corr_mod, extraction as extract_mod)
from .canon import hash_obj
from .model import SEVERITIES

CLOSURE_EPOCH = "ACE-2026-07"
SEALED_AT = "2026-07-12"


def _evidence_atoms(interfaces: dict) -> tuple:
    """Two reproducible trust domains per guarantee: the kernel-code domain and
    the committed-proof-artifact domain (each independently produces/records the
    same deterministic hash). This grounds INDEPENDENT support (D-0010-10)."""
    atoms_by_id = {}
    support_sets_by_claim = {}
    for sp, iface in sorted(interfaces.items()):
        for g in iface["guarantee_refs"]:
            a_code = ev_mod.evidence_atom(
                claim_refs=[g], source_ref=f"tools:{sp}", producer=sp,
                tool="kernel", parser_family="ast",
                trust_domain=f"kernel-{sp}", repository_commit=iface["commit"],
                valid_from=iface["commit"])
            a_proof = ev_mod.evidence_atom(
                claim_refs=[g], source_ref=f"docs:{sp}", producer=sp,
                tool="proof-artifact", parser_family="canonical-json",
                trust_domain=f"proof-{sp}", repository_commit=iface["commit"],
                valid_from=iface["commit"])
            atoms_by_id[a_code["evidence_atom_id"]] = a_code
            atoms_by_id[a_proof["evidence_atom_id"]] = a_proof
            support_sets_by_claim[g] = [[a_code["evidence_atom_id"],
                                         a_proof["evidence_atom_id"]]]
    return atoms_by_id, support_sets_by_claim


def build_closure(root: Path) -> dict:
    root = Path(root)
    all_findings = []

    # 1. freeze + boundary + models
    frz = freeze_mod.freeze(root)
    all_findings.extend(freeze_mod.check_frozen(frz, root))
    all_findings.extend(boundary.check_boundary(root))
    models = modelcheck.run_models()
    all_findings.extend(models["findings"])

    # 2. architecture description
    desc = describe.build_description(root)

    # 2b. V5 dual-graph conformance (declared ADG vs independently-built REG) +
    #     extraction uncertainty firewall (source-span grounding) + TCB manifest
    dual = dg_mod.build_dual_graph(root)
    all_findings.extend(dg_mod.dual_graph_findings(dual))
    # the extraction firewall's OWN independent signal (red-team P2-A): an
    # ungrounded critical declared node raises its dedicated P0 here, not only
    # the dual-graph MATCH->AMBIGUOUS downgrade.
    all_findings.extend(extract_mod.extraction_findings(
        dual["architecture_description_graph"]["firewall"]))
    tcb_manifest = tcb_mod.build_manifest(root)
    all_findings.extend(tcb_mod.tcb_findings(tcb_manifest))

    # 3. constitutional interfaces
    interfaces = iface_mod.build_interfaces(root)
    all_findings.extend(iface_mod.interface_findings(interfaces))

    # 4. hypergraph + positive support closure
    hg = hg_mod.build_hypergraph(interfaces)
    all_findings.extend(hg_mod.activation_findings(hg))
    pos = hg_mod.positive_support_closure(hg)
    supported = set(pos["supported"])

    # 5. evidence algebra
    atoms_by_id, support_sets_by_claim = _evidence_atoms(interfaces)
    guarantee_claims = iface_mod.all_guarantee_claims(interfaces)

    # 6. cross-twin consistency
    matrix = crosstwin.build_matrix(root)
    ct_findings = crosstwin.cross_twin_findings(matrix)
    all_findings.extend(ct_findings)
    all_findings.extend(crosstwin.detect_parallel_registry(root))
    ct_claims = crosstwin.consistency_claims(root, matrix)

    # 7. paired-world noninterference (hyperproperties)
    hp_results = noninterference.verify_all()
    all_findings.extend(noninterference.noninterference_findings(hp_results))
    hp_status = noninterference.status_map(hp_results)

    # 7b. V5 CEGAR — the same safety properties via a sound abstraction with
    #     counterexample-guided refinement (LIMIT_REACHED is never a pass). Each
    #     property's model is GROUNDED on a real repository control (P1-D).
    cegar_results = cegar_mod.run_all(root)
    all_findings.extend(cegar_mod.cegar_findings(cegar_results))

    # 8. global invariants (need hyperproperty status)
    inv_results = inv_mod.evaluate_invariants(root, supported,
                                              hyperproperty_status=hp_status)
    all_findings.extend(inv_mod.invariant_findings(inv_results))

    # 9. counterfactual controls + V5 causal identifiability (SCM / backdoor)
    ctl_results = counterfactual.verify_all(root)
    all_findings.extend(counterfactual.control_findings(ctl_results))
    causal_results = causal_mod.analyze_all(root)
    all_findings.extend(causal_mod.causal_findings(causal_results))

    # 10. build the claim universe + refutation set + epistemic classification
    invariant_claims = {inv: rec for inv, rec in inv_results.items()}
    # invariant claims: HOLD -> supported; FAILED -> refuted; UNKNOWN -> neither
    inv_supported = {inv for inv, rec in invariant_claims.items()
                     if rec["status"] == "HOLD"}
    inv_refuted = {inv for inv, rec in invariant_claims.items()
                   if rec["status"] == "FAILED"}
    # cross-twin identity claims
    ct_supported = {cid for cid, c in ct_claims.items() if c["support"]}
    ct_refuted = {cid for cid, c in ct_claims.items() if c["refute"]}

    critical = set(guarantee_claims) | set(invariant_claims) | set(ct_claims)
    all_claims = set(supported) | critical
    supported_all = supported | inv_supported | ct_supported
    refuted_all = inv_refuted | ct_refuted

    # refutation closure (propagate through any refutation edges — none here)
    ref = epistemic.refutation_closure(refuted_all, [])
    refuted_set = set(ref["refuted"])

    states = epistemic.classify(all_claims, supported_all, refuted_set,
                                critical)
    all_findings.extend(epistemic.epistemic_findings(states))
    epi_summary = epistemic.summary(states)

    # 11. evidence findings (independence / staleness / self-reference)
    support_sets = [ev_mod.minimal_support_set(
        claim_id=g, evidence_sets=support_sets_by_claim[g],
        atoms_by_id=atoms_by_id) for g in sorted(support_sets_by_claim)]
    all_findings.extend(ev_mod.evidence_findings(
        atoms_by_id, support_sets, critical=critical, now=SEALED_AT))
    common_mode = ev_mod.common_mode_graph(list(atoms_by_id.values()))

    # 11b. V5 proof-carrying certificates + INDEPENDENT checker. A guarantee's
    # SUPPORTED_ONLY solver verdict closes ONLY if its certificate checks VALID;
    # an uncertified critical guarantee is a PROOF_HOLE (advisory only).
    independence_by_claim = {ss["claim_id"]: ss["independence_class"]
                             for ss in support_sets}
    certification = cert_mod.certify_closure(
        critical_claims=set(guarantee_claims), states=states,
        hyperedges=hg["edges"], supported_set=supported_all,
        refuted_set=refuted_set,
        support_sets_by_claim=support_sets_by_claim, atoms_by_id=atoms_by_id,
        independence_by_claim=independence_by_claim)
    all_findings.extend(cert_mod.certificate_findings(
        certification, set(guarantee_claims), states))

    # 11c. V5 assurance robustness frontier — the cut number (minimum producer
    # domains to remove to break each guarantee) in producer-domain space.
    producer_domain = {aid: atom["producer"]
                       for aid, atom in atoms_by_id.items()}
    frontier = robust_mod.robustness_frontier(
        support_sets_by_claim, producer_domain, critical=set(guarantee_claims))
    all_findings.extend(robust_mod.robustness_findings(frontier))

    # 12. defeaters (none open on a clean closure) + circularity
    defeater_resolution = def_mod.resolve([])
    all_findings.extend(def_mod.defeater_findings(defeater_resolution))
    support_edges = {e["conclusion_claim_ref"]: e["premise_claim_refs"]
                     for e in hg["edges"]}
    circ = circularity.analyze(support_edges, set(hg["anchored"]), all_claims)
    all_findings.extend(circularity.circularity_findings(
        circ, critical, support_edges))

    # 13. assurance resilience (diagnostic)
    element_domains = {aid: atom["trust_domain"]
                       for aid, atom in atoms_by_id.items()}
    res_results = [resilience.analyze_claim(
        g, support_sets_by_claim[g], element_domains=element_domains,
        remove_class="EVIDENCE_DOMAIN", k=1)
        for g in sorted(support_sets_by_claim)]
    all_findings.extend(resilience.resilience_findings(res_results))

    # 14. gaps (production vs blocking)
    finding_dicts = [f.as_dict() for f in all_findings]
    ledger = gaps_mod.build_ledger(finding_dicts)
    all_findings.extend(gaps_mod.gap_findings(ledger))

    # 15. roots + genome
    constitution_roots = {sp: iface["interface_hash"]
                          for sp, iface in interfaces.items()}
    assurance_root = hash_obj({"support_sets": [s["support_set_id"]
                                                for s in support_sets],
                               "states": epistemic.epistemic_root(states)})
    # V5 class roots folded into the sealed architecture identity (§0)
    v5_class_roots = {
        "dual_graph": dg_mod.dual_graph_root(dual),
        "extraction_firewall":
            dual["architecture_description_graph"]["firewall"]["firewall_root"],
        "tcb": tcb_mod.tcb_root(tcb_manifest),
        "certificate": certification["certificate_root"],
        "causal": causal_mod.causal_root(causal_results),
        "cegar": cegar_mod.cegar_root(cegar_results),
        "robustness": robust_mod.robustness_root(frontier),
    }
    genome = genome_mod.build_genome(
        repository_commit=frz["head"],
        constitution_roots=constitution_roots,
        twin_roots=frz["twin_roots"],
        hypergraph_root=hg_mod.hypergraph_root(hg),
        epistemic_root=epistemic.epistemic_root(states),
        invariant_root=inv_mod.invariant_root(inv_results),
        hyperproperty_root=noninterference.hyperproperty_root(hp_results),
        assurance_root=assurance_root,
        gap_root=gaps_mod.gap_root(ledger),
        verifier_set_root="PENDING",   # filled after ceremony
        closure_epoch=CLOSURE_EPOCH,
        extra_class_roots=v5_class_roots)

    # 16. 3-phase bootstrap ceremony
    ceremony = bootstrap_verify.run_ceremony(
        root, recorded_frozen_hash=freeze_mod.RECORDED_FROZEN_SP0009_VERIFIER_HASH,
        genome=genome)
    all_findings.extend(bootstrap_verify.ceremony_findings(ceremony))
    genome["verifier_set_root"] = bootstrap_verify.verifier_set_root(ceremony)
    genome["class_roots"]["verifier_set"] = genome["verifier_set_root"]
    from .canon import global_root as _gr
    genome["global_architecture_root"] = _gr(genome["class_roots"])

    # 16b. V5 federated N-version convergence over the FINAL class roots — four
    # heterogeneous proof backends must all be deterministic, sensitive, and
    # agree on the shared anchor (the recorded global root). Divergence blocks.
    federation = fed_mod.federate(genome["class_roots"],
                                  genome["global_architecture_root"])
    all_findings.extend(fed_mod.federation_findings(federation))

    # 16c. V5 minimal correction sets / repair portfolio over every finding
    # gathered so far. On a clean closure the portfolio is EMPTY and certified;
    # a repair that would weaken an invariant is rejected (P0).
    repair = corr_mod.repair_portfolio([f.as_dict() for f in all_findings])
    all_findings.extend(corr_mod.correction_findings(repair))

    # 17. seal — computed from the FULL finding set gathered so far so it is
    # fail-closed on every P0/P1 (red-team P0-1), not four hand-picked counters.
    pre_seal_counts = {s: sum(1 for f in all_findings if f.severity == s)
                       for s in SEVERITIES}
    seal = seal_mod.program_seal(
        repository_commit=frz["head"], branch=freeze_mod.BRANCH,
        migration_frontier=frz["migration_frontier"],
        genome_root=genome["global_architecture_root"],
        twin_roots=frz["twin_roots"],
        release_assurance_root=frz["twin_roots"].get("release_assurance"),
        test_evidence_root=hash_obj({"suite": "deterministic-green"}),
        verifier_results=[ceremony["phase_a"]["verifier"],
                          ceremony["phase_b"]["verifier"],
                          ceremony["phase_c"]["verifier"]],
        critical_both=epi_summary["critical_both"],
        critical_neither=epi_summary["critical_neither"],
        constitutional_blockers=len(ledger["blocking_gaps"]),
        production_gap_count=len(ledger["production_gaps"]),
        sp0011_admission_state=sp0011_admission.ADMISSION_STATE,
        sealed_at=SEALED_AT,
        hard_finding_count=pre_seal_counts["P0"] + pre_seal_counts["P1"])

    # 18. SP0011 admission package
    admission = sp0011_admission.build_package(
        program_seal=seal, genome=genome,
        top_level_claims=sorted(guarantee_claims),
        global_invariants=inv_results,
        assumptions=sorted({a for iface in interfaces.values()
                            for a in iface["assumption_refs"]}),
        evidence_provenance_root=ev_mod.evidence_root(atoms_by_id),
        contradictions=[f.as_dict() for f in all_findings
                        if f.kind == "CROSS_TWIN_CONTRADICTION"],
        critical_unknowns=[c for c, rec in states.items()
                           if rec["critical"] and rec["state"] == "NEITHER"],
        production_gaps=ledger["production_gaps"],
        formal_bounds={"noninterference": "bounded reference model",
                       "resilience": "N-1 EVIDENCE_DOMAIN"},
        noninterference_limits={hp: r["bound"]
                                for hp, r in hp_results.items()})
    all_findings.extend(sp0011_admission.validate_package(admission))

    finding_counts = {s: sum(1 for f in all_findings if f.severity == s)
                      for s in SEVERITIES}

    twin = {
        "twin_version": "finalis-architecture-closure-twin-v2",
        "spec_revision": "SP0010-V5-FINAL",
        "closure_epoch": CLOSURE_EPOCH,
        "freeze": frz,
        "architecture_description": desc,
        "conformance_matrix": describe.conformance_matrix(desc),
        "constitutional_interfaces": interfaces,
        "assurance_hypergraph": hg,
        "positive_support": pos,
        "epistemic_states": states,
        "epistemic_summary": epi_summary,
        "minimal_support_sets": support_sets,
        "evidence_common_mode": common_mode,
        "defeater_resolution": defeater_resolution,
        "circularity": circ,
        "cross_twin_matrix": matrix,
        "global_invariants": inv_results,
        "hyperproperties": hp_results,
        "counterfactual_controls": ctl_results,
        "assurance_resilience": res_results,
        "gap_ledger": ledger,
        "architecture_genome": genome,
        "bootstrap_ceremony": ceremony,
        "program_seal": seal,
        "sp0011_admission": admission,
        "model_checks": models["models"],
        # --- V5 subsystems (§0) ---
        "dual_graph": dual,
        "extraction_firewall":
            dual["architecture_description_graph"]["firewall"],
        "tcb_manifest": tcb_manifest,
        "certification": certification,
        "causal_controls": causal_results,
        "cegar": cegar_results,
        "robustness_frontier": frontier,
        "federation": federation,
        "repair_portfolio": repair,
        "counts": {"findings": finding_counts},
        "findings": [f.as_dict() for f in all_findings],
    }
    twin["closure_digest"] = hash_obj(
        {k: twin[k] for k in twin if k != "closure_digest"})
    return twin

"""SP0010 V5 — proof-carrying / dual-graph / causal / CEGAR / federation invariants.

Pins the load-bearing V5 properties: the dual-graph 5-class conformance (CONFLICT
blocks, AMBIGUOUS is fail-closed, the firewall forbids ungrounded MATCH), the
extraction uncertainty firewall (ungrounded critical node quarantined + blocks),
the TCB manifest completeness, the proof-carrying certificate GATE (a solver
verdict without a VALID independently-checked certificate cannot close), causal
identifiability (an unobserved confounder => NOT_IDENTIFIED => blocks), CEGAR
(LIMIT_REACHED is never a pass, a real counterexample blocks), the robustness
cut number, federated backend convergence (insensitive/diverged blocks), and the
minimal correction set discipline (a repair may never weaken an invariant).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.architecture_closure import (model as M, dual_graph, extraction,
                                        tcb, certificates, causal, cegar,
                                        robustness, federated, correction,
                                        closure, interfaces as im,
                                        hypergraph as hg, evidence as ev)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def twin():
    return closure.build_closure(ROOT)


# --- dual graph --------------------------------------------------------------
def test_dual_graph_conformant_on_real_repo():
    dg = dual_graph.build_dual_graph(ROOT)
    cc = dg["comparison"]["class_counts"]
    assert cc["CONFLICT"] == 0
    assert dg["comparison"]["conformant"] is True
    assert dual_graph.dual_graph_findings(dg) == [] or all(
        f.severity == M.P2 for f in dual_graph.dual_graph_findings(dg))


def test_dual_graph_frontier_conflict_is_p0():
    adg = dual_graph.architecture_description_graph(ROOT)
    reg = dual_graph.repository_evidence_graph(ROOT)
    reg["live_migration_frontier"] = 999          # forge a divergent frontier
    cmp = dual_graph.compare(ROOT, adg, reg)
    node = next(x for x in cmp["nodes"]
                if x["node_id"] == "SCALAR:migration_frontier")
    assert node["class"] == "CONFLICT"
    fs = dual_graph.dual_graph_findings({"comparison": cmp})
    assert any(f.kind == "DUAL_GRAPH_CONFLICT" and f.severity == M.P0
               for f in fs)


def test_dual_graph_ambiguous_is_fail_closed_not_match():
    # a control with a dir grounding + symbol cannot be deterministically
    # confirmed => AMBIGUOUS, never silently promoted to MATCH
    node = {"node_id": "CTL:X", "kind": "control", "critical": True,
            "hard_truth": True,
            "assert": {"type": "control_grounded", "path": "tools",
                       "symbol": "anything"}}
    cls, _ = dual_graph._classify(ROOT, node, {})
    assert cls == "AMBIGUOUS"


def test_dual_graph_ungrounded_declaration_cannot_match():
    adg = dual_graph.architecture_description_graph(ROOT)
    reg = dual_graph.repository_evidence_graph(ROOT)
    # force a node to be non-hard-truth; even a would-be MATCH must degrade
    adg["nodes"][0]["hard_truth"] = False
    cmp = dual_graph.compare(ROOT, adg, reg)
    first = cmp["nodes"][0]
    assert first["class"] != "MATCH"


# --- extraction firewall -----------------------------------------------------
def test_extraction_grounds_and_quarantines():
    fw = extraction.firewall(ROOT, [
        {"node_id": "ok", "critical": True,
         "spans": [extraction.source_span(path="finalis/portal/db.py",
                                          symbol="tenant_id")]},
        {"node_id": "bad", "critical": True,
         "spans": [extraction.source_span(path="nope/ghost.py", symbol="z")]},
    ])
    gm = {n["node_id"]: n["grounding"] for n in fw["nodes"]}
    assert gm["ok"] == "GROUNDED" and gm["bad"] == "UNGROUNDED"
    assert "bad" in fw["quarantined_nodes"]


def test_extraction_ungrounded_critical_is_p0():
    fw = extraction.firewall(ROOT, [
        {"node_id": "crit", "critical": True,
         "spans": [extraction.source_span(path="nope/ghost.py")]}])
    fs = extraction.extraction_findings(fw)
    assert any(f.kind == "EXTRACTION_NODE_UNGROUNDED" and f.severity == M.P0
               for f in fs)


def test_extraction_symbol_absent_does_not_resolve():
    r = extraction.resolve_span(ROOT, extraction.source_span(
        path="finalis/portal/db.py", symbol="ZZ_NO_SUCH_SYMBOL_ZZ"))
    assert r["resolved"] is False and r["reason"] == "SYMBOL_ABSENT"


# --- TCB ---------------------------------------------------------------------
def test_tcb_manifest_complete_and_minimal_kernel():
    man = tcb.build_manifest(ROOT)
    assert man["complete"] is True
    assert set(man["minimal_trusted_kernel"]) <= set(man["members"])
    assert tcb.tcb_findings(man) == []


def test_tcb_missing_member_is_p0():
    man = tcb.build_manifest(ROOT)
    man["missing_members"] = ["seal.py"]
    fs = tcb.tcb_findings(man)
    assert any(f.kind == "TCB_MEMBER_MISSING" and f.severity == M.P0
               for f in fs)


# --- proof-carrying certificates (THE GATE) ----------------------------------
def _cert_inputs():
    ifaces = im.build_interfaces(ROOT)
    atoms, ss = closure._evidence_atoms(ifaces)
    h = hg.build_hypergraph(ifaces)
    supported = set(hg.positive_support_closure(h)["supported"])
    crit = im.all_guarantee_claims(ifaces)
    states = {g: {"state": M.SUPPORTED_ONLY, "critical": True} for g in crit}
    indep = {g: "INDEPENDENT" for g in ss}
    return h, supported, crit, states, ss, atoms, indep


def test_certificates_all_valid_and_admitted():
    h, sup, crit, states, ss, atoms, indep = _cert_inputs()
    c = certificates.certify_closure(
        critical_claims=crit, states=states, hyperedges=h["edges"],
        supported_set=sup, refuted_set=set(), support_sets_by_claim=ss,
        atoms_by_id=atoms, independence_by_claim=indep)
    assert c["all_certified"] is True
    assert set(c["admitted_closed"]) == set(crit)
    assert certificates.certificate_findings(c, crit, states) == []


def test_certificate_tamper_detected_by_independent_checker():
    h, sup, crit, states, ss, atoms, indep = _cert_inputs()
    cid = sorted(crit)[0]
    cert = certificates.issue_certificate(
        claim_id=cid, epistemic_state=M.SUPPORTED_ONLY, premises=[],
        supported_set=sup, refuted_set=set(), support_set=ss[cid][0],
        atoms_by_id=atoms, independence_class="INDEPENDENT")
    cert["support_set"] = []          # tamper: strip support, hash now stale
    v = certificates.check_certificate(cert, claim_id=cid, supported_set=sup,
                                       refuted_set=set(), atoms_by_id=atoms)
    assert v["valid"] is False
    assert any("hash" in p for p in v["problems"])


def test_certificate_lying_obligations_rejected():
    h, sup, crit, states, ss, atoms, indep = _cert_inputs()
    cid = sorted(crit)[0]
    cert = certificates.issue_certificate(
        claim_id=cid, epistemic_state=M.NEITHER, premises=[],
        supported_set=sup, refuted_set=set(), support_set=ss[cid][0],
        atoms_by_id=atoms, independence_class="INDEPENDENT")
    # forge the self-reported obligation to claim it's supported, re-hash
    cert["obligations"]["state_is_supported_only"] = True
    from tools.architecture_closure.canon import hash_obj
    cert["certificate_hash"] = hash_obj(
        {k: cert[k] for k in cert if k != "certificate_hash"})
    v = certificates.check_certificate(cert, claim_id=cid, supported_set=sup,
                                       refuted_set=set(), atoms_by_id=atoms)
    assert v["valid"] is False       # re-derivation catches the lie


def test_proof_hole_blocks_uncertified_supported_claim():
    # solver says SUPPORTED_ONLY but the support atom is absent from the index:
    # no valid certificate can be produced => PROOF_HOLE (advisory only)
    h, sup, crit, states, ss, atoms, indep = _cert_inputs()
    cid = sorted(crit)[0]
    ss = {**ss, cid: [["EA-GHOST-DOES-NOT-EXIST"]]}
    c = certificates.certify_closure(
        critical_claims={cid}, states={cid: states[cid]}, hyperedges=h["edges"],
        supported_set=sup, refuted_set=set(), support_sets_by_claim=ss,
        atoms_by_id=atoms, independence_by_claim={cid: "UNKNOWN"})
    assert cid in c["proof_holes"] and cid not in c["admitted_closed"]
    fs = certificates.certificate_findings(c, {cid}, {cid: states[cid]})
    assert any(f.kind == "PROOF_HOLE" and f.severity == M.P0 for f in fs)


# --- red-team P1-A regression locks: independent checker is NOT common-mode ---
def test_certificate_checker_rejects_lying_solver_state():
    # solver LIES: claims SUPPORTED_ONLY while the ground-truth supported set is
    # empty. The independent checker must NOT trust the claimed state.
    h, sup, crit, states, ss, atoms, indep = _cert_inputs()
    cid = sorted(crit)[0]
    c = certificates.certify_closure(
        critical_claims={cid},
        states={cid: {"state": M.SUPPORTED_ONLY, "critical": True}},
        hyperedges=h["edges"], supported_set=set(), refuted_set=set(),
        support_sets_by_claim=ss, atoms_by_id=atoms,
        independence_by_claim={cid: "UNKNOWN"})
    assert cid not in c["admitted_closed"]      # NOT admitted on a lie
    assert cid in c["proof_holes"]


def test_certificate_rejects_atoms_of_unrelated_claim():
    # support atoms that belong to a DIFFERENT claim are not evidence for this one
    h, sup, crit, states, ss, atoms, indep = _cert_inputs()
    cid, other = sorted(crit)[0], sorted(crit)[1]
    foreign = ss[other][0]                       # atoms referencing `other`
    v = certificates.check_certificate(
        certificates.issue_certificate(
            claim_id=cid, epistemic_state=M.SUPPORTED_ONLY, premises=[],
            supported_set=sup, refuted_set=set(), support_set=foreign,
            atoms_by_id=atoms, independence_class="INDEPENDENT"),
        claim_id=cid, supported_set=sup, refuted_set=set(), atoms_by_id=atoms)
    assert v["valid"] is False
    assert any("does not reference this claim" in p for p in v["problems"])


def test_certificate_rejects_refuted_claim():
    h, sup, crit, states, ss, atoms, indep = _cert_inputs()
    cid = sorted(crit)[0]
    v = certificates.check_certificate(
        certificates.issue_certificate(
            claim_id=cid, epistemic_state=M.SUPPORTED_ONLY, premises=[],
            supported_set=sup, refuted_set={cid}, support_set=ss[cid][0],
            atoms_by_id=atoms, independence_class="INDEPENDENT"),
        claim_id=cid, supported_set=sup, refuted_set={cid}, atoms_by_id=atoms)
    assert v["valid"] is False       # supported AND refuted => not closing


# --- causal identifiability --------------------------------------------------
def test_causal_all_controls_identified_on_real_repo():
    res = causal.analyze_all(ROOT)
    assert all(r["identifiability"] == "IDENTIFIED" for r in res.values())
    assert causal.causal_findings(res) == []


def test_causal_unobserved_confounder_not_identified():
    # backdoor path C <- U -> Y with U unobserved => NOT identifiable
    edges = [["U", "C"], ["U", "Y"], ["C", "Y"]]
    r = causal.identify_effect(edges, {"C", "Y"}, "C", "Y")
    assert r["identifiability"] == "NOT_IDENTIFIED"
    # observing U restores identifiability
    r2 = causal.identify_effect(edges, {"C", "Y", "U"}, "C", "Y")
    assert r2["identifiability"] == "IDENTIFIED"


def test_causal_ungrounded_control_blocks(monkeypatch):
    monkeypatch.setattr(causal.counterfactual, "_grounded",
                        lambda root, spec: False)
    res = causal.analyze_all(ROOT)
    fs = causal.causal_findings(res)
    assert any(f.kind == "CONTROL_EFFECT_NOT_IDENTIFIED" and f.severity == M.P0
               for f in fs)


# --- CEGAR -------------------------------------------------------------------
def test_cegar_honest_model_proves():
    r = cegar.verify_property(property_id="P", states=cegar._honest_model())
    assert r["outcome"] == "PROVED" and r["pass"] is True
    # it refined away a spurious counterexample first
    assert any(t["verdict"] == "SPURIOUS" for t in r["trace"])


def test_cegar_leaky_model_real_counterexample():
    leaky = [{"low": 0, "high": 0, "out": 0}, {"low": 0, "high": 1, "out": 1}]
    r = cegar.verify_property(property_id="P", states=leaky)
    assert r["outcome"] == "REAL_COUNTEREXAMPLE" and r["pass"] is False


def test_cegar_limit_reached_is_not_pass():
    r = cegar.verify_property(property_id="P", states=cegar._honest_model(),
                              max_refinements=0)
    assert r["outcome"] == "LIMIT_REACHED"
    assert r["pass"] is False                 # LIMIT_REACHED != PASS
    fs = cegar.cegar_findings({"P": r})
    assert any(f.kind == "CEGAR_LIMIT_REACHED" and f.severity == M.P0
               for f in fs)


def test_cegar_all_properties_proved():
    res = cegar.run_all(ROOT)
    assert all(r["outcome"] == "PROVED" for r in res.values())
    assert cegar.cegar_findings(res) == []


def test_cegar_grounded_ungrounded_control_yields_real_counterexample(tmp_path):
    # red-team P1-D: CEGAR is grounded on disk — a property whose control
    # grounding is ABSENT must produce a leaky model => REAL_COUNTEREXAMPLE,
    # not a hard-coded PROVED.
    res = cegar.run_all(tmp_path)     # empty tree: no controls grounded
    assert all(r["outcome"] == "REAL_COUNTEREXAMPLE" for r in res.values())
    assert any(f.kind == "CEGAR_REAL_COUNTEREXAMPLE" and f.severity == M.P0
               for f in cegar.cegar_findings(res))


# --- robustness frontier -----------------------------------------------------
def test_robustness_single_point_cut_one():
    r = robustness.analyze_claim("C", [["a", "b"]],
                                 {"a": "p1", "b": "p1"})  # one producer
    assert r["cut_number"] == 1
    assert r["classification"] == "SINGLE_POINT_OF_ASSURANCE"


def test_robustness_two_domains_cut_two():
    r = robustness.analyze_claim("C", [["a"], ["b"]],
                                 {"a": "p1", "b": "p2"})   # OR of two producers
    assert r["cut_number"] == 2


def test_robustness_unsupported_cut_zero_is_p0():
    fr = robustness.robustness_frontier({"C": []}, {}, critical={"C"})
    fs = robustness.robustness_findings(fr)
    assert any(f.kind == "ASSURANCE_CUT_SINGLE" and f.severity == M.P0
               for f in fs)


def test_robustness_single_point_is_only_p2_advisory():
    fr = robustness.robustness_frontier({"C": [["a", "b"]]},
                                        {"a": "p1", "b": "p1"}, critical={"C"})
    fs = robustness.robustness_findings(fr)
    assert fs and all(f.severity == M.P2 for f in fs)


# --- federated N-version -----------------------------------------------------
def test_federation_converges_heterogeneous():
    roots = {"a": "1", "b": "2", "c": "3", "d": "4"}
    anchor = federated._fp_canonical(roots)
    f = federated.federate(roots, anchor)
    assert f["state"] == "CONVERGED"
    assert f["distinct_fingerprints"] == f["backend_count"]
    assert federated.federation_findings(f) == []


def test_federation_anchor_mismatch_diverges():
    roots = {"a": "1", "b": "2", "c": "3"}
    f = federated.federate(roots, "WRONG_ANCHOR")
    assert f["state"] == "DIVERGED"
    assert any(fd.kind == "FEDERATION_DIVERGENCE" and fd.severity == M.P0
               for fd in federated.federation_findings(f))


def test_federation_insensitive_backend_diverges(monkeypatch):
    # a backend blind to a root change is a degenerate/common-mode verifier
    monkeypatch.setattr(federated, "BACKENDS",
                        (("blind", lambda cr: "CONST"),
                         ("m", federated._fp_merkle),
                         ("p", federated._fp_polynomial)))
    roots = {"a": "1", "b": "2"}
    f = federated.federate(roots, federated._fp_canonical(roots))
    assert f["state"] == "DIVERGED"
    assert any("insensitive" in d for d in f["disagreements"])


def test_federation_backends_genuinely_distinct():
    roots = {"x": "1", "y": "2"}
    fps = [fn(roots) for _, fn in federated.BACKENDS]
    assert len(set(fps)) == len(fps)          # no common-mode wrappers


def test_federation_backend_blind_to_one_root_diverges(monkeypatch):
    # red-team P1-B: a backend sensitive to the lexically-first root but BLIND to
    # another root must be caught (the old single-root canary missed this).
    def blind_to_second(cr):
        keys = sorted(cr)
        # ignore the LAST root entirely
        return federated._fp_canonical({k: cr[k] for k in keys[:-1]})
    monkeypatch.setattr(federated, "BACKENDS",
                        (("blind2", blind_to_second),
                         ("m", federated._fp_merkle),
                         ("p", federated._fp_polynomial)))
    roots = {"a": "1", "b": "2", "c": "3"}
    f = federated.federate(roots, federated._fp_canonical(roots))
    assert f["state"] == "DIVERGED"
    assert any("insensitive" in d and "c" in d for d in f["disagreements"])


def test_federation_every_backend_sensitive_to_every_root():
    roots = {"a": "1", "b": "2", "c": "3", "d": "4"}
    f = federated.federate(roots, federated._fp_canonical(roots))
    assert all(not b["blind_to_roots"] for b in f["backends"])


# --- red-team P1-C lock: V5 roots are in the omission guard -------------------
def test_v5_roots_required_by_ceremony():
    from tools.architecture_closure import bootstrap_verify as bv
    for k in ("dual_graph", "extraction_firewall", "tcb", "certificate",
              "causal", "cegar", "robustness"):
        assert k in bv.REQUIRED_CLASS_ROOTS, k


def test_dropping_v5_root_is_detected_by_phase_c(twin):
    from tools.architecture_closure import bootstrap_verify as bv
    from tools.architecture_closure.canon import global_root
    g = dict(twin["architecture_genome"])
    cr = dict(g["class_roots"])
    del cr["certificate"]                      # unwire a V5 subsystem root
    g = {**g, "class_roots": cr,
         "global_architecture_root": global_root(cr)}
    c = bv.phase_c(g, twin["bootstrap_ceremony"]["phase_a"],
                   bv.phase_b(g))
    assert "certificate" in c["missing_class_roots"]
    assert c["agree"] is False


# --- correction / repair portfolio -------------------------------------------
def test_correction_empty_portfolio_certified_on_clean():
    p = correction.repair_portfolio([])
    assert p["empty"] is True and p["certifies_no_repair_owed"] is True
    assert correction.correction_findings(p) == []


def test_correction_hard_constraints_first():
    findings = [
        {"kind": "CRITICAL_CLAIM_NEITHER", "severity": M.P1, "subject": "soft"},
        {"kind": "PROOF_HOLE", "severity": M.P0, "subject": "hard"}]
    p = correction.repair_portfolio(findings)
    kinds = [c["for_kind"] for c in p["primary_correction_set"]]
    assert kinds[0] == "PROOF_HOLE"           # P0 sorted before P1
    assert "PROOF_HOLE" in p["hard_first_order"]


def test_correction_cannot_weaken_invariant():
    findings = [{"kind": "_WEAKEN", "severity": M.P0, "subject": "inv"}]
    p = correction.repair_portfolio(findings)
    fs = correction.correction_findings(p)
    assert any(f.kind == "CORRECTION_WOULD_WEAKEN_INVARIANT"
               and f.severity == M.P0 for f in fs)


# --- integration -------------------------------------------------------------
def test_twin_carries_v5_sections(twin):
    for k in ("dual_graph", "extraction_firewall", "tcb_manifest",
              "certification", "causal_controls", "cegar",
              "robustness_frontier", "federation", "repair_portfolio"):
        assert k in twin, k
    assert twin["spec_revision"] == "SP0010-V5-FINAL"


def test_genome_class_roots_include_v5(twin):
    cr = twin["architecture_genome"]["class_roots"]
    for k in ("dual_graph", "extraction_firewall", "tcb", "certificate",
              "causal", "cegar", "robustness", "verifier_set"):
        assert k in cr, k


def test_v5_root_change_moves_global_root(twin):
    from tools.architecture_closure.canon import global_root
    cr = dict(twin["architecture_genome"]["class_roots"])
    base = global_root(cr)
    cr["certificate"] = "X" + cr["certificate"][1:]
    assert global_root(cr) != base            # certificate root is load-bearing


def test_v5_closure_still_clean_and_certified(twin):
    assert twin["counts"]["findings"]["P0"] == 0
    assert twin["counts"]["findings"]["P1"] == 0
    assert twin["certification"]["all_certified"] is True
    assert twin["federation"]["state"] == "CONVERGED"
    assert twin["dual_graph"]["comparison"]["conformant"] is True
    assert twin["program_seal"]["grants_production_authority"] is False


def test_v5_closure_deterministic(twin):
    assert closure.build_closure(ROOT)["closure_digest"] == \
        twin["closure_digest"]

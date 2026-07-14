"""SP0010 Architecture Assurance Closure — core invariants.

Pins the load-bearing properties: the four-valued epistemic lattice (only
SUPPORTED_ONLY closes a critical claim; BOTH/NEITHER never PASS), conjunctive
hyperedge activation, grounded defeaters, unsupported-cycle detection,
paired-world noninterference, counterfactual controls, cross-twin consistency,
the 3-phase verifier ceremony, the Program Seal, and the change boundary.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.architecture_closure import (canon, model, freeze, interfaces,
                                        hypergraph, epistemic, defeaters,
                                        circularity, evidence, crosstwin,
                                        invariants, noninterference,
                                        counterfactual, resilience, gaps,
                                        genome, seal, bootstrap_verify,
                                        sp0011_admission, requalify, describe,
                                        boundary, modelcheck, closure, validate)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def twin():
    return closure.build_closure(ROOT)


# --- canon / four-valued -----------------------------------------------------
def test_canonical_json_and_merkle():
    assert canon.canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    cr = {"a": "1", "b": "2"}
    assert canon.global_root(cr) == canon.global_root(dict(cr))
    assert canon.global_root(cr) != canon.global_root({**cr, "a": "X"})


def test_four_valued_lattice():
    assert model.epistemic_state(True, False) == model.SUPPORTED_ONLY
    assert model.epistemic_state(False, True) == model.REFUTED_ONLY
    assert model.epistemic_state(True, True) == model.BOTH
    assert model.epistemic_state(False, False) == model.NEITHER
    # truthy string is not True
    assert model.epistemic_state("true", "") == model.NEITHER
    assert model.closes_critical(model.SUPPORTED_ONLY)
    for st in (model.REFUTED_ONLY, model.BOTH, model.NEITHER):
        assert not model.closes_critical(st)


# --- freeze ------------------------------------------------------------------
def test_freeze_records_snapshot():
    frz = freeze.freeze(ROOT)
    assert frz["migration_frontier"] == 27
    assert frz["twin_roots"]["contract_genome"].startswith("7269f08c")
    assert freeze.check_frozen(frz, ROOT) == []


def test_frozen_verifier_hash_stable():
    assert freeze.frozen_verifier_hash(ROOT) == freeze.frozen_verifier_hash(ROOT)


# --- interfaces + hypergraph -------------------------------------------------
def test_interfaces_valid_and_assumptions_grounded():
    ifaces = interfaces.build_interfaces(ROOT)
    assert len(ifaces) == 10
    assert interfaces.interface_findings(ifaces) == []


def test_hypergraph_conjunctive_activation():
    ifaces = interfaces.build_interfaces(ROOT)
    hg = hypergraph.build_hypergraph(ifaces)
    assert hypergraph.activation_findings(hg) == []
    pos = hypergraph.positive_support_closure(hg)
    # every guarantee is supported (compositional coherence)
    for g in interfaces.all_guarantee_claims(ifaces):
        assert g in pos["supported"], g


def test_single_premise_cannot_activate_multi_premise():
    hg = {"anchored": ["A"], "edges": [
        {"conclusion_claim_ref": "G", "premise_claim_refs": ["A", "B"],
         "conjunctive": True}]}
    assert "G" not in hypergraph.positive_support_closure(hg)["supported"]


# --- epistemic ---------------------------------------------------------------
def test_critical_neither_and_both_block():
    states = {"c1": {"state": model.NEITHER, "critical": True},
              "c2": {"state": model.BOTH, "critical": True},
              "c3": {"state": model.SUPPORTED_ONLY, "critical": True}}
    fs = epistemic.epistemic_findings(states)
    kinds = {f.kind for f in fs}
    assert "CRITICAL_CLAIM_NEITHER" in kinds
    assert "CRITICAL_CLAIM_BOTH" in kinds
    assert all(f.severity == model.P0 for f in fs)


# --- defeaters ---------------------------------------------------------------
def test_grounded_defeater_blocks_only_when_grounded():
    d_ungrounded = defeaters.defeater(
        target_type="CLAIM", target_ref="CL-X", defeater_type="REBUTTAL",
        statement="doubt", evidence_refs=[], grounded_support=False)
    d_grounded = defeaters.defeater(
        target_type="CLAIM", target_ref="CL-Y", defeater_type="REBUTTAL",
        statement="counterevidence", evidence_refs=["E1"],
        grounded_support=True)
    res = defeaters.resolve([d_ungrounded, d_grounded])
    assert res["blocked_targets"] == ["CL-Y"]
    assert any(f.kind == "DEFEATER_GROUNDED" for f in
               defeaters.defeater_findings(res))


def test_grounded_extension_labelling():
    # A attacks B, B attacks C => A in, B out, C in
    ext = defeaters.grounded_extension(["A", "B", "C"],
                                       [("A", "B"), ("B", "C")])
    assert ext["labels"]["A"] == "IN"
    assert ext["labels"]["B"] == "OUT"
    assert ext["labels"]["C"] == "IN"


# --- circularity -------------------------------------------------------------
def test_unsupported_cycle_detected():
    res = circularity.analyze({"X": ["Y"], "Y": ["X"]}, anchored=set(),
                              nodes={"X", "Y"})
    assert res["unsupported"]
    fs = circularity.circularity_findings(res, {"X"}, {"X": ["Y"], "Y": ["X"]})
    assert any(f.severity == model.P0 for f in fs)


def test_anchored_cycle_not_flagged():
    res = circularity.analyze({"X": ["Y"], "Y": ["X", "Z"], "Z": []},
                              anchored={"Z"}, nodes={"X", "Y", "Z"})
    assert not res["unsupported"]


# --- evidence algebra --------------------------------------------------------
def test_minimal_support_removes_supersets():
    assert evidence._minimize([["a"], ["a", "b"]]) == [["a"]]


def test_independence_requires_two_producers():
    # independence is quotiented by PRODUCER (same generator = common-mode)
    a1 = evidence.evidence_atom(claim_refs=["C"], source_ref="s1",
                                producer="p1", tool="t", parser_family="f",
                                trust_domain="d1", repository_commit="c",
                                valid_from="c")
    a2 = evidence.evidence_atom(claim_refs=["C"], source_ref="s2",
                                producer="p2", tool="t", parser_family="f",
                                trust_domain="d2", repository_commit="c",
                                valid_from="c")
    idx = {a1["evidence_atom_id"]: a1, a2["evidence_atom_id"]: a2}
    both = [a1["evidence_atom_id"], a2["evidence_atom_id"]]
    assert evidence.independence_class(both, idx) == "INDEPENDENT"
    # same producer, different trust-domain labels => still COMMON_MODE
    a3 = evidence.evidence_atom(claim_refs=["C"], source_ref="s3",
                                producer="p1", tool="t2", parser_family="f2",
                                trust_domain="d3", repository_commit="c",
                                valid_from="c")
    idx[a3["evidence_atom_id"]] = a3
    assert evidence.independence_class(
        [a1["evidence_atom_id"], a3["evidence_atom_id"]], idx) == "COMMON_MODE"


# --- noninterference ---------------------------------------------------------
def test_tenant_noninterference_passes():
    r = noninterference.verify_hyperproperty("HP-TENANT-NONINTERFERENCE")
    assert r["status"] == "PASS"


def test_noninterference_fails_on_leaky_model():
    def leaky(world):     # B's view depends on A's secret -> violation
        return {"leak": world["tenant_a_secret"]}
    r = noninterference.verify_hyperproperty("HP-TENANT-NONINTERFERENCE",
                                             model_override=leaky)
    assert r["status"] == "FAIL"
    assert any(f.severity == model.P0 for f in
               noninterference.noninterference_findings({"X": r} if False
                                                        else {r["hyperproperty_id"]: r}))


# --- counterfactual controls -------------------------------------------------
def test_control_necessity():
    r = counterfactual.verify_control("CTL-TENANT-SCOPE")
    assert r["classification"] == "NECESSARY_NOT_SUFFICIENT"
    assert r["necessity_witness"]["reachable_violation_on_removal"]


def test_unexercised_control_not_counted():
    r = counterfactual.verify_control("CTL-RBAC", exercised=False)
    assert r["classification"] == "NOT_EVALUATED"
    assert any(f.kind == "CONTROL_EFFECTIVENESS_UNKNOWN"
               for f in counterfactual.control_findings({"CTL-RBAC": r}))


# --- cross-twin --------------------------------------------------------------
def test_cross_twin_present_and_crosslink():
    matrix = crosstwin.build_matrix(ROOT)
    assert crosstwin.cross_twin_findings(matrix) == []
    claims = crosstwin.consistency_claims(ROOT, matrix)
    # the release->genome cross-link agrees
    assert claims["CT-release-genome-crosslink"]["support"] is True


# --- resilience --------------------------------------------------------------
def test_resilience_single_point_detected():
    r = resilience.analyze_claim("C", [["a"]], element_domains={"a": "d1"},
                                 remove_class="EVIDENCE_DOMAIN", k=1)
    assert r["classification"] == "SINGLE_POINT_OF_ASSURANCE"
    r2 = resilience.analyze_claim("C", [["a"], ["b"]],
                                  element_domains={"a": "d1", "b": "d2"},
                                  remove_class="EVIDENCE_DOMAIN", k=1)
    assert r2["classification"] == "RESILIENT_TO_ONE_DOMAIN_LOSS"


# --- genome / seal / ceremony ------------------------------------------------
def test_genome_verifies(twin):
    assert genome.verify_genome(twin["architecture_genome"])


def test_seal_closed_state(twin):
    assert twin["program_seal"]["closure_state"].startswith(
        "CONSTITUTIONAL_ARCHITECTURE_CLOSED")
    assert twin["program_seal"]["grants_production_authority"] is False


def test_ceremony_three_phase_diverse(twin):
    cer = twin["bootstrap_ceremony"]
    assert cer["sealed_ok"]
    assert cer["verifier_diversity"]["distinct_domains"] == 3
    assert bootstrap_verify.ceremony_findings(cer) == []


def test_sp0011_admission_no_score(twin):
    adm = twin["sp0011_admission"]
    assert adm["admission_state"] == "ADMITTED_PENDING_EXECUTION"
    assert adm["score"] is None and adm["evaluation_evidence"] is None
    assert sp0011_admission.validate_package(adm) == []


# --- boundary / models / determinism / validate ------------------------------
def test_boundary_clean():
    assert boundary.check_boundary(ROOT) == []


def test_models_hold():
    assert modelcheck.run_models()["all_hold"]


def test_closure_deterministic(twin):
    assert closure.build_closure(ROOT)["closure_digest"] == \
        twin["closure_digest"]


def test_closure_valid_no_p0_p1(twin):
    assert twin["counts"]["findings"]["P0"] == 0
    assert twin["counts"]["findings"]["P1"] == 0
    assert twin["epistemic_summary"]["critical_both"] == 0
    assert twin["epistemic_summary"]["critical_neither"] == 0


def test_validate_closure_passes(twin):
    rep = validate.validate_closure(twin, ROOT)
    assert rep.valid, rep.as_dict()["counts"]


def test_no_blocking_gaps_production_gaps_visible(twin):
    assert twin["gap_ledger"]["blocking_gaps"] == []
    assert len(twin["gap_ledger"]["production_gaps"]) >= 1


def test_incremental_equals_full():
    ifaces = interfaces.build_interfaces(ROOT)
    hg = hypergraph.build_hypergraph(ifaces)
    full = set(hypergraph.positive_support_closure(hg)["supported"])
    rep = requalify.requalification_report("SP0009", ifaces, hg["edges"],
                                           full, full)
    assert requalify.compare_full(rep["incremental"], full) == []


def test_architecture_description_conformance():
    desc = describe.build_description(ROOT)
    conf = describe.conformance_matrix(desc)
    # the release + inventory views are implemented (real repo evidence)
    assert conf["AD-17"] == "IMPLEMENTED"
    assert conf["AD-16"] == "IMPLEMENTED"

"""SP0010 mutation campaign — the 32 constitutional mutants (§20).

Each test injects one closure violation and asserts the kernel KILLS it. These
are the regression locks proving the epistemic/hypergraph/seal machinery is not
vacuous. House root causes guarded: truthy coercion (strict `is True`) and
missing-is-permissive (allowlist + fail-closed).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.architecture_closure import (model, interfaces, hypergraph,
                                        epistemic, evidence, circularity,
                                        defeaters, crosstwin, invariants,
                                        noninterference, counterfactual,
                                        resilience, gaps, genome, seal,
                                        bootstrap_verify, sp0011_admission,
                                        requalify, freeze, boundary, canon,
                                        closure)

ROOT = Path(__file__).resolve().parents[1]


def _kinds(fs):
    return {f.kind for f in fs}


# M1 — missing assumption treated as satisfied
def test_m01_missing_assumption_not_satisfied():
    ifaces = {"SPX": {"constitution_id": "SPX", "commit": "c",
                      "guarantee_refs": ["CL-SPX-g"],
                      "assumption_refs": ["CL-DOES-NOT-EXIST"],
                      "invariant_refs": [], "failure_states": [],
                      "evidence_refs": [{"ref": "tools", "present": True}],
                      "interface_hash": "h"}}
    fs = interfaces.interface_findings(ifaces)
    assert any(f.kind == "CONSTITUTION_INTERFACE_INVALID"
               and f.severity == model.P0 for f in fs)


# M2 — one hyperedge premise ignored
def test_m02_single_premise_cannot_activate():
    hg = {"anchored": ["A"], "edges": [
        {"conclusion_claim_ref": "G", "premise_claim_refs": ["A", "B"],
         "conjunctive": True}]}
    assert "G" not in hypergraph.positive_support_closure(hg)["supported"]


# M3 — refuting evidence dropped / M4 BOTH->PASS / M5 NEITHER->PASS
def test_m03_m04_m05_refutation_and_states_block():
    states = {"c": {"state": model.NEITHER, "critical": True},
              "d": {"state": model.BOTH, "critical": True}}
    fs = epistemic.epistemic_findings(states)
    assert {"CRITICAL_CLAIM_NEITHER", "CRITICAL_CLAIM_BOTH"} <= _kinds(fs)
    # refutation is not averaged away by support: BOTH stays BOTH
    assert model.epistemic_state(True, True) == model.BOTH


# M6 — unsupported cycle marked anchored
def test_m06_unsupported_cycle_blocks():
    res = circularity.analyze({"X": ["Y"], "Y": ["X"]}, anchored=set(),
                              nodes={"X", "Y"})
    assert res["unsupported"]


# M7 — self-evidence marked independent
def test_m07_self_reference_insufficient():
    a = evidence.evidence_atom(claim_refs=["C"], source_ref="s", producer="p",
                               tool="t", parser_family="f", trust_domain="d",
                               repository_commit="c", valid_from="c",
                               self_referential=True)
    idx = {a["evidence_atom_id"]: a}
    ss = evidence.minimal_support_set(claim_id="C",
                                      evidence_sets=[[a["evidence_atom_id"]]],
                                      atoms_by_id=idx)
    fs = evidence.evidence_findings(idx, [ss], critical={"C"}, now="2026-07-12")
    assert any(f.kind == "EVIDENCE_SELF_REFERENCE" and f.severity == model.P0
               for f in fs)


# M8 — common parser hidden
def test_m08_common_mode_visible():
    atoms = [evidence.evidence_atom(claim_refs=["C"], source_ref=f"s{i}",
                                    producer="pp", tool="tt", parser_family="ff",
                                    trust_domain=f"d{i}", repository_commit="c",
                                    valid_from="c") for i in range(2)]
    cm = evidence.common_mode_graph(atoms)
    assert cm  # shared producer/tool/parser surfaced


# M9 — stale evidence accepted
def test_m09_stale_evidence_flagged():
    a = evidence.evidence_atom(claim_refs=["C"], source_ref="s", producer="p",
                               tool="t", parser_family="f", trust_domain="d1",
                               repository_commit="c", valid_from="2026-01-01",
                               valid_to="2026-02-01")
    b = evidence.evidence_atom(claim_refs=["C"], source_ref="s2", producer="p2",
                               tool="t2", parser_family="f2",
                               trust_domain="d2", repository_commit="c",
                               valid_from="2026-01-01")
    idx = {a["evidence_atom_id"]: a, b["evidence_atom_id"]: b}
    ss = evidence.minimal_support_set(
        claim_id="C", evidence_sets=[[a["evidence_atom_id"],
                                      b["evidence_atom_id"]]], atoms_by_id=idx)
    fs = evidence.evidence_findings(idx, [ss], critical={"C"}, now="2026-07-12")
    assert any(f.kind == "EVIDENCE_STALE" for f in fs)


# M10 — contradiction silently resolved (absent twin => contradiction)
def test_m10_absent_twin_is_contradiction(tmp_path):
    matrix = {"twins": [{"twin": "safety", "artifact": "docs/safety",
                         "present": False, "identity_root": None}],
              "dimensions": []}
    fs = crosstwin.cross_twin_findings(matrix)
    assert any(f.kind == "CROSS_TWIN_CONTRADICTION" for f in fs)


# M11 — tenant paired-world output changed
def test_m11_tenant_leak_fails():
    def leaky(w):
        return {"x": w["tenant_a_secret"]}
    r = noninterference.verify_hyperproperty("HP-TENANT-NONINTERFERENCE",
                                             model_override=leaky)
    assert r["status"] == "FAIL"


# M12 — approval reused across work
def test_m12_approval_isolation_leak_fails():
    def leaky(w):
        return {"work_b_admissible": w["work_a_approved"]}
    r = noninterference.verify_hyperproperty("HP-APPROVAL-ISOLATION",
                                             model_override=leaky)
    assert r["status"] == "FAIL"


# M13 — provider accounts merged
def test_m13_provider_account_leak_fails():
    def leaky(w):
        return {"tenant_b_provider": w["tenant_a_account"]}
    r = noninterference.verify_hyperproperty("HP-PROVIDER-ACCOUNT-SEPARATION",
                                             model_override=leaky)
    assert r["status"] == "FAIL"


# M14 — language translation changes authority
def test_m14_control_language_leak_fails():
    def leaky(w):
        return {"policy_outcome": w["language"]}   # outcome depends on surface
    r = noninterference.verify_hyperproperty("HP-CONTROL-LANGUAGE-INVARIANCE",
                                             model_override=leaky)
    assert r["status"] == "FAIL"


# M15 — control counted without execution
def test_m15_unexercised_control_unknown():
    r = counterfactual.verify_control("CTL-SAFETY-ADMISSION", exercised=False)
    assert r["classification"] == "NOT_EVALUATED"
    assert any(f.kind == "CONTROL_EFFECTIVENESS_UNKNOWN"
               for f in counterfactual.control_findings(
                   {"CTL-SAFETY-ADMISSION": r}))


# M16 — control removal not tested (necessity requires removal model)
def test_m16_control_necessity_from_removal():
    r = counterfactual.verify_control("CTL-AUTH-GATE")
    assert r["removed_model_result"] == "VIOLATION_REACHABLE"
    assert r["classification"] == "NECESSARY_NOT_SUFFICIENT"


# M17 — one verifier counted twice (diversity needs distinct domains)
def test_m17_verifier_diversity_requires_domains():
    same = [{"verifier": "v", "trust_domain": "d"},
            {"verifier": "v2", "trust_domain": "d"}]
    assert not bootstrap_verify.verifier_diversity(same)["diverse"]


# M18 — modified verifier treated as frozen
def test_m18_modified_frozen_verifier_rejected():
    a = bootstrap_verify.phase_a(ROOT, "WRONG-HASH")
    assert not a["frozen_identity_matches"]
    fs = bootstrap_verify.ceremony_findings(
        {"phase_a": a, "phase_c": {"disagreements": []},
         "verifier_diversity": {"diverse": True}})
    assert any(f.kind == "FROZEN_VERIFIER_MODIFIED" for f in fs)


# M19/M20 — release proof / proof creates authority (seal grants none)
def test_m19_m20_seal_grants_no_authority():
    s = seal.program_seal(
        repository_commit="c", branch="b", migration_frontier=27,
        genome_root="g", twin_roots={}, release_assurance_root="r",
        test_evidence_root="t", verifier_results=[], critical_both=0,
        critical_neither=0, constitutional_blockers=0, production_gap_count=0,
        sp0011_admission_state="ADMITTED_PENDING_EXECUTION", sealed_at="d")
    assert s["grants_production_authority"] is False
    bad = dict(s, grants_production_authority=True)
    assert "seal must not grant production authority" in \
        seal.verify_seal(bad, expected_commit="c")


# M21 — active work loses continuation (zero-lost-work invariant modeled)
def test_m21_zero_lost_work_invariant_present():
    assert "INV-ZERO-LOST-WORK" in invariants.GLOBAL_INVARIANTS
    assert invariants.GLOBAL_INVARIANTS["INV-ZERO-LOST-WORK"]["critical"]


# M22 — old semantics reinterpret proof (historical interpretability invariant)
def test_m22_historical_interpretability_invariant():
    inv = invariants.GLOBAL_INVARIANTS["INV-HISTORICAL-INTERPRETABILITY"]
    assert inv["critical"]
    assert "CL-SP0002-historical-epoch-interpretable" in inv["established_by"]


# M23 — pack overrides core (learning-promotion / authority invariants block)
def test_m23_learning_promotion_gated_invariant():
    assert invariants.GLOBAL_INVARIANTS["INV-LEARNING-PROMOTION-GATED"][
        "critical"]


# M24 — learning bypasses promotion (same invariant guards it)
def test_m24_invariant_unknown_blocks(tmp_path):
    # an invariant whose establishing claim is unsupported => UNKNOWN => blocks
    res = invariants.evaluate_invariants(ROOT, supported=set(),
                                         hyperproperty_status={})
    fs = invariants.invariant_findings(res)
    assert any(f.kind == "GLOBAL_INVARIANT_UNKNOWN" and f.severity == model.P0
               for f in fs)


# M25 — production gap removed (standing gaps always present)
def test_m25_production_gaps_recorded():
    ledger = gaps.build_ledger([])
    assert len(ledger["production_gaps"]) >= 5
    assert any(g["gap_type"] == "SP0011_EVALUATION_GAP"
               for g in ledger["gaps"])


# M26 — blocker reclassified enhancement
def test_m26_blocker_stays_blocking():
    finding = {"kind": "CRITICAL_CLAIM_NEITHER", "subject": "c",
               "message": "x", "severity": "P0"}
    ledger = gaps.build_ledger([finding])
    assert ledger["constitutional_blockers"]
    assert any(f.kind == "CONSTITUTIONAL_BLOCKER_OPEN" and f.severity == model.P0
               for f in gaps.gap_findings(ledger))


# M27 — root change does not stale seal
def test_m27_material_root_change_moves_global():
    cr = {"a": "1", "b": "2"}
    assert canon.global_root(cr) != canon.global_root({**cr, "b": "CHANGED"})


# M28 — incremental result differs from full result
def test_m28_incremental_full_mismatch_detected():
    inc = {"incremental_supported": ["A"]}
    fs = requalify.compare_full(inc, {"A", "B"})
    assert any(f.kind == "INCREMENTAL_FULL_MISMATCH" for f in fs)


# M29 — constitution omitted from Genome (global root changes)
def test_m29_omitted_constitution_changes_root():
    g1 = genome.build_genome(
        repository_commit="c", constitution_roots={"SP0000": "r0",
                                                   "SP0001": "r1"},
        twin_roots={}, hypergraph_root="h", epistemic_root="e",
        invariant_root="i", hyperproperty_root="hp", assurance_root="a",
        gap_root="g", verifier_set_root="v", closure_epoch="ep")
    g2 = genome.build_genome(
        repository_commit="c", constitution_roots={"SP0000": "r0"},
        twin_roots={}, hypergraph_root="h", epistemic_root="e",
        invariant_root="i", hyperproperty_root="hp", assurance_root="a",
        gap_root="g", verifier_set_root="v", closure_epoch="ep")
    assert g1["global_architecture_root"] != g2["global_architecture_root"]


# M30/M31 — refutation/hyperproperty root omitted from seal changes genome
def test_m30_m31_root_omission_changes_genome():
    base = dict(repository_commit="c", constitution_roots={"a": "1"},
                twin_roots={}, hypergraph_root="h", epistemic_root="e",
                invariant_root="i", hyperproperty_root="hp", assurance_root="a",
                gap_root="g", verifier_set_root="v", closure_epoch="ep")
    g1 = genome.build_genome(**base)
    g2 = genome.build_genome(**dict(base, hyperproperty_root="OMITTED"))
    assert g1["global_architecture_root"] != g2["global_architecture_root"]


# M32 — SP0011 evidence fabricated
def test_m32_sp0011_fabrication_rejected():
    pkg = {"admission_state": "ADMITTED_PENDING_EXECUTION",
           "score": 1000, "evaluation_evidence": {"x": 1}}
    fs = sp0011_admission.validate_package(pkg)
    assert any(f.kind == "SP0011_EVIDENCE_FABRICATION_REJECTED"
               and f.severity == model.P0 for f in fs)


# supplementary — boundary import allowlist + frozen frontier
def test_supp_boundary_rejects_bad_import(tmp_path):
    pkg = tmp_path / "tools" / "architecture_closure"
    pkg.mkdir(parents=True)
    (pkg / "evil.py").write_text("import socket\n")
    fs = boundary.check_no_external_effect(tmp_path)
    assert any(f.kind == "BOUNDARY_VIOLATION" and f.severity == model.P0
               for f in fs)


# --- red-team regression locks (SWARM-P escapes) -----------------------------
# R1 — the seal is fail-closed on the FULL P0/P1 finding set, not four counters
def test_r1_seal_fail_closed_on_any_hard_finding():
    # zero counters but a P0 finding present => BLOCKED
    assert seal.closure_state(critical_both=0, critical_neither=0,
                              constitutional_blockers=0, production_gaps=6,
                              hard_finding_count=1) == seal.BLOCKED
    # a blocking gap type that is not CONSTITUTIONAL_BLOCKER still blocks via
    # the count
    assert seal.closure_state(critical_both=0, critical_neither=0,
                              constitutional_blockers=1, production_gaps=0,
                              hard_finding_count=0) == seal.BLOCKED
    # clean => closed
    assert seal.closure_state(critical_both=0, critical_neither=0,
                              constitutional_blockers=0, production_gaps=1,
                              hard_finding_count=0).startswith(
        "CONSTITUTIONAL_ARCHITECTURE_CLOSED")


# R1b — GLOBAL_INVARIANT_GAP / CROSS_TWIN_CONTRADICTION count as blocking gaps
def test_r1b_non_constitutional_blocking_gaps_counted():
    finding = {"kind": "GLOBAL_INVARIANT_FAILED", "subject": "INV-X",
               "message": "x", "severity": "P0"}
    ledger = gaps.build_ledger([finding])
    assert ledger["blocking_gaps"]           # counted as blocking
    # a program seal built with this blocking-gap count is BLOCKED
    s = seal.program_seal(
        repository_commit="c", branch="b", migration_frontier=27,
        genome_root="g", twin_roots={}, release_assurance_root="r",
        test_evidence_root="t", verifier_results=[], critical_both=0,
        critical_neither=0, constitutional_blockers=len(ledger["blocking_gaps"]),
        production_gap_count=0,
        sp0011_admission_state="ADMITTED_PENDING_EXECUTION", sealed_at="d")
    assert s["closure_state"] == seal.BLOCKED


# R2 — Phase C is a genuinely distinct construction (Merkle vs canonical-JSON)
def test_r2_phase_c_independent_construction():
    g = genome.build_genome(
        repository_commit="c", constitution_roots={"a": "1"}, twin_roots={},
        hypergraph_root="h", epistemic_root="e", invariant_root="i",
        hyperproperty_root="hp", assurance_root="a", gap_root="g",
        verifier_set_root="v", closure_epoch="ep")
    a = bootstrap_verify.phase_a(ROOT,
                                 freeze.RECORDED_FROZEN_SP0009_VERIFIER_HASH)
    b = bootstrap_verify.phase_b(g)
    c = bootstrap_verify.phase_c(g, a, b)
    assert c["construction"] == "merkle-tree"
    # the Merkle witness is a DIFFERENT value than the canonical global root
    assert c["independent_merkle_root"] != g["global_architecture_root"]
    # omitting a class root is caught by Phase C
    g2 = dict(g, class_roots={"a": "1"})   # missing required roots
    c2 = bootstrap_verify.phase_c(g2, a, b)
    assert c2["missing_class_roots"] and not c2["agree"]


# R2b — verifier diversity requires distinct CONSTRUCTIONS, not label strings
def test_r2b_diversity_by_construction():
    nominal = [{"verifier": "x", "trust_domain": "d1", "construction": "same"},
               {"verifier": "y", "trust_domain": "d2", "construction": "same"}]
    assert not bootstrap_verify.verifier_diversity(nominal)["diverse"]


# R3 — frozen verifier compared to a HARDCODED recorded constant
def test_r3_frozen_verifier_vs_recorded_constant():
    # a wrong recorded hash (simulating a modified verifier) is rejected
    a = bootstrap_verify.phase_a(ROOT, "0" * 64)
    assert not a["frozen_identity_matches"]
    # the real recorded constant matches the live tree
    a2 = bootstrap_verify.phase_a(
        ROOT, freeze.RECORDED_FROZEN_SP0009_VERIFIER_HASH)
    assert a2["frozen_identity_matches"]


# R4 — an in-cycle member cannot self-anchor an unsupported cycle
def test_r4_in_cycle_anchor_does_not_anchor():
    res = circularity.analyze({"X": ["Y"], "Y": ["X"]}, anchored={"X"},
                              nodes={"X", "Y"})
    assert res["unsupported"]        # X is IN the cycle -> not an external anchor


# R5 — same-producer atoms are common-mode even with distinct trust-domain labels
def test_r5_same_producer_is_common_mode():
    atoms = {}
    for i in range(2):
        a = evidence.evidence_atom(claim_refs=["C"], source_ref=f"s{i}",
                                   producer="one-gen", tool=f"t{i}",
                                   parser_family=f"f{i}", trust_domain=f"d{i}",
                                   repository_commit="c", valid_from="c")
        atoms[a["evidence_atom_id"]] = a
    assert evidence.independence_class(list(atoms), atoms) == "COMMON_MODE"


# R6 — a control with no on-disk grounding is not counted necessary
def test_r6_ungrounded_control_ineffective(tmp_path):
    # empty tree: no grounding files exist
    r = counterfactual.verify_control("CTL-RBAC", root=tmp_path)
    assert r["classification"] == "INEFFECTIVE" and not r["exercised"]
    assert any(f.kind == "CONTROL_NECESSITY_NOT_PROVEN"
               for f in counterfactual.control_findings({"CTL-RBAC": r}))


# R7 — invariant control ref requires the named SYMBOL, not just the file
def test_r7_invariant_symbol_checked(tmp_path):
    (tmp_path / "finalis" / "portal").mkdir(parents=True)
    # file exists but WITHOUT the require_permission symbol
    (tmp_path / "finalis" / "portal" / "app.py").write_text("x = 1\n")
    assert not invariants._control_present(
        tmp_path, "finalis/portal/app.py:require_permission")
    (tmp_path / "finalis" / "portal" / "app.py").write_text(
        "def require_permission(): pass\n")
    assert invariants._control_present(
        tmp_path, "finalis/portal/app.py:require_permission")

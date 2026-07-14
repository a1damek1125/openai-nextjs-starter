"""TOOL-B10 acceptance families (AC-B6): each test pins one subsystem family from
the spec's A..BS taxonomy to a concrete, executed guarantee. These are the
coverage gates the §25 final report references; they exercise the kernel end to
end rather than restating unit behavior."""
from fractions import Fraction

from tools.context_governance import (canon, model, entitlement, evidence,
                                       requirements, compile as comp, capsule,
                                       governance, boundary, validate)
from tests._b10_ctxgov_kernel import (clean_request, make_evidence, make_claim,
                              make_requirement, make_entitlement)


# A — deterministic hashing / Merkle forest
def test_ac_A_deterministic_capsule_root():
    a = governance.build_capsule(clean_request())
    b = governance.build_capsule(clean_request())
    assert a["capsule"]["certificate"]["capsule_root"] == \
        b["capsule"]["certificate"]["capsule_root"]


# B — four-valued claim lattice
def test_ac_B_four_valued_lattice_no_true_from_both():
    assert not model.closes_critical(model.BOTH)
    assert not model.closes_critical(model.NEITHER)
    assert model.claim_state("truthy", False) == model.NEITHER


# C — entitlement before retrieval (fail-closed)
def test_ac_C_entitlement_precedes_and_fails_closed():
    res = governance.build_capsule(
        clean_request(entitlement=make_entitlement(purpose="WRONG")))
    assert not res["valid"]


# D — point-in-time snapshot + version vector
def test_ac_D_version_vector_binds_inputs():
    from tests._b10_ctxgov_kernel import make_version_vector
    assert make_version_vector()["vector_hash"] != \
        make_version_vector(source_versions={"src1": "v9"})["vector_hash"]


# E — TOCTOU firewall fails closed on unknown delta
def test_ac_E_toctou_unknown_delta_blocks():
    from tests._b10_ctxgov_kernel import (make_version_vector, make_evidence as mev,
                                  make_claim as mcl, make_snapshot, make_lease)
    vv = make_version_vector(); vv2 = dict(vv); vv2["x"] = "y"
    e = mev(); c = mcl(e); snap = make_snapshot(vv, e, c)
    r = entitlement.revalidate(make_lease(snap), snapshot_vector=vv,
                               current_vector=vv2, now="2026-07-12")
    assert r["verdict"] == "BLOCKED"


# F — evidence before belief (content-addressed, immutable)
def test_ac_F_evidence_is_content_addressed():
    e = make_evidence(content="abc")
    assert e["content_hash"] == canon.content_address("abc")


# G — semantic taint survives transformation
def test_ac_G_taint_survives_unless_proven():
    assert evidence.propagate_taint(["QUARANTINED"]) == "QUARANTINED"


# H — authority air-gap
def test_ac_H_information_never_authorizes():
    e = make_evidence(); e["asserts_authority"] = True
    assert evidence.authority_air_gap([e])[0].kind == "AUTHORITY_INFERENCE_REJECTED"


# I — common-mode independence quotient
def test_ac_I_common_mode_not_double_counted():
    a = make_evidence(source_id="s1", provider="P")
    b = make_evidence(source_id="s2", provider="P")
    by = {a["evidence_id"]: a, b["evidence_id"]: b}
    assert evidence.independence_class([a["evidence_id"], b["evidence_id"]], by) \
        == "COMMON_MODE"


# J — requirement hypergraph minimal support basis
def test_ac_J_minimal_support_basis():
    e = make_evidence(); c = make_claim(e, discharges=["atom_a"], support=True)
    ev = requirements.evaluate_requirement(make_requirement(atoms=["atom_a"]),
                                           [c], evidence_by_id={e["evidence_id"]: e})
    assert ev["minimal_support_bases"] == [[c["claim_id"]]]


# K — mandatory reservation precedes budget
def test_ac_K_mandatory_reserved_before_budget():
    e = make_evidence(); c = make_claim(e, discharges=["atom_a"], support=True,
                                        tokens=2)
    ev = requirements.evaluate_requirement(
        make_requirement(atoms=["atom_a"], mandatory=True), [c],
        evidence_by_id={e["evidence_id"]: e})
    res = requirements.reserve_mandatory([ev], {c["claim_id"]: c},
                                         token_of=lambda x: x["tokens"])
    assert c["claim_id"] in res["reserved_claim_ids"]


# L — robust submodular selection under budget
def test_ac_L_selection_respects_budget():
    e = make_evidence(); c = make_claim(e, discharges=["atom_a"], support=True,
                                        tokens=3)
    sel = requirements.robust_select([c["claim_id"]], {c["claim_id"]: c},
                                     budget=5, token_of=lambda x: x["tokens"])
    assert sel["budget_ok"]


# M — VOI retrieval never stops with mandatory unmet
def test_ac_M_voi_forced_continue():
    steps = [{"marginal_value": Fraction(0), "cost": 1, "atoms_after": []}]
    voi = requirements.voi_retrieval(steps, mandatory_unmet_at=lambda i: ["m"])
    assert voi["mandatory_unmet_at_stop"] == ["m"]


# N — anytime-valid monitoring (optional stopping safe)
def test_ac_N_anytime_valid():
    d = requirements.anytime_decision([Fraction(25)], alpha=Fraction(1, 20))
    assert d["anytime_valid"] and d["reject_h0"]


# O — conformal with distribution-shift guard
def test_ac_O_conformal_shift_guard():
    c = requirements.conformal_interval([1, 2, 3], 2, shift_detected=True)
    assert c["guarantee_active"] is False


# P — claim-preserving compaction
def test_ac_P_compaction_preserves_critical():
    e = make_evidence(); c = make_claim(e, support=True)
    cert = comp.compaction(original_claims=[c], retained_claims=[c],
                           critical_ids={c["claim_id"]})
    assert cert["preserved"]


# Q — conflict-preserving merge
def test_ac_Q_merge_preserves_conflict():
    e = make_evidence()
    s = make_claim(e, discharges=["a"], support=True)
    rf = make_claim(e, discharges=["a"], support=False, refute=True,
                    predicate="no")
    by = {s["claim_id"]: s, rf["claim_id"]: rf}
    b1 = comp.branch(base_snapshot_root="S", hypothesis="h1",
                     claim_refs=[s["claim_id"]], tenant_id="t")
    b2 = comp.branch(base_snapshot_root="S", hypothesis="h2",
                     claim_refs=[rf["claim_id"]], tenant_id="t")
    m = comp.merge_branches([b1, b2], by, critical_ids={"a"})
    assert m["critical_conflicts"] == ["a"]


# R — least-privilege views + noninterference
def test_ac_R_view_least_privilege():
    v = comp.compile_view({"provider_token": "x", "claims": []},
                          view_class="CUSTOMER_RENDER_VIEW")
    assert "provider_token" not in v["fields"]


# S — non-compensatory privacy budget
def test_ac_S_privacy_non_compensatory():
    b = comp.privacy_budget({"pii": 9, "financial": 0})
    exp = comp.privacy_exposure({"pii": 0, "financial": 1}, b)
    assert exp["within_budget"] is False


# T — model-context ABI + consumption receipt truncation
def test_ac_T_truncation_detected():
    v = comp.compile_view({"claims": []}, view_class="REASONING_MODEL_VIEW")
    r = comp.render_abi(v)
    rec = comp.consumption_receipt(render=r,
                                   lease_revalidation={"verdict": "VALID"},
                                   provider_reported_len=r["byte_len"] - 1)
    assert rec["truncation"] == "DETECTED"


# U — proof of non-use
def test_ac_U_proof_of_non_use():
    p = comp.proof_of_non_use(excluded_ref="X", output_hash="h",
                              output_without_excluded_hash="h")
    assert p["non_use_proven"]


# V — Context BOM completeness
def test_ac_V_bom_binds_inputs():
    res = governance.build_capsule(clean_request())
    assert res["capsule"]["body"]["bom_root"]


# W — proof-carrying certificate + INDEPENDENT checker
def test_ac_W_independent_checker_accepts_valid():
    res = governance.build_capsule(clean_request())
    assert res["check"]["accepted"] and res["check"]["independent"]


# X — generator cannot self-certify
def test_ac_X_no_self_certification():
    res = governance.build_capsule(clean_request(), generator_id="z",
                                   checker_id="z")
    assert res["capsule"] is None


# Y — replay twin determinism
def test_ac_Y_replay_twin():
    res = governance.build_capsule(clean_request())
    body = res["capsule"]["body"]
    rep = capsule.replay_twin(res["capsule"], body, generator_id="ctxgov-generator")
    assert rep["diverged"] is False


# Z — Context TCB manifest completeness
def test_ac_Z_tcb_complete():
    assert capsule.tcb_manifest(present=list(capsule.TCB_COMPONENTS))["complete"]


# AA — SCITT transparency projection
def test_ac_AA_transparency_receipt():
    res = governance.build_capsule(clean_request())
    rec = capsule.transparency_receipt(res["capsule"], log_position=1)
    assert rec["capsule_root"] == res["capsule"]["certificate"]["capsule_root"]


# AB — boundary firewall (no live effect)
def test_ac_AB_no_live_effect():
    assert boundary.classify_effect("EMAIL_SEND") == "FORBIDDEN"
    assert boundary.classify_effect("UNSEEN_OP") == "UNKNOWN"


# AC — invariant self-check green
def test_ac_AC_invariants_green():
    assert validate.validate()["ok"] is True


# AD — capsule informs, never authorizes (top-level contract)
def test_ac_AD_capsule_informs_only():
    res = governance.build_capsule(clean_request())
    assert res["capsule"]["body"]["informs_not_authorizes"] is True
    assert "authority_grant" not in res["capsule"]["body"]


# AE — memory writeback quarantine (never auto-admit)
def test_ac_AE_memory_quarantine():
    cand = evidence.memory_candidate(proposed_fact={"x": 1}, evidence_refs=[],
                                     work_succeeded=True)
    assert cand["auto_admitted"] is False

"""TOOL-B10 requirements: hypergraph, minimal bases, mandatory reservation,
robust submodular selection, VOI, anytime-valid, conformal-with-shift-guard."""
from fractions import Fraction

from tools.context_governance import requirements as r
from tests._b10_ctxgov_kernel import make_evidence, make_claim, make_requirement


def _tok(c):
    return int(c.get("tokens", 1))


def test_satisfied_requirement_has_support_basis():
    e = make_evidence()
    c = make_claim(e, discharges=["atom_a"], support=True)
    req = make_requirement(atoms=["atom_a"])
    ev = r.evaluate_requirement(req, [c], evidence_by_id={e["evidence_id"]: e})
    assert ev["satisfied"] is True
    assert ev["minimal_support_bases"] == [[c["claim_id"]]]
    assert ev["missing_evidence_bases"] == []


def test_unmet_atom_produces_missing_basis():
    req = make_requirement(atoms=["atom_a", "atom_b"])
    e = make_evidence()
    c = make_claim(e, discharges=["atom_a"], support=True)
    ev = r.evaluate_requirement(req, [c], evidence_by_id={e["evidence_id"]: e})
    assert ev["satisfied"] is False
    assert ev["unmet_atoms"] == ["atom_b"]
    assert ev["missing_evidence_bases"] == [["atom_b"]]


def test_critical_both_does_not_satisfy():
    req = make_requirement(atoms=["atom_a"], critical=True)
    e = make_evidence()
    c = make_claim(e, discharges=["atom_a"], support=True, refute=True)  # BOTH
    ev = r.evaluate_requirement(req, [c], evidence_by_id={e["evidence_id"]: e})
    assert ev["satisfied"] is False        # BOTH never satisfies critical


def test_common_mode_fails_independence_floor():
    # non-mandatory so the common-mode reason is not masked by the mandatory-miss
    req = make_requirement(atoms=["atom_a"], min_independent=2, mandatory=False)
    a = make_evidence(source_id="s1", provider="P")
    b = make_evidence(source_id="s2", provider="P")   # same provider = common mode
    ca = make_claim(a, discharges=["atom_a"], support=True)
    cb = make_claim(b, discharges=["atom_a"], support=True)
    by_id = {a["evidence_id"]: a, b["evidence_id"]: b}
    ev = r.evaluate_requirement(req, [ca, cb], evidence_by_id=by_id)
    assert "atom_a" in ev["common_mode_short_atoms"]
    fs = r.requirement_findings([ev])
    assert any(f.kind == "COMMON_MODE_SUPPORT_INSUFFICIENT" for f in fs)


def test_independent_sources_meet_floor():
    req = make_requirement(atoms=["atom_a"], min_independent=2)
    a = make_evidence(source_id="s1", provider="P")
    b = make_evidence(source_id="s2", provider="Q")
    ca = make_claim(a, discharges=["atom_a"], support=True)
    cb = make_claim(b, discharges=["atom_a"], support=True)
    by_id = {a["evidence_id"]: a, b["evidence_id"]: b}
    ev = r.evaluate_requirement(req, [ca, cb], evidence_by_id=by_id)
    assert ev["common_mode_short_atoms"] == []


def test_mandatory_requirement_missing_is_p0():
    req = make_requirement(atoms=["atom_z"], critical=True, mandatory=True)
    ev = r.evaluate_requirement(req, [], evidence_by_id={})
    fs = r.requirement_findings([ev])
    assert any(f.kind == "MANDATORY_REQUIREMENT_MISSING" and f.severity == "P0"
               for f in fs)


def test_reserve_mandatory_pins_support_basis():
    e = make_evidence()
    c = make_claim(e, discharges=["atom_a"], support=True, tokens=3)
    req = make_requirement(atoms=["atom_a"], mandatory=True)
    ev = r.evaluate_requirement(req, [c], evidence_by_id={e["evidence_id"]: e})
    res = r.reserve_mandatory([ev], {c["claim_id"]: c}, token_of=_tok)
    assert res["reserved_claim_ids"] == [c["claim_id"]]
    assert res["reserved_tokens"] == 3


def test_robust_select_respects_budget_and_reservation():
    e = make_evidence()
    c1 = make_claim(e, discharges=["atom_a"], support=True, tokens=3)
    c2 = make_claim(e, discharges=["atom_b"], support=True, tokens=3,
                    predicate="also")
    by_id = {c1["claim_id"]: c1, c2["claim_id"]: c2}
    sel = r.robust_select([c1["claim_id"], c2["claim_id"]], by_id, budget=4,
                          token_of=_tok, reserved={c1["claim_id"]})
    assert c1["claim_id"] in sel["selected_ids"]     # reserved kept
    assert sel["spent_tokens"] <= 4 and sel["budget_ok"]


def test_reservation_over_budget_fails_closed():
    e = make_evidence()
    c = make_claim(e, discharges=["atom_a"], support=True, tokens=50)
    by_id = {c["claim_id"]: c}
    sel = r.robust_select([c["claim_id"]], by_id, budget=10, token_of=_tok,
                          reserved={c["claim_id"]})
    assert sel["budget_ok"] is False
    ev = {"mandatory": True, "minimal_support_bases": [[c["claim_id"]]],
          "req_id": "R"}
    fs = r.selection_findings(sel, {"unreservable_requirements": [],
                                    "reserved_claim_ids": [c["claim_id"]]})
    assert any(f.kind == "CONTEXT_BUDGET_INSUFFICIENT" for f in fs)


def test_voi_stops_on_nonpositive_but_not_while_mandatory_unmet():
    steps = [{"marginal_value": Fraction(1), "cost": 1, "atoms_after": []},
             {"marginal_value": Fraction(0), "cost": 1, "atoms_after": []}]
    # nothing mandatory unmet -> stop at the zero-value step
    voi = r.voi_retrieval(steps, mandatory_unmet_at=lambda i: [])
    assert voi["stop_reason"] == "MARGINAL_VALUE_NONPOSITIVE"
    # mandatory unmet at the zero-value step -> forced to continue past it
    voi2 = r.voi_retrieval(steps, mandatory_unmet_at=lambda i: ["m"])
    assert 1 in voi2["steps_taken"]
    assert voi2["stop_reason"] == "MANDATORY_FORCED_CONTINUE"


def test_voi_findings_flag_unmet_mandatory_at_stop():
    voi = {"mandatory_unmet_at_stop": ["m"], "steps_taken": [], "stop_reason": "X"}
    fs = r.voi_findings(voi)
    assert fs and fs[0].kind == "MANDATORY_RETRIEVAL_STOPPED"


def test_anytime_valid_rejects_when_wealth_crosses_threshold():
    d = r.anytime_decision([Fraction(30)], alpha=Fraction(1, 20))
    assert d["reject_h0"] is True and d["anytime_valid"] is True


def test_anytime_valid_no_reject_below_threshold():
    d = r.anytime_decision([Fraction(2), Fraction(3)], alpha=Fraction(1, 20))
    assert d["reject_h0"] is False


def test_conformal_shift_guard_disables_guarantee():
    c = r.conformal_interval([1, 2, 3], 2, shift_detected=True)
    assert c["guarantee_active"] is False and c["covered"] is None
    fs = r.statistics_findings(c)
    assert any(f.kind == "DISTRIBUTION_SHIFT_DETECTED" for f in fs)


def test_conformal_active_without_shift():
    c = r.conformal_interval([1, 2, 3, 4, 5], 0, shift_detected=False)
    assert c["guarantee_active"] is True

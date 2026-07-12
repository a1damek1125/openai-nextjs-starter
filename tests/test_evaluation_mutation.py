"""SP0011 — mutation campaign + red-team regression locks (§20).

Each test injects a defect the evaluation MUST reject (a false qualification path)
and asserts the fail-closed discipline kills it. Covers the §20 mutation classes:
credits without evidence/maturity/certificate, failed-gate ignored, score without
maturity/envelope, score>1000, PARTIAL/UNKNOWN as success, judge-as-sole-critical-
oracle, low-fidelity promotion, zero-failure-as-zero-risk, association-as-causal,
confidence-as-authority, omitted genome roots, fabricated 1000/1000 & production.
"""
from __future__ import annotations

from pathlib import Path

from tools.evaluation import (model, credits, score, hardgates, oracles,
                              fidelity, causal, calibration, statistics,
                              genome, claims, canon, evaluation, contamination)

ROOT = Path(__file__).resolve().parents[1]


def _base_cert(**over):
    d = dict(claim_id="C", configuration_root="CFG", program_seal="SEAL",
             evidence_refs=["e"], evidence_domain_refs=["d"],
             oracle_certificate_refs=["o"], statistical_certificate_ref=None,
             required_maturity="M1", achieved_maturity="M1",
             hard_gate_results={"g": True}, valid_from="t", valid_until=None,
             defeater_refs=[], kernel_version="k", evidence_current=True,
             evidence_present=True, evidence_refuted=False,
             statistical_required=False, statistical_pass=True, oracle_valid=True)
    d.update(over)
    return credits.issue_certificate(**d)


def _gt(**over):
    d = {"claim_id": "C", "required_maturity": "M1", "achieved_maturity": "M1",
         "evidence_present": True, "evidence_current": True,
         "evidence_refuted": False, "oracle_valid": True, "statistical_ok": True,
         "hard_gate_pass": True, "defeater_refs": []}
    d.update(over)
    return d


def _check(cert, gt=None):
    return credits.check_certificate(cert, expected_configuration_root="CFG",
                                     expected_program_seal="SEAL",
                                     ground_truth=gt or _gt())


# 1-4: missing / stale / refuted / invalid evidence awards zero (ground truth)
def test_missing_evidence_awards_zero():
    assert not _check(_base_cert(), _gt(evidence_present=False))["awarded"]


def test_stale_evidence_awards_zero():
    assert not _check(_base_cert(), _gt(evidence_current=False))["awarded"]


def test_refuted_evidence_awards_zero():
    assert not _check(_base_cert(), _gt(evidence_refuted=True))["awarded"]


def test_forged_certificate_cannot_beat_ground_truth():
    # P0-1: a cert with inflated self-reported fields is rejected because the
    # kernel awards against its OWN ground truth, not the cert.
    c = _base_cert(achieved_maturity="M5", required_maturity="M1")
    assert not _check(c, _gt(achieved_maturity="M1", required_maturity="M3"))[
        "awarded"]


# 5: failed hard gate ignored
def test_failed_hard_gate_blocks_credit():
    assert not _check(_base_cert(), _gt(hard_gate_pass=False))["awarded"]


def test_failed_gate_blocks_official_score():
    hg = hardgates.evaluate_hard_gates(
        program_seal_ok=True, p0=1, p1=0, integrity_clean=True,
        contamination_clean=True, no_fabricated_evidence=True, oracles_valid=True,
        no_sole_llm_judge_critical=True, no_low_fidelity_promotion=True,
        adaptive_logged=True, no_hidden_weak_stratum=True,
        critical_claims_state={"tenant_isolation": "PASS",
                               "authority_conservation": "PASS", "consent": "PASS",
                               "protected_effect_approval": "PASS",
                               "no_unresolved_outcome": True,
                               "no_calibration_failure": True},
        sp0010_admitted=True, no_critical_unknown_as_pass=True,
        no_out_of_scope_statistical_cert=True, no_stale_critical_credit=True,
        evaluation_seal_will_be_valid=True)
    sc = score.compute_score(
        claims={"C": {"domain_id": "D1"}},
        awards={"C": {"awarded": True, "credits": 5}}, hard_gate_result=hg,
        configuration_id="cfg", program_seal="s", evaluation_seal=None,
        sealed_at="t", valid_until=None, envelope_ref="e", achieved_maturity="M1",
        open_blockers=[], open_production_gaps=[])
    assert sc["total_credits"] == 0     # non-compensatory


# 6-8: score without maturity / envelope; score > 1000
def test_score_over_1000_rejected():
    sc = {"diagnostic_total_credits": 1005, "total_credits": 1005,
          "official_score_blocked_by_gate": False, "maturity": "M1",
          "hard_gate_state": "PASS", "qualification_envelope_ref": "e"}
    fs = score.verify_score_arithmetic(sc, {f"c{i}": {"awarded": True}
                                            for i in range(201)})
    assert any(f.kind == "SCORE_ARITHMETIC_INVALID" for f in fs)


def test_score_without_maturity_rejected():
    sc = {"diagnostic_total_credits": 0, "total_credits": 0,
          "official_score_blocked_by_gate": False, "maturity": "",
          "hard_gate_state": "PASS", "qualification_envelope_ref": "e"}
    assert any(f.kind == "SCORECARD_INVALID"
               for f in score.verify_score_arithmetic(sc, {}))


# 10-11: partial / unknown as success
def test_partial_is_not_success():
    assert not model.is_success("PARTIAL")


def test_unknown_is_not_success():
    assert not model.is_success("UNKNOWN")


# 13-14: deterministic oracle bypass / judge sole critical
def test_llm_judge_cannot_solely_close_critical():
    fs = oracles.critical_oracle_findings({"C": ["LLM_JUDGE", "AGENT_AS_JUDGE"]})
    assert any(f.kind == "CRITICAL_LLM_JUDGE_SOLE" for f in fs)


# 43: low-fidelity evidence promoted to higher maturity
def test_low_fidelity_promotion_rejected():
    assert fidelity.promotion_allowed("UNIT", "M5") is False
    fs = fidelity.fidelity_findings(
        plan={"critical_omitted": [], "all_probabilities_logged": True},
        low_fidelity_promotions=["C"])
    assert any(f.kind == "LOW_FIDELITY_EVIDENCE_PROMOTION" for f in fs)


# 33: zero failures labeled zero risk
def test_zero_failure_not_zero_risk():
    z = statistics.zero_failure_upper_bound(500)
    assert z["failure_rate_upper_bound"] > 0
    assert z["zero_risk_claimed"] is False


# 35: causal association labeled causal
def test_association_not_labeled_causal():
    r = causal.attribute(outcome_ref="o", treatment_component="t",
                         reference_configuration="a", candidate_configuration="b",
                         design="OBSERVATIONAL", observed_confounders=[],
                         known_confounders=["x"], effect_estimate=0.5)
    assert r["state"] == "ASSOCIATIONAL_ONLY" and r["effect_estimate"] is None


# 36: confidence creates authority
def test_confidence_cannot_create_authority():
    fs = calibration.calibration_findings(
        {"reliability_curve": {"expected_calibration_error": 0.0}},
        confidence_as_authority=True)
    assert any(f.kind == "CONFIDENCE_AS_AUTHORITY" for f in fs)


# 41: adaptive selector removes critical scenario
def test_adaptive_cannot_omit_critical():
    plan = fidelity.adaptive_plan(mandatory_covered=True, candidates=[
        {"scenario_ref": "s", "mandatory_critical": True, "selection_prob": 0.5}])
    # a mandatory-critical candidate always gets probability 1.0
    assert plan["selections"][0]["selection_probability"] == 1.0


# 48-49: omitted genome roots
def test_omitted_credit_root_moves_genome():
    full = genome.build_genome({k: str(i) for i, k in
                                enumerate(genome.REQUIRED_ROOTS)})
    dropped = dict(full["class_roots"])
    dropped["credit_certificate_root"] = "ABSENT"
    g2 = genome.build_genome(dropped)
    assert g2["global_evaluation_root"] != full["global_evaluation_root"]


# 52-54: fabricated 1000/1000, production, blanket approval
def test_no_fabricated_1000(twin=None):
    t = evaluation.build_evaluation(ROOT)
    assert t["scorecard"]["total_credits"] < 1000
    assert t["finalis_1000_state"] != "FINALIS_PRODUCT_1000_QUALIFIED"


def test_no_production_readiness_claimed():
    t = evaluation.build_evaluation(ROOT)
    assert t["product_state"] == "NOT_PRODUCTION_READY"
    assert t["maturity"] in ("M0", "M1")   # never M4/M5 without field/prod evidence


def test_blanket_permanent_approval_rejected():
    from tools.evaluation import scenarios
    # a scoped reusable approval MUST carry expiry + revocation (not blanket)
    assert "expiry" in scenarios.REUSABLE_APPROVAL_BINDING
    assert "revocation" in scenarios.REUSABLE_APPROVAL_BINDING


# integrity: evaluator immutability + metric reconciliation
def test_evaluator_tampering_detected():
    m = contamination.build_ledger(ROOT)
    m2 = dict(m)
    m2["evaluator_immutability"] = {"all_present": False}
    m2["answer_exposures"] = []
    fs = contamination.contamination_findings(m2)
    assert any(f.kind == "EVALUATOR_TAMPERING" for f in fs)


# P1-2: a rewritten scorer (pinned-hash mismatch) is detected, not just deletion
def test_pinned_asset_mismatch_detected():
    m = contamination.build_ledger(ROOT)
    m2 = dict(m)
    m2["evaluator_immutability"] = {"all_present": True,
                                    "mismatched_pins": ["tools/evaluation/score.py"]}
    m2["answer_exposures"] = []
    assert any(f.kind == "EVALUATOR_TAMPERING"
               for f in contamination.contamination_findings(m2))


# P1-3: UNKNOWN contamination is fail-closed (does not silently pass)
def test_unknown_contamination_blocks():
    m = contamination.build_ledger(ROOT)
    m2 = dict(m)
    m2["answer_exposures"] = []
    m2["unknown_classes"] = ["RUN-CRIT-1"]
    fs = contamination.contamination_findings(m2)
    assert any(f.kind == "CONTAMINATION_UNKNOWN" and f.severity == model.P0
               for f in fs)

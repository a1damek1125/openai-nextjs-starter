"""SP0011 Evaluation Kernel — core invariants.

Pins the load-bearing properties: the 10×20×5=1000 accounting, the maturity
ladder (never auto-promoted), the proof-carrying credit certificate + independent
kernel checker (a certificate without valid obligations/config/seal awards zero),
the non-compensatory hard gates, score arithmetic (<=1000, blocked on gate fail),
outcome strictness (PARTIAL/UNKNOWN != SUCCESS), the oracle hierarchy, the genome/
seal reproduction, determinism, the change boundary, and the TRUTHFUL sub-1000
score at maturity M1.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.evaluation import (canon, model, admit, freeze, configuration, tcb,
                              kernel, claims, credits, hardgates, score,
                              genome, oracles, boundary, evaluation, validate)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def twin():
    return evaluation.build_evaluation(ROOT)


# --- canon / accounting ------------------------------------------------------
def test_canonical_and_accounting():
    assert canon.canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert model.CLAIM_COUNT == 200
    assert model.MAX_CREDITS == 1000
    assert model.DOMAIN_COUNT == 10 and model.CLAIMS_PER_DOMAIN == 20


def test_maturity_ladder_no_auto_promote():
    assert model.maturity_meets("M1", "M1")
    assert model.maturity_meets("M3", "M1")
    assert not model.maturity_meets("M1", "M3")   # M1 never satisfies M3
    assert not model.maturity_meets("BOGUS", "M1")


def test_outcome_strictness():
    assert model.is_success("SUCCESS")
    for o in ("PARTIAL", "UNKNOWN", "FAILURE", "success"):
        assert not model.is_success(o)


# --- program dependency + freeze + boundary ----------------------------------
def test_sp0010_admitted():
    adm = admit.admit_program_seal(ROOT)
    assert adm["admitted"] is True
    assert adm["admission_state"] == "ADMITTED_PENDING_EXECUTION"
    assert admit.admission_findings(adm) == []


def test_freeze_frontier_v27():
    frz = freeze.freeze(ROOT)
    assert frz["migration_frontier"] == 27
    assert freeze.check_frozen(frz, ROOT) == []


def test_boundary_clean():
    assert boundary.check_boundary(ROOT) == []


# --- configuration identity --------------------------------------------------
def test_configuration_material_change_moves_root():
    cfg = configuration.build_configuration(ROOT)
    base = cfg["configuration_root"]
    changed = {**cfg, "model_identity": {"provider": "OTHER"}}
    assert configuration.configuration_root(changed) != base


# --- TCB + kernel ------------------------------------------------------------
def test_tcb_complete_and_kernel_smaller_than_stack():
    man = tcb.build_manifest(ROOT)
    assert man["complete"] is True
    assert man["member_count"] < man["member_count"] + man["untrusted_count"]
    assert set(man["minimal_trusted_kernel"]) <= set(man["members"])
    assert tcb.tcb_findings(man) == []


def test_kernel_identity_deterministic():
    assert kernel.kernel_identity(ROOT)["kernel_root"] == \
        kernel.kernel_identity(ROOT)["kernel_root"]


# --- claims ------------------------------------------------------------------
def test_exactly_200_claims_10x20():
    c = claims.build_claims(ROOT)
    assert claims.validate_counts(c) == []
    assert len(c) == 200


def test_domain_grounding_gives_m1():
    c = claims.build_claims(ROOT)
    # D10 auditability is fully repository-grounded => M1 achieved
    assert c["D10-C01-evidence-provenance"]["achieved_maturity"] == "M1"


# --- proof-carrying credit certificate + kernel checker ----------------------
def _cert(claim, cfg_root, seal, gate_pass=True):
    return credits.issue_certificate(
        claim_id=claim["claim_id"], configuration_root=cfg_root,
        program_seal=seal, evidence_refs=["repo:x"], evidence_domain_refs=["d"],
        oracle_certificate_refs=["ORA-DET-STATE"], statistical_certificate_ref=None,
        required_maturity=claim["required_maturity"],
        achieved_maturity=claim["achieved_maturity"],
        hard_gate_results={"applicable": gate_pass}, valid_from="t",
        valid_until=None, defeater_refs=[], kernel_version="k",
        evidence_current=True, evidence_present=True, evidence_refuted=False,
        statistical_required=False, statistical_pass=True, oracle_valid=True)


def test_valid_certificate_awards_five():
    c = claims.build_claims(ROOT)
    m1 = c["D10-C01-evidence-provenance"]
    cert = _cert(m1, "CFG", "SEAL")
    v = credits.check_certificate(cert, expected_configuration_root="CFG",
                                  expected_program_seal="SEAL")
    assert v["awarded"] and v["credits"] == 5


def test_certificate_config_mismatch_awards_zero():
    c = claims.build_claims(ROOT)
    cert = _cert(c["D10-C01-evidence-provenance"], "CFG", "SEAL")
    v = credits.check_certificate(cert, expected_configuration_root="WRONG",
                                  expected_program_seal="SEAL")
    assert not v["awarded"] and v["credits"] == 0
    assert any("configuration_root mismatch" in p for p in v["problems"])


def test_certificate_forged_hash_rejected():
    c = claims.build_claims(ROOT)
    cert = _cert(c["D10-C01-evidence-provenance"], "CFG", "SEAL")
    cert["achieved_maturity"] = "M5"    # tamper without re-hashing
    v = credits.check_certificate(cert, expected_configuration_root="CFG",
                                  expected_program_seal="SEAL")
    assert not v["awarded"]
    assert any("hash" in p for p in v["problems"])


def test_unmet_maturity_awards_zero():
    c = claims.build_claims(ROOT)
    m3 = c["D3-C15-prompt-injection-resistance"]  # required M3, achieved M1
    cert = _cert(m3, "CFG", "SEAL")
    v = credits.check_certificate(cert, expected_configuration_root="CFG",
                                  expected_program_seal="SEAL")
    assert not v["awarded"]     # maturity insufficient


def test_failed_hard_gate_in_cert_awards_zero():
    c = claims.build_claims(ROOT)
    cert = _cert(c["D10-C01-evidence-provenance"], "CFG", "SEAL",
                 gate_pass=False)
    v = credits.check_certificate(cert, expected_configuration_root="CFG",
                                  expected_program_seal="SEAL")
    assert not v["awarded"]


# --- hard gates --------------------------------------------------------------
def test_hard_gate_non_compensatory():
    r = hardgates.evaluate_hard_gates(
        program_seal_ok=True, p0=0, p1=0, integrity_clean=True,
        contamination_clean=True, no_fabricated_evidence=True, oracles_valid=True,
        no_sole_llm_judge_critical=True, no_low_fidelity_promotion=True,
        adaptive_logged=True, no_hidden_weak_stratum=True,
        critical_claims_state={"tenant_isolation": "PASS",
                               "authority_conservation": "PASS", "consent": "PASS",
                               "protected_effect_approval": "PASS"})
    assert r["overall_pass"] is True
    bad = hardgates.evaluate_hard_gates(
        program_seal_ok=True, p0=1, p1=0, integrity_clean=True,
        contamination_clean=True, no_fabricated_evidence=True, oracles_valid=True,
        no_sole_llm_judge_critical=True, no_low_fidelity_promotion=True,
        adaptive_logged=True, no_hidden_weak_stratum=True,
        critical_claims_state={"tenant_isolation": "PASS",
                               "authority_conservation": "PASS", "consent": "PASS",
                               "protected_effect_approval": "PASS"})
    assert bad["overall_pass"] is False and "P0_ZERO" in bad["failed"]


# --- oracle hierarchy --------------------------------------------------------
def test_deterministic_oracle_outranks_judge():
    assert oracles.select_oracle(["LLM_JUDGE", "DETERMINISTIC"]) == "DETERMINISTIC"
    assert oracles.select_oracle(["LLM_JUDGE", "AGENT_AS_JUDGE"]) == \
        "AGENT_AS_JUDGE"


def test_critical_claim_needs_non_judge_oracle():
    fs = oracles.critical_oracle_findings({"C": ["LLM_JUDGE"]})
    assert any(f.kind == "CRITICAL_LLM_JUDGE_SOLE" and f.severity == model.P0
               for f in fs)
    assert oracles.critical_oracle_findings({"C": ["DETERMINISTIC"]}) == []


def test_outcome_classification_strict():
    assert oracles.classify_outcome(activity_done=True, effect_achieved=True,
                                    outcome_verified=True,
                                    completion_condition_met=True,
                                    evidence_present=True) == "SUCCESS"
    assert oracles.classify_outcome(activity_done=True, effect_achieved=True,
                                    outcome_verified=False,
                                    completion_condition_met=False,
                                    evidence_present=True) == "PARTIAL"
    assert oracles.classify_outcome(activity_done=True, effect_achieved=True,
                                    outcome_verified=True,
                                    completion_condition_met=True,
                                    evidence_present=False) == "UNKNOWN"


# --- score + genome + seal + determinism -------------------------------------
def test_truthful_sub_1000_m1_score(twin):
    assert twin["counts"]["awarded_credits"] < 1000
    assert twin["counts"]["awarded_credits"] > 0     # real evidence exists
    assert twin["maturity"] == "M1"
    assert twin["finalis_1000_state"] == \
        "NOT_QUALIFIED_PENDING_RUNTIME_FIELD_AND_PRODUCTION_EVIDENCE"
    assert twin["product_state"] == "NOT_PRODUCTION_READY"


def test_score_never_exceeds_1000(twin):
    assert twin["scorecard"]["diagnostic_total_credits"] <= 1000
    assert score.verify_score_arithmetic(twin["scorecard"],
                                         twin["credit_awards"]) == []


def test_score_carries_maturity_gate_envelope_expiration(twin):
    sc = twin["scorecard"]
    assert sc["maturity"] and sc["hard_gate_state"]
    assert sc["qualification_envelope_ref"]
    assert "valid_until" in sc


def test_seal_grants_no_runtime_authority(twin):
    assert twin["evaluation_seal"]["grants_runtime_authority"] is False


def test_genome_and_seal_reproduce(twin):
    assert genome.verify_genome(twin["evaluation_genome"])
    frz = freeze.freeze(ROOT)
    assert genome.verify_seal(twin["evaluation_seal"],
                              expected_commit=frz["starting_head"]) == []


def test_evaluation_deterministic(twin):
    assert evaluation.build_evaluation(ROOT)["evaluation_digest"] == \
        twin["evaluation_digest"]


def test_no_p0_p1(twin):
    assert twin["counts"]["findings"]["P0"] == 0
    assert twin["counts"]["findings"]["P1"] == 0


def test_validate_passes(twin):
    rep = validate.validate_evaluation(twin, ROOT)
    assert rep.valid, rep.as_dict()["counts"]


def test_no_fabricated_field_or_production_evidence(twin):
    env = twin["qualification_envelope"]
    assert env["validity_scope"]["field_evidence"] == "ABSENT"
    assert env["validity_scope"]["production_evidence"] == "ABSENT"
    # maturity is M1, never M4/M5
    assert twin["maturity"] in ("M0", "M1")

"""SP0005 assurance, evidence, oracle, oversight, probes. Covers AC-0005-085..097,
125..147."""
from __future__ import annotations

from tools.safety.assurance import (validate_claims, open_defeaters,
                                    stale_critical_evidence, propagate_defeater)
from tools.safety.evidence import validate_evidence, applicable, freshness
from tools.safety.oracle import validate_hard_property, strongest, rank
from tools.safety.oversight import evaluate_oversight, validate_review_packet
from tools.safety.probes import validate_probe_contract, validate_decision_trace
from tools.safety.model import (CRITICAL_DEFEATER_OPEN, ASSURANCE_EVIDENCE_STALE,
                                HUMAN_OVERSIGHT_INSUFFICIENT,
                                HUMAN_REVIEW_PACKET_INCOMPLETE,
                                SELF_REPORT_AS_SOLE_ORACLE, INVALID_SAFETY_SCHEMA)


def _k(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


# ---- assurance case + defeaters (AC-0005-085..095) -------------------------
def test_open_critical_defeater_challenges_claim():
    reg = {"claims": [{"claim_id": "C", "status": "SUPPORTED_CURRENT",
                       "defeater_refs": ["D"]}],
           "defeaters": [{"defeater_id": "D", "severity": "CRITICAL",
                          "status": "OPEN"}]}
    assert CRITICAL_DEFEATER_OPEN in _k(open_defeaters(reg))


def test_resolved_defeater_does_not_challenge():
    reg = {"claims": [{"claim_id": "C", "status": "SUPPORTED_CURRENT",
                       "defeater_refs": ["D"]}],
           "defeaters": [{"defeater_id": "D", "severity": "CRITICAL",
                          "status": "RESOLVED"}]}
    assert CRITICAL_DEFEATER_OPEN not in _k(open_defeaters(reg))


def test_defeater_propagation():
    reg = {"claims": [{"claim_id": "C1", "defeater_refs": ["D"]},
                      {"claim_id": "C2", "depends_on": ["C1"]}]}
    r = propagate_defeater(reg, "D")
    assert r["challenged"] == ["C1"] and r["reassessment_required"] == ["C2"]


# ---- evidence freshness (AC-0005-096/097) ----------------------------------
def test_stale_critical_evidence_fails():
    reg = {"claims": [{"claim_id": "C", "status": "SUPPORTED_CURRENT",
                       "critical": True, "evidence_refs": ["E"]}],
           "evidence": [{"evidence_id": "E", "status": "EVIDENCE_STALE"}]}
    assert ASSURANCE_EVIDENCE_STALE in _k(stale_critical_evidence(reg))


def test_evidence_applicability_context():
    ev = {"code_version": "v1", "semantic_epoch": "e1"}
    assert applicable(ev, {"code_version": "v1", "semantic_epoch": "e1"})
    assert not applicable(ev, {"code_version": "v2", "semantic_epoch": "e1"})
    assert freshness(ev, {"code_version": "v2"}) == "EVIDENCE_STALE"


# ---- oracle hierarchy (AC-0005-142..147) -----------------------------------
def test_self_report_alone_insufficient():
    assert SELF_REPORT_AS_SOLE_ORACLE in _k(validate_hard_property(
        {"property_id": "P", "oracles": ["AGENT_SELF_REPORT"]}))


def test_llm_judge_alone_insufficient_unless_validated():
    assert SELF_REPORT_AS_SOLE_ORACLE in _k(validate_hard_property(
        {"property_id": "P", "oracles": [{"type": "LLM_JUDGE",
                                          "independently_validated": False}]}))
    assert not validate_hard_property(
        {"property_id": "P", "oracles": [{"type": "LLM_JUDGE",
                                          "independently_validated": True}]})


def test_environment_oracle_is_strongest():
    assert strongest(["LLM_JUDGE", "ENVIRONMENT_STATE"]) == "ENVIRONMENT_STATE"
    assert rank("ENVIRONMENT_STATE") < rank("AGENT_SELF_REPORT")


def test_env_oracle_property_ok():
    assert not validate_hard_property(
        {"property_id": "P", "oracles": ["ENVIRONMENT_STATE"]})


# ---- human oversight + review packet (AC-0005-125..135) --------------------
def test_oversight_missing_reject_authority_insufficient():
    o = {"oversight_id": "O", "sufficient_information": True,
         "reject_authority": False, "time_to_intervene": True,
         "relevant_competence": True, "stop_capability": True}
    assert HUMAN_OVERSIGHT_INSUFFICIENT in _k(evaluate_oversight(o))


def test_full_oversight_ok():
    o = {"oversight_id": "O", "sufficient_information": True,
         "reject_authority": True, "time_to_intervene": True,
         "relevant_competence": True, "stop_capability": True}
    assert not evaluate_oversight(o)


def test_review_packet_incomplete_detected():
    assert HUMAN_REVIEW_PACKET_INCOMPLETE in _k(validate_review_packet(
        {"packet_id": "P", "proposal": "x"}))  # missing many fields


def test_review_packet_hiding_uncertainty_flagged():
    from tools.safety.model import REVIEW_PACKET_FIELDS
    full = {f: "x" for f in REVIEW_PACKET_FIELDS}
    full.update({"packet_id": "P", "hides_uncertainty": True})
    assert HUMAN_REVIEW_PACKET_INCOMPLETE in _k(validate_review_packet(full))


# ---- probes + decision trace (AC-0005-136..141) ----------------------------
def test_probe_no_private_cot_required():
    assert any("chain-of-thought" in f.message for f in validate_probe_contract(
        {"contract_id": "C", "requires_private_chain_of_thought": True,
         "observed_boundaries": [], "distinguishes": {}}))


def test_probe_must_distinguish_effect_from_outcome():
    c = {"contract_id": "C", "observed_boundaries": [],
         "distinguishes": {"model_proposal_vs_policy_decision": True,
                           "authority_decision_vs_effect": True}}
    # missing effect_vs_outcome
    assert any("effect from outcome" in f.message
               for f in validate_probe_contract(c))


def test_decision_trace_requires_fields():
    assert validate_decision_trace({"trace_id": "T"})  # missing all fields
    from tools.safety.probes import TRACE_FIELDS
    full = {f: "x" for f in TRACE_FIELDS}
    full["trace_id"] = "T"
    assert not validate_decision_trace(full)

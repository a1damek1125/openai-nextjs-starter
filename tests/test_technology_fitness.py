"""SP0004 fitness, protocols, supply-chain, survivability, envelopes, intent.
Covers AC-0004-089..148."""
from __future__ import annotations

from tools.technology.fitness import (validate_waiver, waived, evaluate_fitness,
                                       fitness_summary, UNWAIVABLE)
from tools.technology.protocols import (validate_protocols, deprecation_findings,
                                        validate_radar)
from tools.technology.supplychain import validate_strategy, attestation_verified
from tools.technology.survivability import survivability_profile, impact_cone
from tools.technology.envelope import decision_envelope, substitution_envelope
from tools.technology.intent import validate_intent
from tools.technology.model import (WAIVER_INVALID, FLOATING_VERSION,
                                    PROTOCOL_VERSION_STALE, FALSE_SLSA_COMPLIANCE,
                                    PROTOCOL_VERSION_UNSUPPORTED)


def _kinds(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


# ---- AC-0004-097 + waivers -------------------------------------------------
def test_anonymous_and_eternal_waivers_invalid():
    assert WAIVER_INVALID in _kinds(validate_waiver(
        {"waiver_id": "w", "scope": "s", "rationale": "r", "expiry": "2099-01-01"},
        today="2026-07-11"))   # missing owner
    assert WAIVER_INVALID in _kinds(validate_waiver(
        {"waiver_id": "w", "owner": "o", "scope": "s", "rationale": "r"},
        today="2026-07-11"))   # no expiry


def test_constitutional_p0_cannot_be_waived():
    w = {"waiver_id": "w", "owner": "o", "scope": "s", "rationale": "r",
         "expiry": "2099-01-01", "fitness_id": "FIT-NO-RAW-SECRET"}
    assert WAIVER_INVALID in _kinds(validate_waiver(w, today="2026-07-11"))
    assert not waived("FIT-NO-RAW-SECRET", [w], today="2026-07-11")


def test_valid_waiver_waives_non_constitutional():
    w = {"waiver_id": "w", "owner": "o", "scope": "s", "rationale": "r",
         "expiry": "2099-01-01", "fitness_id": "FIT-REVIEW-CURRENT"}
    assert not validate_waiver(w, today="2026-07-11")
    assert waived("FIT-REVIEW-CURRENT", [w], today="2026-07-11")


# ---- AC-0004-093/094: fitness catches leakage + unsupported protocol -------
def test_fitness_catches_raw_secret_and_unsupported_protocol():
    program = {
        "contracts": {"contracts": [
            {"contract_id": "c", "request_schema": {"api_key": "s"}}]},
        "inventory": {}, "exit_profiles": [],
        "protocols": {"protocols": [
            {"protocol_id": "p", "status": "UNSUPPORTED"}]},
        "waivers": []}
    kinds = _kinds(evaluate_fitness(program, today="2026-07-11"))
    assert "RAW_SECRET_EXPOSURE" in kinds
    assert PROTOCOL_VERSION_UNSUPPORTED in kinds


# ---- AC-0004-102/103/104: protocols ----------------------------------------
def test_floating_version_flagged():
    reg = {"protocols": [{"protocol_id": "p", "family": "MCP",
                          "role": "INTEROP_BOUNDARY", "protected": True,
                          "supported_version": "latest"}]}
    assert FLOATING_VERSION in _kinds(validate_protocols(reg))


def test_mcp_must_be_interop_boundary_not_authority():
    # exact family
    assert validate_protocols({"protocols": [
        {"protocol_id": "p", "family": "MCP", "role": "AUTHORITY",
         "supported_version": "2025-11-25"}]})
    # lowercase / whitespace family cannot evade (red-team F6)
    assert validate_protocols({"protocols": [
        {"protocol_id": "p", "family": " mcp ", "role": "AUTHORITY"}]})
    # omitted family, inferred from protocol_id
    assert validate_protocols({"protocols": [
        {"protocol_id": "MCP-1", "role": "AUTHORITY"}]})


def test_sunset_protocol_flagged():
    reg = {"protocols": [{"protocol_id": "p", "sunset_date": "2020-01-01"}]}
    assert PROTOCOL_VERSION_STALE in _kinds(
        deprecation_findings(reg, today="2026-07-11"))


def test_radar_valid_rings():
    assert not validate_radar({"entries": [{"technology": "x", "ring": "ADOPT"}]})
    assert validate_radar({"entries": [{"technology": "x", "ring": "BOGUS"}]})


# ---- AC-0004-128/129: supply chain -----------------------------------------
def test_supply_chain_requires_all_standards():
    assert validate_strategy({"standards": []})   # missing all four -> findings


def test_false_compliance_claim_flagged():
    s = {"standards": [
        {"standard": "SLSA", "decision": "ADOPT_TARGET", "claims_compliance": True},
        {"standard": "CYCLONEDX", "decision": "EVALUATE"},
        {"standard": "SPDX", "decision": "EVALUATE"},
        {"standard": "AI_ML_BOM", "decision": "DEFER"}]}
    assert FALSE_SLSA_COMPLIANCE in _kinds(validate_strategy(s))


def test_attestation_distinct_from_verification():
    assert attestation_verified({"verified_by_policy": True}) is True
    assert attestation_verified({"signature": "x"}) is False


# ---- AC-0004-112..116: survivability ---------------------------------------
def test_survivability_dimensions_separate():
    p = survivability_profile({"technology_id": "t",
                               "survivability": {"data_portability": "FULL"}})
    assert p["dimensions"]["data_portability"] == "FULL"
    assert p["dimensions"]["team_knowledge"] == "UNKNOWN"


def test_impact_cone_spans_graphs():
    g = {"nodes": [{"node_id": "a"}, {"node_id": "b"}],
         "edges": [{"from": "b", "to": "a"}]}
    d = {"affected_technologies": ["a"], "affected_architecture": ["mod"],
         "affected_program": ["SP0009"]}
    cone = impact_cone(g, d)
    assert "b" in cone["technology_downstream"]
    assert cone["affected_program"] == ["SP0009"]


# ---- AC-0004-123: change intent --------------------------------------------
def test_change_intent_schema():
    assert not validate_intent({"change_id": "c", "change_kind": "PROVIDER_CHANGED",
                                "target": "x"})
    assert validate_intent({"change_id": "c", "change_kind": "BOGUS",
                            "target": "x"})


# ---- AC-0004-140..148: proof envelopes -------------------------------------
def test_decision_envelope_deterministic_and_evidence():
    d = {"decision_id": "T", "candidates": [{"candidate_id": "a"}],
         "evidence_refs": ["E"]}
    e1, e2 = decision_envelope(d), decision_envelope(d)
    assert e1["envelope_hash"] == e2["envelope_hash"]
    assert e1["classification"] == "EVIDENCE_NOT_AUTHORITY"


def test_envelope_changes_on_candidate_and_evidence_change():
    d = {"decision_id": "T", "candidates": [{"candidate_id": "a"}],
         "evidence_refs": ["E"]}
    h0 = decision_envelope(d)["envelope_hash"]
    d2 = dict(d, candidates=[{"candidate_id": "b"}])
    d3 = dict(d, evidence_refs=["E", "F"])
    assert decision_envelope(d2)["envelope_hash"] != h0
    assert decision_envelope(d3)["envelope_hash"] != h0


def test_envelope_changes_on_exit_plan_and_fitness_policy():
    d = {"decision_id": "T", "exit_plan_ref": "x", "fitness_policy_ref": "p"}
    h0 = decision_envelope(d)["envelope_hash"]
    assert decision_envelope(dict(d, exit_plan_ref="y"))["envelope_hash"] != h0
    assert decision_envelope(dict(d, fitness_policy_ref="q"))["envelope_hash"] != h0


def test_substitution_envelope_version_bound():
    ev = {"substitution_id": "s", "contract_version": "1.0", "corpus_version": "1.0"}
    h0 = substitution_envelope(ev)["envelope_hash"]
    assert substitution_envelope(dict(ev, corpus_version="2.0"))["envelope_hash"] \
        != h0

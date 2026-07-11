"""Regression locks for SWARM-L red-team findings (SP0004 repair round)."""
from __future__ import annotations

from tools.technology.contracts import check_credential_isolation
from tools.technology.decisions import check_append_only
from tools.technology.substitution import (shadow_replay, evidence_applicable,
                                           validate_substitution_evidence,
                                           stale_substitution)
from tools.technology.conformance import DeterministicReferenceProvider
from tools.technology.exit_readiness import evaluate_exit
from tools.technology.depgraph import classify_diversity, detect_common_mode
from tools.technology.protocols import validate_protocols
from tools.technology.model import (RAW_SECRET_EXPOSURE, APPEND_ONLY_VIOLATION,
                                    SHADOW_EXTERNAL_EFFECT_BLOCKED, DATA_EXPORT_GAP,
                                    COSMETIC_PROVIDER_DIVERSITY,
                                    SUBSTITUTION_EVIDENCE_STALE)


def _kinds(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


# ---- pre-repair proactive: hyphen/case credential evasion ------------------
def test_credential_hyphen_case_variants_caught():
    for field in ("authorization", "x-api-key", "access_key",
                  "connection_string", "AUTHORIZATION", "auth-token"):
        c = {"contract_id": "c", "request_schema": {field: "str"}}
        assert RAW_SECRET_EXPOSURE in _kinds(check_credential_isolation(c)), field


def test_credential_reference_still_ok():
    for field in ("credential_ref", "credential_reference", "canonical_input"):
        c = {"contract_id": "c", "request_schema": {field: "str"}}
        assert RAW_SECRET_EXPOSURE not in _kinds(check_credential_isolation(c)), field


# ---- F1: secret hidden as a schema field-name VALUE ------------------------
def test_F1_secret_as_schema_value_caught():
    c = {"contract_id": "c", "request_schema":
         {"type": "object", "fields": [{"name": "api_key", "type": "string"}]}}
    assert RAW_SECRET_EXPOSURE in _kinds(check_credential_isolation(c))


def test_F1_openapi_parameter_secret_caught():
    c = {"contract_id": "c", "request_schema":
         {"parameters": [{"name": "authorization", "in": "header"}]}}
    assert RAW_SECRET_EXPOSURE in _kinds(check_credential_isolation(c))


def test_F1c_reference_suffix_not_over_exempted():
    # a raw key masquerading with "reference" mid-name is NOT exempted
    c = {"contract_id": "c", "request_schema": {"api_key_for_reference": "str"}}
    assert RAW_SECRET_EXPOSURE in _kinds(check_credential_isolation(c))


# ---- proactive: append-only core by exclusion ------------------------------
def test_append_only_protects_substantive_fields():
    base = {"decision_id": "T", "status": "ACTIVE", "criticality": "T4",
            "evidence_refs": ["E"], "exit_plan_ref": "X", "scope": "s"}
    for field, val in (("criticality", "T0"), ("evidence_refs", ["FAKE"]),
                       ("exit_plan_ref", None)):
        old = {"decisions": [dict(base)]}
        new = {"decisions": [dict(base, **{field: val})]}
        assert APPEND_ONLY_VIOLATION in _kinds(check_append_only(old, new)), field


def test_append_only_allows_status_and_editorial():
    base = {"decision_id": "T", "status": "ACTIVE", "criticality": "T4",
            "scope": "s"}
    old = {"decisions": [dict(base)]}
    new = {"decisions": [dict(base, status="SUPERSEDED", title="new title")]}
    assert APPEND_ONLY_VIOLATION not in _kinds(check_append_only(old, new))


# ---- F2: shadow lab fails CLOSED -------------------------------------------
def test_F2_shadow_lab_fails_closed_on_missing_effect_mode():
    prov = DeterministicReferenceProvider("email")
    # real effect mode, `effectful` flag omitted -> must be refused
    r = shadow_replay(prov, [{"workload_id": "send", "effect_mode": "REAL"}])
    assert r["replayed"] == 0 and r["blocked_effectful"] == 1
    assert SHADOW_EXTERNAL_EFFECT_BLOCKED in {f["kind"] for f in r["findings"]}
    # no effect_mode at all -> also refused (fail closed)
    r2 = shadow_replay(prov, [{"workload_id": "x"}])
    assert r2["replayed"] == 0


def test_F2_shadow_lab_runs_only_no_external_effect():
    prov = DeterministicReferenceProvider("model")
    r = shadow_replay(prov, [{"workload_id": "ok",
                              "effect_mode": "NO_EXTERNAL_EFFECT"}])
    assert r["replayed"] == 1 and r["blocked_effectful"] == 0


# ---- F3: substitution evidence provider_version enforced -------------------
def test_F3_missing_provider_version_rejected_and_not_applicable():
    assert any("provider_version" in f.message for f in
               validate_substitution_evidence(
                   {"substitution_id": "s", "source_provider": "a",
                    "candidate_provider": "b", "contract_version": "1",
                    "corpus_version": "1", "tested_at": "t"}))
    ev = {"contract_version": "1.0", "corpus_version": "1.0"}  # no provider_version
    assert not evidence_applicable(ev, current_contract_version="1.0",
                                   current_corpus_version="1.0",
                                   current_provider_version="v99")


def test_F3_stale_substitution_uses_provider_version():
    ev = [{"substitution_id": "s", "contract_version": "1.0",
           "corpus_version": "1.0", "provider_version": "v1"}]
    assert SUBSTITUTION_EVIDENCE_STALE in _kinds(stale_substitution(
        ev, current_contract_version="1.0", current_corpus_version="1.0",
        current_provider_version="v99"))


# ---- F4: exit readiness requires VALIDATED export --------------------------
def test_F4_documented_or_stale_export_is_a_gap():
    inv = {"technologies": [{"technology_id": "t", "criticality": "T4"}]}
    for state in ("DOCUMENTED", "STALE", "PARTIAL"):
        profs = [{"technology_id": "t", "data_export": state,
                  "last_drill_level": "D4"}]
        assert DATA_EXPORT_GAP in _kinds(evaluate_exit(inv, profs)), state


def test_F4_validated_export_passes():
    inv = {"technologies": [{"technology_id": "t", "criticality": "T3"}]}
    profs = [{"technology_id": "t", "data_export": "FULL",
              "last_drill_level": "D3"}]
    assert DATA_EXPORT_GAP not in _kinds(evaluate_exit(inv, profs))


def test_F4_insufficient_drill_flagged():
    from tools.technology.model import EXIT_PLAN_MISSING
    inv = {"technologies": [{"technology_id": "t", "criticality": "T4"}]}
    profs = [{"technology_id": "t", "data_export": "FULL",
              "last_drill_level": "D1"}]
    assert EXIT_PLAN_MISSING in _kinds(evaluate_exit(inv, profs))


# ---- F5: one shared critical failure domain is cosmetic --------------------
def test_F5_single_shared_cloud_is_cosmetic():
    g = {"nodes": [
        {"node_id": "pA", "failure_domain": {"cloud": "aws", "region": "us"}},
        {"node_id": "pB", "failure_domain": {"cloud": "aws", "region": "eu"}}],
        "edges": []}
    assert classify_diversity(g, "pA", "pB")["class"] == "DIVERSITY_COSMETIC"
    assert COSMETIC_PROVIDER_DIVERSITY in _kinds(detect_common_mode(g, [["pA", "pB"]]))


def test_F5_distinct_domains_stay_real():
    g = {"nodes": [
        {"node_id": "pA", "failure_domain": {"cloud": "aws", "region": "us",
         "identity_dependency": "x", "gateway_dependency": "g1",
         "upstream_model": "m1", "upstream_service": "s1", "control_plane": "c1"}},
        {"node_id": "pB", "failure_domain": {"cloud": "gcp", "region": "eu",
         "identity_dependency": "y", "gateway_dependency": "g2",
         "upstream_model": "m2", "upstream_service": "s2", "control_plane": "c2"}}],
        "edges": []}
    assert classify_diversity(g, "pA", "pB")["class"] == "DIVERSITY_REAL"


# ---- F6: protocol authority evasion --------------------------------------
def test_F6_authority_role_default_denied():
    for proto in ({"protocol_id": "p", "family": "mcp", "role": "AUTHORITY"},
                  {"protocol_id": "MCP-1", "role": "AUTHORITY"},
                  {"protocol_id": "p", "family": " A2A ", "role": "AUTHORITY"}):
        assert validate_protocols({"protocols": [proto]}), proto


# ---- SWARM-M item 1: all 5 substitutability classes reachable --------------
def test_M1_substitutability_unknown_reachable():
    from tools.technology.conformance import substitutability
    assert substitutability({"workloads": 0}, contract_deterministic=True) == \
        "UNKNOWN"
    got = {substitutability({"workloads": 2, "agreement": a},
                            contract_deterministic=True)
           for a in (1.0, 0.9, 0.3, 0.0)}
    assert got == {"CONTRACT_EQUIVALENT", "FUNCTIONALLY_ACCEPTABLE",
                   "PARTIALLY_SUBSTITUTABLE", "NON_EQUIVALENT"}


# ---- SWARM-M item 2: attest binds real Pareto/sensitivity ------------------
def test_M2_envelope_binds_pareto_and_sensitivity():
    from tools.technology.envelope import decision_envelope
    d = {"decision_id": "T",
         "candidates": [{"candidate_id": "A", "scores": {"q": 9}},
                        {"candidate_id": "B", "scores": {"q": 1}}],
         "criteria": [{"key": "q", "direction": "MAX", "min": 0, "max": 10,
                       "weight": 1.0}]}
    from tools.technology.pareto import pareto_frontier
    from tools.technology.sensitivity import sensitivity
    analyses = {"pareto": pareto_frontier(d["candidates"], d["criteria"]),
                "sensitivity": sensitivity(d)}
    bound = decision_envelope(d, analyses=analyses)
    inert = decision_envelope(d)
    # binding real analyses changes the pareto/sensitivity hashes and the envelope
    assert bound["pareto_analysis_hash"] != inert["pareto_analysis_hash"]
    assert bound["envelope_hash"] != inert["envelope_hash"]

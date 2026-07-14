"""SP0004 provider layer: contracts, credential/identity/error isolation,
core+extensions, conformance, differential, substitution, exit readiness, common
mode. Covers AC-0004-041..088."""
from __future__ import annotations

from tools.technology.contracts import (validate_contract,
                                        check_credential_isolation,
                                        check_identity_and_error_leakage,
                                        check_extensions)
from tools.technology.conformance import (validate_workload,
                                          DeterministicReferenceProvider,
                                          run_conformance, differential,
                                          substitutability)
from tools.technology.substitution import (shadow_replay,
                                           validate_substitution_evidence,
                                           evidence_applicable, stale_substitution)
from tools.technology.exit_readiness import (evaluate_exit, exit_readiness_index,
                                             required_drill_level,
                                             drill_sufficient)
from tools.technology.depgraph import (classify_diversity, detect_common_mode,
                                       upstream_closure, common_upstream)
from tools.technology.model import (RAW_SECRET_EXPOSURE, PROVIDER_IDENTITY_LEAKAGE,
                                    PROVIDER_ERROR_AS_BUSINESS_STATE,
                                    EXTENSION_REDEFINES_CORE,
                                    UNIVERSAL_PROVIDER_CONTRACT,
                                    CRITICAL_DEPENDENCY_WITHOUT_EXIT_PLAN,
                                    DATA_EXPORT_GAP, COSMETIC_PROVIDER_DIVERSITY,
                                    SUBSTITUTION_EVIDENCE_STALE,
                                    SHADOW_EXTERNAL_EFFECT_BLOCKED)


def _kinds(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


# ---- AC-0004-047: no universal provider contract ---------------------------
def test_universal_provider_contract_flagged():
    c = {"contract_id": "c", "provider_class": "x",
         "core_capabilities": ["execute"]}
    assert UNIVERSAL_PROVIDER_CONTRACT in _kinds(validate_contract(c))


# ---- AC-0004-057: raw secret cannot enter model-facing schema --------------
def test_raw_secret_exposure():
    c = {"contract_id": "c", "request_schema": {"api_key": "str"}}
    assert RAW_SECRET_EXPOSURE in _kinds(check_credential_isolation(c))


def test_credential_reference_ok():
    c = {"contract_id": "c", "request_schema": {"credential_ref": "str"}}
    assert RAW_SECRET_EXPOSURE not in _kinds(check_credential_isolation(c))


# ---- AC-0004-052/053: provider id / error leakage --------------------------
def test_provider_id_as_canonical_identity_flagged():
    c = {"contract_id": "c",
         "provider_id_mappings": [{"maps_to": "employee_id", "kind": "primary"}]}
    assert PROVIDER_IDENTITY_LEAKAGE in _kinds(check_identity_and_error_leakage(c))


def test_provider_error_as_business_state_flagged():
    c = {"contract_id": "c",
         "error_mappings": [{"from": "429", "maps_to": "case_status"}]}
    assert PROVIDER_ERROR_AS_BUSINESS_STATE in _kinds(
        check_identity_and_error_leakage(c))


# ---- AC-0004-048/049/050: core + namespaced extensions ---------------------
def test_extension_cannot_redefine_core():
    c = {"contract_id": "c", "core_capabilities": ["transcribe"],
         "extensions": [{"namespace": "px", "name": "transcribe"}]}
    assert EXTENSION_REDEFINES_CORE in _kinds(check_extensions(c))


def test_extension_must_be_namespaced():
    c = {"contract_id": "c", "core_capabilities": ["x"],
         "extensions": [{"name": "feature"}]}
    assert any(f.message.endswith("not namespaced (AC-0004-049)")
               for f in check_extensions(c))


# ---- AC-0004-055: effectful contract needs UNKNOWN_OUTCOME ------------------
def test_effectful_contract_requires_unknown_outcome():
    c = {"contract_id": "c", "provider_class": "email", "effectful": True,
         "core_capabilities": ["send"], "error_taxonomy": ["TIMEOUT"]}
    assert any("UNKNOWN_OUTCOME" in f.message for f in validate_contract(c))


# ---- AC-0004-061/062/063/064/065: reference provider + corpus --------------
def test_reference_provider_deterministic_and_fault():
    ref = DeterministicReferenceProvider("model")
    w = {"workload_id": "w", "canonical_input": {"x": 1},
         "required_properties": ["p"]}
    r1, r2 = ref.handle(w), ref.handle(w)
    assert r1 == r2 and r1["outcome"] == "SUCCESS"
    fault = DeterministicReferenceProvider("model", fault="TIMEOUT")
    assert fault.handle(w)["outcome"] == "FAILED"


def test_workload_must_be_provider_neutral():
    w = {"workload_id": "w", "provider_class": "model",
         "canonical_input": {"provider_native": True}}
    assert any("provider-native" in f.message for f in validate_workload(w))


def test_effectful_workload_defaults_no_external_effect():
    w = {"workload_id": "w", "provider_class": "email", "effectful": True,
         "effect_mode": "REAL"}
    assert any("NO_EXTERNAL_EFFECT" in f.message for f in validate_workload(w))


# ---- AC-0004-066/067/068/069..074: conformance + differential --------------
def test_conformance_pass_and_substitutability_not_boolean():
    corpus = [{"workload_id": "w1", "canonical_input": {}, "required_properties":
               []}]
    a = DeterministicReferenceProvider("model")
    b = DeterministicReferenceProvider("model")
    assert run_conformance(a, corpus)["verdict"] == "PASS"
    diff = differential(a, b, corpus)
    assert diff["agreement"] == 1.0
    assert substitutability(diff, contract_deterministic=True) == \
        "CONTRACT_EQUIVALENT"
    assert substitutability(diff, contract_deterministic=False) == \
        "FUNCTIONALLY_ACCEPTABLE"


# ---- AC-0004-076: shadow lab creates no unauthorized external effect --------
def test_shadow_lab_blocks_effectful_workload():
    corpus = [{"workload_id": "w", "effectful": True, "effect_mode": "REAL",
               "canonical_input": {}}]
    r = shadow_replay(DeterministicReferenceProvider("email"), corpus)
    assert r["blocked_effectful"] == 1
    assert SHADOW_EXTERNAL_EFFECT_BLOCKED in {f["kind"] for f in r["findings"]}


# ---- AC-0004-079/080: exit readiness ---------------------------------------
def test_critical_dependency_without_exit_plan_fails():
    inv = {"technologies": [{"technology_id": "t", "criticality": "T4"}]}
    assert CRITICAL_DEPENDENCY_WITHOUT_EXIT_PLAN in _kinds(evaluate_exit(inv, []))


def test_data_export_gap_detected():
    inv = {"technologies": [{"technology_id": "t", "criticality": "T3"}]}
    profiles = [{"technology_id": "t", "data_export": "UNKNOWN"}]
    assert DATA_EXPORT_GAP in _kinds(evaluate_exit(inv, profiles))


def test_exit_index_advisory_with_hard_blocker():
    prof = {"data_export": "UNKNOWN"}
    idx = exit_readiness_index(prof)
    assert idx["advisory_only"] and idx["hard_blocker_data_export"]


def test_drill_level_scales_with_criticality():
    assert required_drill_level("T4") == "D4"
    assert drill_sufficient("T4", "D4") and not drill_sufficient("T4", "D1")


# ---- AC-0004-085..088: substitution evidence version-bound -----------------
def test_substitution_evidence_version_bound():
    ev = {"substitution_id": "s", "contract_version": "1.0", "corpus_version":
          "1.0", "provider_version": "1.0"}
    assert evidence_applicable(ev, current_contract_version="1.0",
                               current_corpus_version="1.0")
    assert not evidence_applicable(ev, current_contract_version="2.0",
                                   current_corpus_version="1.0")


def test_stale_substitution_detected():
    ev = [{"substitution_id": "s", "contract_version": "1.0",
           "corpus_version": "0.9"}]
    assert SUBSTITUTION_EVIDENCE_STALE in _kinds(
        stale_substitution(ev, current_contract_version="1.0",
                           current_corpus_version="1.0"))


# ---- AC-0004-041/042/043: common-mode --------------------------------------
def test_cosmetic_diversity_detected():
    g = {"nodes": [
        {"node_id": "pA", "failure_domain": {"cloud": "aws", "region": "us"}},
        {"node_id": "pB", "failure_domain": {"cloud": "aws", "region": "us"}}],
        "edges": []}
    assert classify_diversity(g, "pA", "pB")["class"] == "DIVERSITY_COSMETIC"
    assert COSMETIC_PROVIDER_DIVERSITY in _kinds(
        detect_common_mode(g, [["pA", "pB"]]))


def test_shared_upstream_detected():
    g = {"nodes": [{"node_id": "pA"}, {"node_id": "pB"}, {"node_id": "gw"}],
         "edges": [{"from": "pA", "to": "gw"}, {"from": "pB", "to": "gw"}]}
    assert common_upstream(g, "pA", "pB") == {"gw"}

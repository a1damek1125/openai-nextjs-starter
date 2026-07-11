"""SP0004 adversarial lock-in mutation campaign (§20.27, AC-0004-151). Each
lock-in corruption must be DETECTED — never a silent P0/P1."""
from __future__ import annotations

from tools.technology.contracts import validate_contract
from tools.technology.decisions import check_append_only
from tools.technology.constraints import candidate_feasible
from tools.technology.exit_readiness import evaluate_exit
from tools.technology.depgraph import detect_common_mode
from tools.technology.substitution import evidence_applicable
from tools.technology.protocols import validate_protocols
from tools.technology.supplychain import validate_strategy
from tools.technology.fitness import waived, validate_waiver
from tools.technology.model import (RAW_SECRET_EXPOSURE, PROVIDER_IDENTITY_LEAKAGE,
                                    PROVIDER_ERROR_AS_BUSINESS_STATE,
                                    EXTENSION_REDEFINES_CORE,
                                    UNIVERSAL_PROVIDER_CONTRACT,
                                    APPEND_ONLY_VIOLATION,
                                    CRITICAL_DEPENDENCY_WITHOUT_EXIT_PLAN,
                                    COSMETIC_PROVIDER_DIVERSITY,
                                    FALSE_SLSA_COMPLIANCE, WAIVER_INVALID)


def _kinds(fs):
    return {f.kind for f in (fs.findings if hasattr(fs, "findings") else fs)}


# 1) provider object as universal core
def test_mut_universal_provider_core():
    assert UNIVERSAL_PROVIDER_CONTRACT in _kinds(validate_contract(
        {"contract_id": "c", "provider_class": "x",
         "core_capabilities": ["invoke"]}))


# 2) provider ID as canonical identity
def test_mut_provider_id_as_identity():
    assert PROVIDER_IDENTITY_LEAKAGE in _kinds(validate_contract(
        {"contract_id": "c", "provider_class": "x", "core_capabilities": ["a"],
         "provider_id_mappings": [{"maps_to": "case_id", "kind": "primary"}]}))


# 3) provider error as business state
def test_mut_provider_error_as_business_state():
    assert PROVIDER_ERROR_AS_BUSINESS_STATE in _kinds(validate_contract(
        {"contract_id": "c", "provider_class": "x", "core_capabilities": ["a"],
         "error_mappings": [{"from": "500", "maps_to": "work_status"}]}))


# 4) credential in model context
def test_mut_credential_in_model_context():
    assert RAW_SECRET_EXPOSURE in _kinds(validate_contract(
        {"contract_id": "c", "provider_class": "x", "core_capabilities": ["a"],
         "request_schema": {"client_secret": "str"}}))


# 5) critical dependency without export
def test_mut_critical_without_export():
    inv = {"technologies": [{"technology_id": "t", "criticality": "T4"}]}
    assert CRITICAL_DEPENDENCY_WITHOUT_EXIT_PLAN in _kinds(evaluate_exit(inv, []))


# 6) provider extension as core
def test_mut_extension_as_core():
    assert EXTENSION_REDEFINES_CORE in _kinds(validate_contract(
        {"contract_id": "c", "provider_class": "x", "core_capabilities": ["send"],
         "extensions": [{"namespace": "px", "name": "send"}]}))


# 7) historical TDR rewrite
def test_mut_historical_tdr_rewrite():
    old = {"decisions": [{"decision_id": "T", "status": "ACTIVE",
                          "scope": "orig", "candidates": [],
                          "selected_candidate": None, "problem": "p",
                          "hard_constraints": [], "rejected_candidates": [],
                          "decision_method": [], "reversibility_class": "R1"}]}
    new = {"decisions": [{**old["decisions"][0], "scope": "SILENTLY CHANGED"}]}
    assert APPEND_ONLY_VIOLATION in _kinds(check_append_only(old, new))


# 8) fake portability claim (interface without substitution evidence)
def test_mut_stale_portability_claim():
    ev = {"contract_version": "1.0", "corpus_version": "1.0"}
    # a claim bound to old versions no longer applies
    assert not evidence_applicable(ev, current_contract_version="2.0",
                                   current_corpus_version="1.0")


# 9) two fallback providers sharing one upstream
def test_mut_cosmetic_diversity():
    g = {"nodes": [
        {"node_id": "pA", "failure_domain": {"cloud": "gcp", "region": "eu"}},
        {"node_id": "pB", "failure_domain": {"cloud": "gcp", "region": "eu"}}],
        "edges": []}
    assert COSMETIC_PROVIDER_DIVERSITY in _kinds(detect_common_mode(g, [["pA", "pB"]]))


# 10) protocol silently pinned to floating latest
def test_mut_floating_protocol():
    from tools.technology.model import FLOATING_VERSION
    assert FLOATING_VERSION in _kinds(validate_protocols(
        {"protocols": [{"protocol_id": "p", "family": "MCP",
                        "role": "INTEROP_BOUNDARY", "protected": True,
                        "supported_version": "latest"}]}))


# 11) false SLSA compliance claim
def test_mut_false_slsa_claim():
    s = {"standards": [
        {"standard": "SLSA", "decision": "ADOPT_TARGET", "claims_compliance": True},
        {"standard": "CYCLONEDX", "decision": "EVALUATE"},
        {"standard": "SPDX", "decision": "EVALUATE"},
        {"standard": "AI_ML_BOM", "decision": "EVALUATE"}]}
    assert FALSE_SLSA_COMPLIANCE in _kinds(validate_strategy(s))


# 12) fitness rule disabled by permanent waiver
def test_mut_permanent_waiver_rejected():
    w = {"waiver_id": "w", "owner": "o", "scope": "s", "rationale": "r"}  # no expiry
    assert WAIVER_INVALID in _kinds(validate_waiver(w, today="2026-07-11"))
    assert not waived("FIT-REVIEW-CURRENT", [w], today="2026-07-11")


# 13) unknown critical requirement laundered as PASS
def test_mut_unknown_not_pass():
    c = {"hard_constraint_results": {"security": "UNKNOWN"}}
    assert candidate_feasible(c, ["security"])[0] is False


# 14) constitutional invariant waived
def test_mut_constitutional_waiver_blocked():
    w = {"waiver_id": "w", "owner": "o", "scope": "s", "rationale": "r",
         "expiry": "2099-01-01", "fitness_id": "FIT-NO-PROVIDER-IDENTITY"}
    assert not waived("FIT-NO-PROVIDER-IDENTITY", [w], today="2026-07-11")

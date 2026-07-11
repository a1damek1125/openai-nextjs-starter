"""Technology Decision Proof Envelope + Substitution Evidence Envelope (SP0004
D-0004-80/81/82, §10.11/§11.16, INV-0004-24/25).

Deterministic over stable input fields, excluding volatile presentation. A change
to the candidate set / evidence set / exit plan / fitness policy changes the
decision envelope (AC-0004-142..145). Both envelopes are EVIDENCE, not authority
(INV-0004-24/25) — they never create runtime authority.
"""
from __future__ import annotations

from .canon import core_hash, sha256_hex, canonical_json

ENVELOPE_VERSION = "2.0.0"
VALIDATOR_VERSION = "sp0004-v2"


def _h(obj) -> str:
    return core_hash(obj)


def decision_envelope(decision: dict, *, analyses: dict | None = None) -> dict:
    analyses = analyses or {}
    core = {
        "envelope_version": ENVELOPE_VERSION,
        "decision_id": decision.get("decision_id"),
        "candidate_set_hash": _h(decision.get("candidates", [])),
        "evidence_set_hash": _h(decision.get("evidence_refs", [])),
        "hard_constraint_hash": _h(decision.get("hard_constraints", [])),
        "pareto_analysis_hash": _h(analyses.get("pareto")),
        "sensitivity_hash": _h(analyses.get("sensitivity")),
        "scenario_analysis_hash": _h(analyses.get("scenario")),
        "reversibility_hash": _h(decision.get("reversibility_class")),
        "switching_cost_hash": _h(decision.get("switching_cost", {})),
        "lock_in_hash": _h(decision.get("lock_in_exposure", {})),
        "exit_plan_hash": _h(decision.get("exit_plan_ref")),
        "fitness_policy_hash": _h(decision.get("fitness_policy_ref")),
        "provider_contract_hash": _h(decision.get("provider_contract_refs", [])),
        "review_policy_hash": _h({"review_by": decision.get("review_by"),
                                  "triggers": decision.get("review_triggers", [])}),
        "validator_version": VALIDATOR_VERSION,
    }
    env = dict(core)
    env["envelope_hash"] = sha256_hex(canonical_json(core))
    env["classification"] = "EVIDENCE_NOT_AUTHORITY"
    return env


def substitution_envelope(ev: dict) -> dict:
    core = {
        "envelope_version": ENVELOPE_VERSION,
        "substitution_id": ev.get("substitution_id"),
        "source_provider": ev.get("source_provider"),
        "candidate_provider": ev.get("candidate_provider"),
        "contract_version": ev.get("contract_version"),
        "corpus_version": ev.get("corpus_version"),
        "provider_version": ev.get("provider_version"),
        "environment": ev.get("environment"),
        "conformance_result": ev.get("conformance_result"),
        "differential_result": ev.get("differential_result"),
        "failure_injection_result": ev.get("failure_injection_result"),
        "portability_result": ev.get("portability_result"),
        "validator_version": VALIDATOR_VERSION,
    }
    env = dict(core)
    env["envelope_hash"] = sha256_hex(canonical_json(core))
    env["classification"] = "EVIDENCE_NOT_AUTHORITY"
    return env

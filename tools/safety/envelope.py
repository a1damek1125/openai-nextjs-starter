"""Safety Case Proof Envelope + Safety Decision Proof Envelope (SP0005 D-0005-87/
88/89, INV-0005-26).

Deterministic over the canonical safety-case / decision inputs, excluding volatile
presentation, so a change to hazards / action contract / trajectory contract /
proof obligations / evidence / defeaters / regulatory context changes the envelope
(AC-0005-210..215). Both envelopes are EVIDENCE, not execution authority — a valid
hash never grants automatic permission (INV-0005-26, D-0005-89).
"""
from __future__ import annotations

from .canon import core_hash, sha256_hex, canonical_json

ENVELOPE_VERSION = "2.0.0"
VALIDATOR_VERSION = "sp0005-v2"


def _h(obj) -> str:
    return core_hash(obj)


def safety_case_envelope(case: dict) -> dict:
    core = {
        "envelope_version": ENVELOPE_VERSION,
        "case_id": case.get("case_id"),
        "claim_set_hash": _h(case.get("claims", [])),
        "hazard_set_hash": _h(case.get("hazards", [])),
        "action_contract_hash": _h(case.get("action_contracts", [])),
        "trajectory_contract_hash": _h(case.get("trajectory_contracts", [])),
        "proof_obligation_hash": _h(case.get("proof_obligations", [])),
        "control_set_hash": _h(case.get("controls", [])),
        "evidence_set_hash": _h(case.get("evidence", [])),
        "defeater_set_hash": _h(case.get("defeaters", [])),
        "regulatory_context_hash": _h(case.get("regulatory_context", [])),
        "version_context_hash": _h(case.get("version_context", {})),
        "validator_version": VALIDATOR_VERSION,
    }
    env = dict(core)
    env["envelope_hash"] = sha256_hex(canonical_json(core))
    env["classification"] = "EVIDENCE_NOT_AUTHORITY"
    return env


def safety_decision_envelope(decision: dict) -> dict:
    core = {
        "envelope_version": ENVELOPE_VERSION,
        "action_fingerprint": decision.get("action_fingerprint"),
        "context_fingerprint": decision.get("context_fingerprint"),
        "trajectory_state_hash": decision.get("trajectory_state_hash"),
        "authority_snapshot_hash": decision.get("authority_snapshot_hash"),
        "proof_obligation_result_hash": _h(decision.get("proof_obligations", [])),
        "control_class_result": decision.get("control_class_result"),
        "decision": decision.get("decision"),
        "reason_codes": sorted(decision.get("reason_codes", [])),
        "policy_version": decision.get("policy_version"),
        "validator_version": VALIDATOR_VERSION,
    }
    env = dict(core)
    env["envelope_hash"] = sha256_hex(canonical_json(core))
    env["classification"] = "EVIDENCE_NOT_AUTHORITY"
    return env

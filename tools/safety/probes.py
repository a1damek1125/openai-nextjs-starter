"""Safety Measurement Probe Contract + Safety Decision Trace (SP0005 D-0005-58/59/
60, INV-0005-01, §5.10).

Safety-observable boundaries (goal admission, context assembly, tool proposal,
authority decision, safety decision, human review, effect preparation, effect
execution, provider response, outcome observation, memory write, …) are probeable
via OBSERVABLE evidence — NOT private model chain-of-thought (D-0005-59,
AC-0005-140). A safety decision is reconstructable from an action fingerprint,
context fingerprint, authority snapshot, proof obligations, evidence refs, policy
version, control-class result, decision and reason codes (D-0005-60).
"""
from __future__ import annotations

from .model import Finding, P1, INVALID_SAFETY_SCHEMA

PROBE_BOUNDARIES = ("goal_admission", "context_assembly",
                    "candidate_claim_admission", "plan_change", "tool_proposal",
                    "authority_decision", "safety_decision", "human_review",
                    "effect_preparation", "effect_execution", "provider_response",
                    "outcome_observation", "memory_write", "learning_promotion")

# distinctions the probe contract MUST keep separate (AC-0005-137/138/139)
REQUIRED_DISTINCTIONS = (("model_proposal", "policy_decision"),
                         ("authority_decision", "effect"),
                         ("effect", "outcome"))

TRACE_FIELDS = ("action_fingerprint", "context_fingerprint",
                "authority_snapshot_hash", "proof_obligations", "evidence_refs",
                "policy_version", "control_class_result", "decision",
                "reason_codes")


def validate_probe_contract(contract: dict) -> list[Finding]:
    out: list[Finding] = []
    cid = contract.get("contract_id", "-")
    # must not require private chain-of-thought (INV-0005-01/D-0005-59)
    if contract.get("requires_private_chain_of_thought"):
        out.append(Finding(INVALID_SAFETY_SCHEMA, P1, cid,
                           "probe contract requires private chain-of-thought — "
                           "forbidden (AC-0005-140)", {}))
    observed = set(contract.get("observed_boundaries", []))
    for a, b in REQUIRED_DISTINCTIONS:
        if not (a in observed and b in observed) and \
                contract.get("distinguishes", {}).get(f"{a}_vs_{b}") is not True:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, cid,
                               f"probe contract must distinguish {a} from {b} "
                               "(AC-0005-137/138/139)", {}))
    return out


def validate_decision_trace(trace: dict) -> list[Finding]:
    out: list[Finding] = []
    tid = trace.get("trace_id", "-")
    for f in TRACE_FIELDS:
        if f not in trace:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, tid,
                               f"safety decision trace missing {f!r} "
                               "(D-0005-60)", {}))
    return out

"""Outcomes, completion and the oracle hierarchy (SP0011 §2.1.G, §11.8/11.9,
§10.8, D-0011-011/044/045/046, AC-0011-101..120).

Activity != effect != outcome != completion (INV-17..19). Every run records all
four and classifies the outcome SUCCESS/FAILURE/PARTIAL/UNKNOWN — PARTIAL and
UNKNOWN are never success. Outcomes are verified by an ORACLE chosen by strict
priority (deterministic > cryptographic > contract > external-state > human >
agent-as-judge > llm-judge). An LLM judge or Agent-as-a-Judge can NEVER solely
close a critical claim (D-0011-045/046); a critical claim without a valid non-
judge oracle blocks. Oracle disagreement is preserved, never silently resolved.
"""
from __future__ import annotations

from .canon import hash_obj
from .model import (Finding, P0, ORACLE_TYPES, ORACLE_PRIORITY,
                    UNTRUSTED_SOLE_ORACLES, is_success)

# The reference oracle registry (grounded in real repo verification engines).
ORACLES = {
    "ORA-DET-STATE": {"oracle_type": "DETERMINISTIC", "independence_domain":
                      "repository-state",
                      "grounding": "tools/governed_work/outcome.py:verify_outcome"},
    "ORA-CRYPTO": {"oracle_type": "CRYPTOGRAPHIC", "independence_domain":
                   "hash-chain",
                   "grounding": "finalis/ai_employee/run_ledger.py"},
    "ORA-CONTRACT": {"oracle_type": "CONTRACT", "independence_domain":
                     "contract-surface",
                     "grounding": "tools/contracts_inventory/genome.py"},
    "ORA-EXTERNAL": {"oracle_type": "EXTERNAL_STATE", "independence_domain":
                     "external", "grounding": "MOCK_ONLY"},
    "ORA-HUMAN": {"oracle_type": "HUMAN", "independence_domain": "human-review",
                  "grounding": "ABSENT_NO_FIELD_REVIEW"},
    "ORA-AAJ": {"oracle_type": "AGENT_AS_JUDGE", "independence_domain":
                "agent-judge", "grounding": "META_EVAL_REQUIRED"},
    "ORA-LLM": {"oracle_type": "LLM_JUDGE", "independence_domain": "llm-judge",
                "grounding": "META_EVAL_REQUIRED"},
}


def select_oracle(available_types: list) -> str:
    """Return the highest-priority available oracle type (lowest priority index)."""
    present = [t for t in available_types if t in ORACLE_PRIORITY]
    if not present:
        return "UNRESOLVED"
    return min(present, key=lambda t: ORACLE_PRIORITY[t])


def classify_outcome(*, activity_done: bool, effect_achieved: bool,
                     outcome_verified: bool, completion_condition_met: bool,
                     evidence_present: bool) -> str:
    """Strict outcome classification. Missing evidence => UNKNOWN; activity/effect
    without a verified completed outcome => PARTIAL; only a verified, completed,
    evidenced outcome is SUCCESS."""
    if not evidence_present:
        return "UNKNOWN"
    if outcome_verified is True and completion_condition_met is True:
        return "SUCCESS"
    if activity_done or effect_achieved:
        return "PARTIAL"
    return "FAILURE"


def oracle_record(oracle_id: str, *, claim_refs: list) -> dict:
    spec = ORACLES[oracle_id]
    r = {"oracle_id": oracle_id, "oracle_type": spec["oracle_type"],
         "claim_refs": sorted(claim_refs),
         "independence_domain": spec["independence_domain"],
         "grounding": spec["grounding"],
         "trusted_sole": spec["oracle_type"] not in UNTRUSTED_SOLE_ORACLES}
    r["oracle_hash"] = hash_obj(r)
    return r


def critical_oracle_findings(claim_oracles: dict) -> list[Finding]:
    """claim_oracles: critical_claim_id -> list of oracle_types available. A
    critical claim whose only available oracle is a judge (or none) blocks."""
    out: list[Finding] = []
    for cid, types in sorted(claim_oracles.items()):
        trusted = [t for t in types if t not in UNTRUSTED_SOLE_ORACLES]
        if not trusted:
            out.append(Finding(
                "CRITICAL_LLM_JUDGE_SOLE", P0, cid,
                "critical claim has no valid non-judge oracle: an LLM/agent judge "
                "cannot solely close a critical claim (D-0011-045)",
                {"available": types}))
    return out


def oracle_root(records: list) -> str:
    return hash_obj(sorted(r["oracle_hash"] for r in records))

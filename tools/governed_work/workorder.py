"""Work Order Compiler + Canonical Work Order (SP0006 §9.2/10.2, D-0006-03/07).

Natural-language interpretation MAY propose fields; canonical admission and
validation are DETERMINISTIC (D-0006-07). The compiler canonicalizes goal/scope/
constraints/outcome/purpose/budget/approval/dependency/technology/safety, binds
the accountable owner, and computes the distinct semantic and instance hashes
(D-0006-02). No safe default may broaden intent (D-0006-09).
"""
from __future__ import annotations

from .model import (Finding, P0, P1, INVALID_WORK_SCHEMA, UNDEFINED_OUTCOME,
                    UNDEFINED_ACCOUNTABLE_OWNER, CONTEXT_USED_AS_AUTHORITY,
                    MEMORY_USED_AS_AUTHORITY)
from .canon import semantic_work_hash, work_instance_hash

# fields that must be present for a canonical work order to be well-formed
REQUIRED = ("work_order_id", "tenant_id", "requester_id", "canonical_goal",
            "allowed_scope", "privacy_purpose")


def compile_work_order(candidate: dict, *, bindings: dict | None = None) -> dict:
    """Deterministically compile a candidate intent (+ explicit bindings) into a
    canonical work order draft. Bindings supply governance context (owner,
    outcome contract, budgets, approval topology, envelopes) — never derived from
    the untrusted message body."""
    b = bindings or {}
    w: dict = {
        "work_order_id": candidate.get("work_order_id") or b.get("work_order_id"),
        "work_version": 1,
        "tenant_id": candidate.get("tenant_id"),
        "requester_id": candidate.get("requester_id"),
        "accountable_owner_id": b.get("accountable_owner_id"),
        "source_surface": candidate.get("source_surface"),
        "source_reference": candidate.get("source_reference"),
        "semantic_epoch": b.get("semantic_epoch", ""),
        "canonical_goal": _canonicalize_goal(candidate.get("proposed_goal", {})),
        "allowed_scope": candidate.get("proposed_scope", {}) or {},
        "forbidden_scope": b.get("forbidden_scope", {}) or {},
        "constraints": sorted_constraints(candidate.get("proposed_constraints",
                                                        [])),
        "required_inputs": b.get("required_inputs", []),
        "admitted_evidence_refs": b.get("admitted_evidence_refs", []),
        "outcome_contract": b.get("outcome_contract"),
        "capability_ceiling": b.get("capability_ceiling", {}) or {},
        "budget_vector": b.get("budget_vector"),
        "privacy_purpose": b.get("privacy_purpose")
        or candidate.get("privacy_purpose"),
        "retention_rule": b.get("retention_rule"),
        "approval_topology": b.get("approval_topology"),
        "recurrence_contract_ref": b.get("recurrence_contract_ref"),
        "issued_at": b.get("issued_at", ""),
        "expires_at": b.get("expires_at", ""),
        "recurrence_instance": b.get("recurrence_instance"),
        "cancellation_policy": b.get("cancellation_policy", {}),
        "dependency_envelope_ref": b.get("dependency_envelope_ref"),
        "technology_envelope_ref": b.get("technology_envelope_ref"),
        "safety_envelope_ref": b.get("safety_envelope_ref"),
        "risk_requirements": b.get("risk_requirements", {}),
        "status": "DRAFT",
    }
    w["semantic_work_hash"] = semantic_work_hash(w)
    w["work_instance_hash"] = work_instance_hash(w)
    return w


def _canonicalize_goal(goal) -> dict:
    if isinstance(goal, str):
        return {"statement": goal.strip()}
    if isinstance(goal, dict):
        return {k: (v.strip() if isinstance(v, str) else v)
                for k, v in sorted(goal.items())}
    return {}


def sorted_constraints(cs) -> list:
    if not isinstance(cs, list):
        return []
    def key(c):
        return c.get("constraint_id", "") if isinstance(c, dict) else str(c)
    return sorted(cs, key=key)


def validate_work_order(w: dict) -> list[Finding]:
    out: list[Finding] = []
    wid = w.get("work_order_id", "-")
    for f in REQUIRED:
        if not w.get(f):
            out.append(Finding(INVALID_WORK_SCHEMA, P1, wid,
                               f"work order missing {f}", {}))
    if not w.get("accountable_owner_id"):
        out.append(Finding(UNDEFINED_ACCOUNTABLE_OWNER, P1, wid,
                           "work order has no accountable owner "
                           "(AC-0006-035, INV-0006-13)", {}))
    if not w.get("outcome_contract"):
        out.append(Finding(UNDEFINED_OUTCOME, P1, wid,
                           "work order has no outcome contract "
                           "(D-0006-10, AC-0006-037)", {}))
    # context/memory must not be used as authority
    if w.get("authority_from_context"):
        out.append(Finding(CONTEXT_USED_AS_AUTHORITY, P0, wid,
                           "authority derived from context (INV-0006-04)", {}))
    if w.get("authority_from_memory"):
        out.append(Finding(MEMORY_USED_AS_AUTHORITY, P0, wid,
                           "authority derived from memory (INV-0006-05)", {}))
    # hash integrity
    if w.get("semantic_work_hash") and \
            w["semantic_work_hash"] != semantic_work_hash(w):
        out.append(Finding(INVALID_WORK_SCHEMA, P1, wid,
                           "semantic_work_hash does not match content", {}))
    if w.get("work_instance_hash") and \
            w["work_instance_hash"] != work_instance_hash(w):
        out.append(Finding(INVALID_WORK_SCHEMA, P1, wid,
                           "work_instance_hash does not match content", {}))
    return out

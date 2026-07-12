"""Plan Binding to SP0003 (SP0006 §9.9, D-0006-06/40/41, INV-0006-03).

A candidate plan (the "how" — an SP0003 plan envelope) is NOT authority
(D-0006-06, INV-0006-03): the plan proposes steps, targets, effects and budget
draws, but it can never grant capability or approval. A plan must BIND to a
canonical work order by referencing that work order's exact semantic and instance
identities; a plan that references the wrong identity, or that carries a grant, is
rejected. A material plan change re-opens impact, budget, lease and approval
revalidation (D-0006-41).

Governance tooling only; product runtime must never import it (INV-0006-46). It
opens NO external effect (INV-0006-47).
"""
from __future__ import annotations

from .model import Finding, P0, P1, INVALID_WORK_SCHEMA
from .canon import core_hash, semantic_work_hash, work_instance_hash

# a plan carrying any of these is trying to grant authority (D-0006-06 forbidden).
PLAN_GRANT_FIELDS = ("granted_capability", "approval")

# fields whose change makes a plan revision MATERIAL (D-0006-41).
MATERIAL_PLAN_FIELDS = ("steps", "targets", "effects", "budgets")

# revalidations re-opened by a material plan change (D-0006-41).
MATERIAL_REQUIREMENTS = ("impact_analysis", "budget_revalidation",
                         "lease_revalidation", "approval_revalidation")


def _work_semantic_hash(work_order: dict) -> str:
    return work_order.get("semantic_work_hash") or semantic_work_hash(work_order)


def _work_instance_hash(work_order: dict) -> str:
    return work_order.get("work_instance_hash") or work_instance_hash(work_order)


def bind_plan(work_order: dict, plan: dict) -> dict:
    """Produce a plan-binding record that references the work order's exact
    semantic and instance identities plus the governed envelopes the plan must
    respect. The record is explicitly non-authoritative (INV-0006-03)."""
    record = {
        "binding_kind": "PLAN_BINDING",
        "semantic_work_hash": _work_semantic_hash(work_order),
        "work_instance_hash": _work_instance_hash(work_order),
        "constraint_set": work_order.get("constraints", []),
        "outcome_contract": work_order.get("outcome_contract"),
        "budgets": work_order.get("budget_vector"),
        "dependency_envelope_ref": work_order.get("dependency_envelope_ref"),
        "plan_hash": core_hash(plan),
        "non_authoritative": True,
        "note": "plan is not authority (D-0006-06, INV-0006-03)",
    }
    record["binding_hash"] = core_hash({k: record.get(k) for k in
                                       ("semantic_work_hash", "work_instance_hash",
                                        "plan_hash", "constraint_set",
                                        "outcome_contract", "budgets",
                                        "dependency_envelope_ref")})
    return record


def validate_plan_binding(work_order: dict, plan: dict) -> list[Finding]:
    """Validate that a plan binds to the correct work order and grants no
    authority (AC-0006-126..130)."""
    out: list[Finding] = []
    subject = plan.get("plan_id", work_order.get("work_order_id", "-"))

    # 1. plan must reference the CORRECT semantic + instance identity.
    expected_sem = _work_semantic_hash(work_order)
    expected_inst = _work_instance_hash(work_order)
    if plan.get("semantic_work_hash") != expected_sem:
        out.append(Finding(INVALID_WORK_SCHEMA, P1, subject,
                           "plan does not reference the work order's "
                           "semantic_work_hash (D-0006-40)",
                           {"expected": expected_sem,
                            "actual": plan.get("semantic_work_hash")}))
    if plan.get("work_instance_hash") != expected_inst:
        out.append(Finding(INVALID_WORK_SCHEMA, P1, subject,
                           "plan does not reference the work order's "
                           "work_instance_hash (D-0006-40)",
                           {"expected": expected_inst,
                            "actual": plan.get("work_instance_hash")}))

    # 2. a plan must NOT carry capability/approval grants — plan is not authority.
    grants = [f for f in PLAN_GRANT_FIELDS if plan.get(f)]
    if grants:
        out.append(Finding(INVALID_WORK_SCHEMA, P0, subject,
                           "plan cannot grant authority; a plan is the 'how', not "
                           "a source of capability or approval "
                           "(D-0006-06, INV-0006-03)",
                           {"grant_fields": grants}))
    return out


def material_plan_change(old_plan: dict, new_plan: dict) -> dict:
    """Determine whether a plan revision is MATERIAL (changes steps/targets/
    effects/budgets). A material change re-opens impact, budget, lease and
    approval revalidation (D-0006-41, AC-0006-126..130)."""
    changed = [f for f in MATERIAL_PLAN_FIELDS
               if core_hash(old_plan.get(f)) != core_hash(new_plan.get(f))]
    material = bool(changed)
    return {
        "material": material,
        "changed_fields": changed,
        "requires": list(MATERIAL_REQUIREMENTS) if material else [],
    }

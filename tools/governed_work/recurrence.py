"""Recurring Work Contract + Recurring Instance + Per-Run Reauthorization
(SP0006 §9.10, D-0006-50/51, INV-0006-31/32).

A recurring CONTRACT (cadence / purpose / scope_ceiling / capability_ceiling /
per_run_budget / approval_policy / reauthorization_requirements / expiry /
termination_policy) is distinct from a recurring INSTANCE: each occurrence is a
NEW work instance with its own identity and its own admission. There is no
permanent recurring authorization (D-0006-51) — every run revalidates tenant,
requester/owner status, policy, leases, approvals, technology, safety, purpose,
target state and budgets. An approval token issued for a prior occurrence (a
different work_instance_hash) can never authorize a new run (AC-0006-151).
"""
from __future__ import annotations

from .model import (Finding, P1, RECURRENCE_REAUTHORIZATION_FAILED,
                    INVALID_WORK_SCHEMA, RECURRENCE_INSTANCE_STATES)
from .canon import core_hash, semantic_work_hash, work_instance_hash

# a recurring contract is well-formed only with every scoping/limit field.
CONTRACT_REQUIRED = ("cadence", "purpose", "scope_ceiling", "capability_ceiling",
                     "per_run_budget", "expiry", "termination_policy")

# the standing per-run reauthorization surface (D-0006-51). A contract MAY name a
# subset in reauthorization_requirements; these are the checks every run revisits.
REAUTHORIZATION_CHECKS = ("tenant", "requester_status", "owner_status", "policy",
                          "leases", "approvals", "technology", "safety",
                          "purpose", "target_state", "budgets")


def validate_contract(contract: dict) -> list[Finding]:
    """A recurring contract must fully bound every occurrence in advance."""
    out: list[Finding] = []
    cid = contract.get("contract_id", "-")
    for f in CONTRACT_REQUIRED:
        if contract.get(f) in (None, "", {}, []):
            out.append(Finding(INVALID_WORK_SCHEMA, P1, cid,
                               f"recurring contract missing {f} (D-0006-50)",
                               {"field": f}))
    return out


def instance_hash(contract: dict, occurrence: dict) -> str:
    """Occurrence-dependent instance identity (AC-0006-148). Binds the contract's
    semantic id to the occurrence sequence/time so two distinct occurrences of the
    same contract always produce distinct hashes."""
    contract_semantic = contract.get("semantic_work_hash") \
        or semantic_work_hash(contract.get("work_skeleton", {}) or contract)
    return core_hash({
        "contract_id": contract.get("contract_id"),
        "contract_semantic": contract_semantic,
        "occurrence_id": occurrence.get("occurrence_id"),
        "sequence": occurrence.get("sequence"),
        "scheduled_time": occurrence.get("scheduled_time"),
    })


def new_instance(contract: dict, occurrence: dict) -> dict:
    """Produce a recurring INSTANCE for one occurrence — a fresh per-run work
    instance derived from (but distinct from) the contract. Each occurrence gets a
    distinct instance identity; a recurring contract never authorizes a run by
    itself (D-0006-51)."""
    skeleton = dict(contract.get("work_skeleton", {}) or {})
    ih = instance_hash(contract, occurrence)
    recurrence_instance = {
        "contract_id": contract.get("contract_id"),
        "occurrence_id": occurrence.get("occurrence_id"),
        "sequence": occurrence.get("sequence"),
        "scheduled_time": occurrence.get("scheduled_time"),
    }
    instance = {
        **skeleton,
        "work_order_id": f"{contract.get('contract_id', 'contract')}"
                         f"#{occurrence.get('sequence', occurrence.get('occurrence_id'))}",
        "tenant_id": contract.get("tenant_id") or skeleton.get("tenant_id"),
        "purpose": contract.get("purpose"),
        "capability_ceiling": contract.get("capability_ceiling", {}),
        "allowed_scope": contract.get("scope_ceiling", {}),
        "budget_vector": contract.get("per_run_budget"),
        "expires_at": occurrence.get("expires_at") or contract.get("expiry"),
        "issued_at": occurrence.get("scheduled_time", ""),
        "recurrence_instance": recurrence_instance,
        "recurrence_contract_ref": contract.get("contract_id"),
        "instance_state": RECURRENCE_INSTANCE_STATES[0],  # SCHEDULED
        "instance_hash": ih,
        "requires_reauthorization": True,
        "status": "DRAFT",
    }
    instance["work_instance_hash"] = ih
    return instance


def reauthorize(contract: dict, instance: dict,
                current: dict) -> tuple[bool, list[Finding]]:
    """Per-run reauthorization (D-0006-51). Every run revalidates the standing
    checks; any required check missing or failed in `current` blocks the run. An
    approval token issued for a prior instance (different work_instance_hash)
    can never authorize a new run (AC-0006-151)."""
    out: list[Finding] = []
    subject = instance.get("work_order_id", contract.get("contract_id", "-"))
    required = contract.get("reauthorization_requirements") \
        or list(REAUTHORIZATION_CHECKS)
    ok = True

    for check in required:
        result = current.get(check)
        if result is None or result is False \
                or (isinstance(result, str) and result.upper() in
                    ("FAILED", "MISSING", "UNKNOWN", "STALE")):
            ok = False
            out.append(Finding(
                RECURRENCE_REAUTHORIZATION_FAILED, P1, subject,
                f"per-run reauthorization check '{check}' missing or failed "
                f"(D-0006-51)",
                {"check": check, "result": result,
                 "occurrence": instance.get("recurrence_instance")}))

    # an OLD approval token bound to a prior instance must not authorize this run.
    expected_ih = instance.get("work_instance_hash") \
        or instance.get("instance_hash")
    for token in _as_list(current.get("approval_tokens")):
        bound = token.get("work_instance_hash") or token.get("bound_instance_hash")
        # fail-closed: a token must POSITIVELY carry a recognized binding equal to
        # this run's instance hash. A token with no recognized binding key, or a
        # binding under an alternate key, cannot authorize the run (SWARM-M E9).
        if expected_ih and bound != expected_ih:
            ok = False
            out.append(Finding(
                RECURRENCE_REAUTHORIZATION_FAILED, P1, subject,
                "approval token not positively bound to this recurring instance "
                "cannot authorize the run (AC-0006-151, D-0006-51)",
                {"token_id": token.get("approval_id"),
                 "token_instance_hash": bound,
                 "expected_instance_hash": expected_ih}))

    return ok, out


def _as_list(v) -> list:
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple, set)) else [v]

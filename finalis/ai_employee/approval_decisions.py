"""Finalis Human Approval Gate — Decisions + Non-Transferable Grants
(CORE-A4.2, PART 2).

Pure, deterministic logic for a scoped human approval DECISION and a local,
non-transferable APPROVAL GRANT that authorizes only a future gated
transition. This module executes nothing: no LLM, no Tool Broker, no external
provider, no payment, no customer message. An approval grant is NOT OAuth,
GNAP, OAP, or a bearer token for external systems — it is a local Finalis
artifact that must be revalidated before any future use.

Fail-closed: an approval grant is valid only if EVERY factor of
ApprovalGrantValid holds. Approval can never average out a hard failure, never
convert a forbidden action into an allowed action, and never override consent,
evidence, RBAC or proof failures.
"""
from __future__ import annotations

import hashlib
import json

from .approvals import HONESTY_LABELS as _FOUNDATION_LABELS

DECISION_VERSION = "finalis-approval-decision-v1"
GRANT_VERSION = "finalis-approval-grant-v1"
GRANT_TYPE = "LOCAL_NON_TRANSFERABLE_APPROVAL_GRANT"
DECISION_GENESIS = "0" * 64

DECISIONS = {"APPROVE", "REJECT", "REQUEST_CHANGES", "REVOKE"}

# Approval-request lifecycle statuses reachable in PART 2.
APPROVED_STATUSES = {"APPROVED", "APPROVED_CONSUME_READY",
                     "APPROVED_BUT_NOT_CONSUMABLE"}
# Dual-control: an approved request that still awaits a further distinct
# approver before any grant is issued.
QUORUM_PENDING_STATUS = "APPROVED_PENDING_QUORUM"
TERMINAL_STATUSES = {"REJECTED", "CHANGES_REQUESTED", "EXPIRED", "REVOKED",
                     "SUPERSEDED", "CONSUMED", "BLOCKED", "NOT_IMPLEMENTED"}
# A decision may only be made from one of these request states. A request that
# is awaiting quorum stays decidable so the SECOND distinct approver can act.
DECIDABLE_STATUSES = {"PENDING", "CHALLENGE_REQUIRED", "REQUESTED",
                      QUORUM_PENDING_STATUS}
# Grant lifecycle states that are terminal regardless of timestamps.
TERMINAL_GRANT_STATUSES = {"REVOKED", "SUPERSEDED", "CONSUMED", "EXPIRED",
                           "INVALID", "BLOCKED"}

GRANT_STATUSES = {"ISSUED", "VALID", "INVALID", "EXPIRED", "REVOKED",
                  "SUPERSEDED", "CONSUMED", "NOT_CONSUMABLE",
                  "HASH_STATE_CHANGED", "PRECONDITION_FAILED", "BLOCKED"}
GRANT_USAGE_POLICIES = {"SINGLE_USE_READY", "MULTI_USE_NOT_IMPLEMENTED",
                        "CONSUMPTION_NOT_IMPLEMENTED"}

VALIDATION_STATUSES = {"VALID", "INVALID", "EXPIRED", "REVOKED", "SUPERSEDED",
                       "CONSUMED", "HASH_STATE_CHANGED", "PRECONDITION_FAILED",
                       "CHALLENGE_REQUIRED", "NOT_CONSUMABLE", "BLOCKED"}

# Role rank for approver-authority comparison (higher satisfies lower).
_ROLE_RANK = {"viewer": 0, "ai_worker": 0, "technician": 1, "accountant": 1,
              "operator": 1, "manager": 2, "owner": 3}

DECISION_HONESTY_LABELS = [
    "Approval does not execute the action.",
    "Approval authorizes only a future gated transition.",
    "Consume-check validates approval scope only; it does not execute the "
    "action.",
    "Approval does not override consent, evidence, RBAC or proof failures.",
    "AI Employee cannot approve its own work.",
    "Only an authorized human approver can approve.",
    "Self-approval is forbidden where policy requires separation of duties.",
    "Approval is scoped to this run, task, action and hash state.",
    "Approval grant must be revalidated before future use.",
    "Approval challenge is required for high-risk approvals.",
    "Tool Broker is not implemented in this mission.",
    "Human Approval Gate does not call external providers.",
    "This is not OAuth, GNAP, or an external bearer token.",
    "Server-side policy remains authoritative.",
    "This is not production autonomous execution.",
]


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _sha(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def role_satisfies(role: str, required: str) -> bool:
    return _ROLE_RANK.get(role, -1) >= _ROLE_RANK.get(required, 99)


# --- Approval decision -----------------------------------------------------
def _decision_core(d: dict) -> dict:
    volatile = {"decision_hash", "decision_chain_hash", "decision_time",
                "created_at", "honesty_labels"}
    return {k: v for k, v in d.items() if k not in volatile}


def decision_hash(decision: dict) -> str:
    return _sha(_decision_core(decision))


def build_decision(*, approval_decision_id, approval_request_id, tenant_id,
                   run_id, task_id, decider_user_id, decider_role, decision,
                   decision_reason, approval_request_hash_snapshot,
                   approval_package_hash_snapshot,
                   approval_challenge_hash_snapshot,
                   approval_precondition_hash_snapshot, viewed_package_hash,
                   acknowledgements, challenge_passed, decision_time,
                   previous_decision_hash=None) -> dict:
    if decision not in DECISIONS:
        raise ValueError(f"unknown decision {decision}")
    d = {
        "approval_decision_id": approval_decision_id,
        "approval_decision_version": DECISION_VERSION,
        "approval_request_id": approval_request_id, "tenant_id": tenant_id,
        "run_id": run_id, "task_id": task_id,
        "decider_user_id": decider_user_id, "decider_role": decider_role,
        "decider_actor_type": "HUMAN_USER", "decision": decision,
        "decision_reason": decision_reason,
        "approval_request_hash_snapshot": approval_request_hash_snapshot,
        "approval_package_hash_snapshot": approval_package_hash_snapshot,
        "approval_challenge_hash_snapshot": approval_challenge_hash_snapshot,
        "approval_precondition_hash_snapshot":
            approval_precondition_hash_snapshot,
        "viewed_package_hash": viewed_package_hash,
        "acknowledgements": dict(acknowledgements),
        "challenge_passed": bool(challenge_passed),
        "decision_time": decision_time,
        "honesty_labels": DECISION_HONESTY_LABELS,
    }
    d["decision_hash"] = decision_hash(d)
    d["decision_chain_hash"] = _sha({
        "previous_decision_hash": previous_decision_hash or DECISION_GENESIS,
        "decision_hash": d["decision_hash"]})
    return d


# --- Non-transferable approval grant ---------------------------------------
def grant_nonce_hash(*, nonce, approval_request_id, approval_decision_id,
                     run_state_hash, task_contract_hash,
                     policy_decision_hash) -> str:
    """Deterministic local nonce hash binding a grant to its exact decision
    and hash state. Production nonce hardening (entropy audit, single-use
    replay cache at consumption, KMS signing) is classified MISSING/NEXT."""
    return _sha({"nonce": nonce, "approval_request_id": approval_request_id,
                 "approval_decision_id": approval_decision_id,
                 "run_state_hash": run_state_hash,
                 "task_contract_hash": task_contract_hash,
                 "policy_decision_hash": policy_decision_hash})


def _grant_identity(g: dict) -> dict:
    """The immutable, scope-defining fields covered by approval_grant_hash.
    Mutable lifecycle fields (status/timestamps/validation) are excluded so the
    identity hash is stable across the grant lifecycle."""
    keys = ("approval_grant_id", "grant_version", "approval_request_id",
            "approval_decision_id", "tenant_id", "run_id", "task_id",
            "approval_action_type", "approval_scope", "allowed_next_transition",
            "task_contract_hash", "task_envelope_hash", "run_state_hash",
            "run_chain_hash", "run_event_merkle_root", "policy_decision_hash",
            "approval_package_hash", "approval_challenge_hash",
            "approval_decision_hash", "approval_precondition_hash",
            "grant_nonce_hash", "grant_type", "grant_usage_policy",
            "single_use", "expires_at")
    return {k: g[k] for k in keys}


def grant_hash(grant: dict) -> str:
    return _sha(_grant_identity(grant))


def build_grant(*, approval_grant_id, approval_request_id,
                approval_decision_id, tenant_id, run_id, task_id,
                approval_action_type, approval_scope, allowed_next_transition,
                task_contract_hash, task_envelope_hash, run_state_hash,
                run_chain_hash, run_event_merkle_root, policy_decision_hash,
                approval_package_hash, approval_challenge_hash,
                approval_decision_hash, approval_precondition_hash,
                grant_nonce_hash, grant_status, grant_usage_policy, single_use,
                expires_at, created_at) -> dict:
    if grant_status not in GRANT_STATUSES:
        raise ValueError(f"unknown grant_status {grant_status}")
    if grant_usage_policy not in GRANT_USAGE_POLICIES:
        raise ValueError(f"unknown grant_usage_policy {grant_usage_policy}")
    g = {
        "approval_grant_id": approval_grant_id,
        "grant_version": GRANT_VERSION,
        "approval_request_id": approval_request_id,
        "approval_decision_id": approval_decision_id, "tenant_id": tenant_id,
        "run_id": run_id, "task_id": task_id,
        "approval_action_type": approval_action_type,
        "approval_scope": approval_scope,
        "allowed_next_transition": allowed_next_transition,
        "task_contract_hash": task_contract_hash,
        "task_envelope_hash": task_envelope_hash,
        "run_state_hash": run_state_hash, "run_chain_hash": run_chain_hash,
        "run_event_merkle_root": run_event_merkle_root,
        "policy_decision_hash": policy_decision_hash,
        "approval_package_hash": approval_package_hash,
        "approval_challenge_hash": approval_challenge_hash,
        "approval_decision_hash": approval_decision_hash,
        "approval_precondition_hash": approval_precondition_hash,
        "grant_nonce_hash": grant_nonce_hash, "grant_type": GRANT_TYPE,
        "grant_usage_policy": grant_usage_policy, "single_use": bool(single_use),
        "expires_at": expires_at,
        # mutable lifecycle (excluded from grant_hash):
        "grant_status": grant_status, "created_at": created_at,
        "validated_at": None, "last_validation_status": None,
        "last_validation_reason": None, "consume_check_count": 0,
        "consumed_at": None, "consumed_by_run_event_id": None,
        "revoked_at": None, "superseded_at": None,
        "honesty_labels": DECISION_HONESTY_LABELS,
    }
    g["approval_grant_hash"] = grant_hash(g)
    return g


# --- Grant validation (fail-closed product) --------------------------------
def validate_grant(grant: dict, *, current: dict, expired: bool,
                   tool_broker_available: bool = False) -> dict:
    """Pure, fail-closed grant validation. `current` carries the freshly
    observed state hashes to compare against the grant's frozen scope. Returns
    a validation result; it does NOT mutate the grant and executes nothing.

    Precedence: terminal lifecycle states first, then freshness, then hash-
    state drift, then preconditions/policy, then consumability.
    """
    reasons = []
    drift = False

    # 1) terminal lifecycle states (already recorded on the grant). Check both
    # the timestamps AND grant_status so an inconsistent record still
    # fail-closes to its terminal state rather than falling through to VALID.
    if grant.get("revoked_at") or grant["grant_status"] == "REVOKED":
        return _vr("REVOKED", "approval grant was revoked", grant)
    if grant.get("superseded_at") or grant["grant_status"] == "SUPERSEDED":
        return _vr("SUPERSEDED", "approval grant was superseded by a newer "
                   "grant", grant)
    if grant.get("consumed_at") or grant["grant_status"] == "CONSUMED":
        return _vr("CONSUMED", "approval grant was already consumed", grant)
    if grant["grant_status"] in ("BLOCKED", "INVALID"):
        return _vr("BLOCKED" if grant["grant_status"] == "BLOCKED"
                   else "INVALID", "approval grant is not usable "
                   f"({grant['grant_status']})", grant)

    # 2) freshness
    if expired:
        return _vr("EXPIRED", "approval grant has expired", grant)

    # 3) hash-state drift — any scope/hash divergence invalidates the grant
    drift_fields = [
        ("tenant_id", "tenant"), ("run_id", "run"), ("task_id", "task"),
        ("approval_action_type", "action"),
        ("task_contract_hash", "task contract hash"),
        ("task_envelope_hash", "task envelope hash"),
        ("run_state_hash", "run state hash"),
        ("run_chain_hash", "run chain hash"),
        ("run_event_merkle_root", "run event merkle root"),
        ("policy_decision_hash", "policy decision hash"),
        ("approval_package_hash", "approval package hash"),
        ("approval_challenge_hash", "approval challenge hash"),
        ("approval_decision_hash", "approval decision hash"),
    ]
    # Fail-closed: compare every scope field unconditionally. A field the
    # caller omits from `current` reads as None and diverges from the grant's
    # frozen value, so an incomplete `current` flags drift rather than silently
    # passing (no fail-open by omission).
    for key, label in drift_fields:
        if current.get(key) != grant.get(key):
            drift = True
            reasons.append(f"{label} changed since approval")
    if drift:
        r = _vr("HASH_STATE_CHANGED",
                "; ".join(reasons), grant)
        r["drift_detected"] = True
        return r

    # 4) preconditions still hold (server-review markers must not be failed)
    if current.get("precondition_status") == "FAILED":
        return _vr("PRECONDITION_FAILED",
                   current.get("precondition_reason",
                               "approval preconditions no longer hold"), grant)

    # 5) forbidden action can never be unlocked by a grant
    if current.get("action_always_blocked"):
        return _vr("BLOCKED", "action is always blocked; approval cannot "
                   "convert a forbidden action into an allowed one", grant)

    # 6) execution requires Tool Broker, which is not implemented
    if current.get("tool_broker_required") and not tool_broker_available:
        r = _vr("NOT_CONSUMABLE", "Tool Broker is required to execute this "
                "action and is not implemented in this mission", grant)
        return r

    return _vr("VALID", "approval grant scope and hash state are intact", grant)


def _vr(status: str, reason: str, grant: dict) -> dict:
    return {"grant_validation_status": status, "reason": reason,
            "drift_detected": False,
            "allowed_next_transition": grant.get("allowed_next_transition"),
            "precondition_status": "OK" if status == "VALID" else status,
            "can_execute_now": False}

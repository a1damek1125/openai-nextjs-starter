"""Finalis Human Approval Gate Foundation (CORE-A4.1, PART 1).

Pure, deterministic logic for a scoped, policy-bound, replay-resistant human
approval FOUNDATION: the policy decision capsule, the canonical approval
request / package / challenge envelopes and their hashes, the precondition
contract, and the risk-based approval policy matrix.

PART 1 creates and exposes approval requests only. It does NOT approve,
reject, grant, or consume anything, and it executes nothing — no LLM, no tool,
no external provider. Creating an approval request does not approve or execute
the action; approval decisions and grants arrive in CORE-A4.2. Server-side
policy remains authoritative; an approval can never convert a forbidden action
into an allowed one.
"""
from __future__ import annotations

import hashlib
import json

APPROVAL_ENVELOPE_VERSION = "finalis-approval-request-v1"
PACKAGE_VERSION = "finalis-approval-package-v1"
CHALLENGE_VERSION = "finalis-approval-challenge-v1"
POLICY_CAPSULE_VERSION = "finalis-policy-capsule-v1"
POLICY_ENGINE = "LOCAL_DETERMINISTIC_CORE_A4"
POLICY_ENGINE_VERSION = "1"

# PART 1 statuses only — no APPROVED/REJECTED/REVOKED decisions here.
APPROVAL_STATUSES = {"REQUESTED", "PENDING", "CHALLENGE_REQUIRED", "EXPIRED",
                     "BLOCKED", "NOT_IMPLEMENTED"}

CHALLENGE_TYPES = {"CHECKBOX_ATTESTATION", "ACTION_SCOPE_CONFIRMATION",
                   "RISK_ACKNOWLEDGEMENT", "HASH_STATE_ACKNOWLEDGEMENT",
                   "SUBJECT_ACCESS_ACKNOWLEDGEMENT"}
CHALLENGE_STATUSES = {"CREATED", "REQUIRED", "EXPIRED", "NOT_REQUIRED"}

# An approval can NEVER unlock these — recorded on every package.
FORBIDDEN_UNLOCKS = [
    "override_consent", "override_rbac", "rewrite_evidence", "delete_evidence",
    "hide_proof_failure", "approve_own_work",
    "execute_payment_without_tool_broker",
    "send_customer_message_without_policy", "call_external_provider_directly",
    "claim_legal_validity", "claim_production_readiness", "reuse_for_other_run",
    "reuse_for_other_task", "reuse_for_other_action",
    "reuse_after_hash_state_change",
]

# Actions that stay blocked even WITH a human approval (approval cannot convert
# a forbidden action into an allowed one).
ALWAYS_BLOCKED_ACTIONS = {
    "override_consent", "rewrite_evidence", "delete_evidence",
    "approve_own_work", "self_approve_quote", "approve_quote",
    "execute_payment", "call_external_provider", "change_ai_permissions",
    "grant_admin", "access_cross_tenant", "hide_proof_failure",
    "claim_legal_validity", "claim_production_readiness", "override_policy",
    "verify_memory", "execute_merge", "sync_external_crm_write",
    "perform_oauth_flow",
}

HONESTY_LABELS = [
    "Approval request creation does not approve or execute the action.",
    "Approval authorizes only a future gated transition after a valid human "
    "decision.",
    "Approval does not override consent, evidence, RBAC or proof failures.",
    "Approval is scoped to this run, task, action and hash state.",
    "Approval challenge is required for high-risk approvals.",
    "Approval decisions and grants are implemented in CORE-A4.2.",
    "Tool Broker is not implemented in this mission.",
    "Human Approval Gate does not call external providers.",
    "Safe approval view may omit sensitive fields; omitted fields do not "
    "change server-side approval truth.",
    "This is not OAuth, GNAP, or an external bearer token.",
    "Server-side policy remains authoritative.",
    "This is not production autonomous execution.",
]

SAFE_VIEW_OMITTED = ["task_description", "approval_scope_detail",
                     "policy_input"]


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _sha(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


# --- Risk-based approval policy matrix -------------------------------------
def _approver_role(risk: str) -> tuple:
    """(required_approver_role, required_approver_count, dual_control)."""
    return {
        "LOW": ("manager", 1, False),
        "MEDIUM": ("manager", 1, False),
        "HIGH": ("owner", 1, False),
        "CRITICAL": ("owner", 2, True),
    }.get(risk, ("owner", 1, False))


def challenge_required(risk: str) -> bool:
    return risk in ("HIGH", "CRITICAL")


APPROVAL_POLICY_MATRIX = {
    "LOW": {"human_approval_required": False, "challenge_required": False,
            "required_approver_role": "manager", "required_approver_count": 1,
            "dual_control": False,
            "note": "read-only/draft-only work may not require approval"},
    "MEDIUM": {"human_approval_required": True, "challenge_required": False,
               "required_approver_role": "manager",
               "required_approver_count": 1, "dual_control": False,
               "note": "one authorized human approval before customer-facing "
                       "send"},
    "HIGH": {"human_approval_required": True, "challenge_required": True,
             "required_approver_role": "owner", "required_approver_count": 1,
             "dual_control": False,
             "note": "manager/owner approval + anti-rubber-stamp challenge; "
                     "dual-control-ready"},
    "CRITICAL": {"human_approval_required": True, "challenge_required": True,
                 "required_approver_role": "owner",
                 "required_approver_count": 2, "dual_control": True,
                 "note": "owner/compliance approval + challenge + dual "
                         "control; many direct actions remain blocked"},
}


def build_policy_capsule(*, tenant_id, run_id, task_id, approval_request_id,
                         action_type, subject_type, subject_id, risk_level,
                         authority_decision, authority_hard_fail,
                         consent_requirement, evidence_requirement,
                         proof_requirement, allowed_next_transition,
                         created_at) -> dict:
    """A deterministic policy decision capsule. No LLM generates policy; the
    matrix is a pure function of (action_type, risk, authority, requirements).
    """
    role, count, dual = _approver_role(risk_level)
    always_blocked = action_type in ALWAYS_BLOCKED_ACTIONS \
        or authority_decision == "BLOCKED" or authority_hard_fail
    blocked_reasons = []
    if action_type in ALWAYS_BLOCKED_ACTIONS:
        blocked_reasons.append(
            f"'{action_type}' is always blocked; approval cannot convert a "
            "forbidden action into an allowed action")
    if authority_decision == "BLOCKED" or authority_hard_fail:
        blocked_reasons.append("authority decision is BLOCKED (hard-fail "
                               "dominance)")

    policy_input = {
        "action_type": action_type, "subject_type": subject_type,
        "subject_id": subject_id, "risk_level": risk_level,
        "authority_decision": authority_decision,
        "authority_hard_fail": bool(authority_hard_fail),
        "consent_requirement": bool(consent_requirement),
        "evidence_requirement": bool(evidence_requirement),
        "proof_requirement": bool(proof_requirement),
    }
    required_acks = ["risk_acknowledged", "scope_acknowledged",
                     "future_execution_acknowledged", "no_override_acknowledged",
                     "limitations_acknowledged"]
    if evidence_requirement:
        required_acks.append("evidence_acknowledged")
    if consent_requirement:
        required_acks.append("consent_acknowledged")
    if proof_requirement:
        required_acks.append("proof_acknowledged")

    policy_output = {
        "required_approver_role": role, "required_approver_count": count,
        "dual_control_required": dual, "self_approval_forbidden": True,
        "ai_approval_forbidden": True,
        "subject_access_required": bool(subject_id),
        "challenge_required": challenge_required(risk_level)
        and not always_blocked,
        "allowed_next_transition": allowed_next_transition,
        "blocked_reasons": blocked_reasons,
        "required_acknowledgements": sorted(required_acks),
        "forbidden_unlocks": list(FORBIDDEN_UNLOCKS),
    }
    capsule = {
        "policy_decision_id": approval_request_id + "-policy",
        "policy_decision_version": POLICY_CAPSULE_VERSION,
        "tenant_id": tenant_id, "run_id": run_id, "task_id": task_id,
        "approval_request_id": approval_request_id,
        "policy_engine": POLICY_ENGINE,
        "policy_engine_version": POLICY_ENGINE_VERSION,
        "action_type": action_type, "subject_type": subject_type,
        "subject_id": subject_id, "risk_level": risk_level,
        "authority_decision": authority_decision,
        "authority_hard_fail": bool(authority_hard_fail),
        "consent_requirement": bool(consent_requirement),
        "evidence_requirement": bool(evidence_requirement),
        "proof_requirement": bool(proof_requirement),
        **{k: policy_output[k] for k in (
            "required_approver_role", "required_approver_count",
            "dual_control_required", "self_approval_forbidden",
            "ai_approval_forbidden", "subject_access_required",
            "challenge_required", "allowed_next_transition", "blocked_reasons",
            "required_acknowledgements", "forbidden_unlocks")},
        "policy_input": policy_input,
        "policy_input_hash": _sha(policy_input),
        "policy_output_hash": _sha(policy_output),
        "always_blocked": always_blocked, "created_at": created_at,
    }
    return capsule


def policy_decision_hash(capsule: dict) -> str:
    core = {k: v for k, v in capsule.items()
            if k not in ("policy_decision_hash", "created_at")}
    return _sha(core)


# --- Approval package ------------------------------------------------------
def build_package(*, approval_request_id, tenant_id, run_id, task_id,
                  task_contract_hash, task_envelope_hash, run_chain_hash,
                  run_state_hash, run_event_merkle_root, assigned_ai_employee_id,
                  requester_user_id, capsule, approval_action_type,
                  approval_scope, allowed_next_transition, risk_level,
                  authority_decision, authority_reason, requires_consent_check,
                  requires_evidence_check, requires_tool_broker, evidence_refs,
                  proof_report_refs, consent_refs, subject_refs,
                  data_scope_refs, preconditions, challenge) -> dict:
    warnings = ["Approval does not override consent, evidence, RBAC or proof "
                "failures."]
    return {
        "package_version": PACKAGE_VERSION,
        "approval_request_id": approval_request_id, "tenant_id": tenant_id,
        "run_id": run_id, "task_id": task_id,
        "task_contract_hash": task_contract_hash,
        "task_envelope_hash": task_envelope_hash,
        "run_chain_hash": run_chain_hash, "run_state_hash": run_state_hash,
        "run_event_merkle_root": run_event_merkle_root,
        "assigned_ai_employee_id": assigned_ai_employee_id,
        "requester_user_id": requester_user_id,
        "policy_decision_capsule": capsule,
        "policy_decision_hash": policy_decision_hash(capsule),
        "approval_action_type": approval_action_type,
        "approval_scope": approval_scope,
        "allowed_next_transition": allowed_next_transition,
        "risk_level": risk_level, "authority_decision": authority_decision,
        "authority_reason": authority_reason,
        "requires_human_approval": True,
        "requires_consent_check": bool(requires_consent_check),
        "requires_evidence_check": bool(requires_evidence_check),
        "requires_tool_broker": bool(requires_tool_broker),
        "evidence_refs": list(evidence_refs or []),
        "proof_report_refs": list(proof_report_refs or []),
        "consent_refs": list(consent_refs or []),
        "subject_refs": list(subject_refs or []),
        "data_scope_refs": list(data_scope_refs or []),
        "preconditions": preconditions,
        "blocked_reasons": capsule["blocked_reasons"],
        "warnings": warnings,
        "limitations": ["Approval decisions and grants are implemented in "
                        "CORE-A4.2."],
        "forbidden_unlocks": list(FORBIDDEN_UNLOCKS),
        "required_acknowledgements": capsule["required_acknowledgements"],
        "approval_challenge": challenge, "honesty_labels": HONESTY_LABELS,
    }


def package_hash(package: dict) -> str:
    core = {k: v for k, v in package.items() if k != "package_hash"}
    return _sha(core)


# --- Approval challenge (anti-rubber-stamp) --------------------------------
def build_challenge(*, approval_request_id, tenant_id, viewed_package_hash,
                    required_acknowledgements, risk_level, subject_required,
                    created_at, expires_at, required: bool) -> dict:
    ctypes = ["RISK_ACKNOWLEDGEMENT", "ACTION_SCOPE_CONFIRMATION",
              "HASH_STATE_ACKNOWLEDGEMENT", "CHECKBOX_ATTESTATION"]
    if subject_required:
        ctypes.append("SUBJECT_ACCESS_ACKNOWLEDGEMENT")
    challenge = {
        "approval_challenge_id": approval_request_id + "-challenge",
        "approval_request_id": approval_request_id, "tenant_id": tenant_id,
        "challenge_version": CHALLENGE_VERSION,
        "challenge_type": sorted(ctypes),
        "viewed_package_hash": viewed_package_hash,
        "required_summary_points": [
            "the exact action being approved", "the run and task it is scoped "
            "to", "the risk level", "the hash state at review time"],
        "required_acknowledgements": sorted(required_acknowledgements),
        "required_confirmation_fields": sorted(required_acknowledgements),
        "created_at": created_at, "expires_at": expires_at,
        "challenge_status": "REQUIRED" if required else "NOT_REQUIRED",
    }
    challenge["challenge_hash"] = challenge_hash(challenge)
    return challenge


def challenge_hash(challenge: dict) -> str:
    core = {k: v for k, v in challenge.items()
            if k not in ("challenge_hash", "created_at")}
    return _sha(core)


# --- Preconditions ---------------------------------------------------------
def build_preconditions(*, tenant_id, run_id, task_id, approval_action_type,
                        subject_type, subject_id, task_contract_hash,
                        task_envelope_hash, run_state_hash, run_chain_hash,
                        run_event_merkle_root, policy_decision_hash,
                        authority_decision, consent_required, evidence_required,
                        proof_required, challenge_required) -> dict:
    return {
        "tenant_id_unchanged": tenant_id, "run_id_unchanged": run_id,
        "task_id_unchanged": task_id,
        "approval_action_type_unchanged": approval_action_type,
        "subject_type_unchanged": subject_type,
        "subject_id_unchanged": subject_id,
        "task_contract_hash_unchanged": task_contract_hash,
        "task_envelope_hash_unchanged": task_envelope_hash,
        "run_state_hash_unchanged": run_state_hash,
        "run_chain_hash_unchanged": run_chain_hash,
        "run_event_merkle_root_unchanged": run_event_merkle_root,
        "policy_decision_hash_unchanged": policy_decision_hash,
        "authority_not_blocked": authority_decision != "BLOCKED",
        "consent_not_revoked_if_required": ("SERVER_REVIEW_REQUIRED"
                                            if consent_required else
                                            "NOT_APPLICABLE"),
        "evidence_proof_not_failed_if_required": ("SERVER_REVIEW_REQUIRED"
                                                  if (evidence_required
                                                      or proof_required)
                                                  else "NOT_APPLICABLE"),
        "approval_not_expired": True,
        "approval_challenge_required": bool(challenge_required),
    }


def precondition_hash(preconditions: dict) -> str:
    return _sha(preconditions)


def request_hash(request_core: dict) -> str:
    """Hash of the approval request minus its own hash and volatile fields."""
    core = {k: v for k, v in request_core.items()
            if k not in ("approval_request_hash", "created_at", "updated_at",
                         "honesty_labels")}
    return _sha(core)


def safe_view(request_json: dict) -> dict:
    def redact(obj):
        if isinstance(obj, dict):
            return {k: ("<omitted in safe view>" if k in SAFE_VIEW_OMITTED
                        else redact(v)) for k, v in obj.items()}
        if isinstance(obj, list):
            return [redact(v) for v in obj]
        return obj
    view = redact(request_json)
    view["redaction_profile"] = "SAFE_APPROVAL_VIEW"
    view["redaction_manifest"] = {
        "omitted_fields": sorted(SAFE_VIEW_OMITTED),
        "note": "Safe approval view may omit sensitive fields; omitted fields "
                "do not change server-side approval truth. Safe approval view "
                "is not a separate approval."}
    view["redaction_manifest_hash"] = _sha(view["redaction_manifest"])
    return view

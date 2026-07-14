"""Finalis Secure Work Intake — Canonical Task Envelope + Task Contract
(CORE-A2). Pure, deterministic logic: task-type taxonomy, canonical JSON +
envelope/contract hashing, purpose/data-scope derivation, risk classification
and untrusted-input detection.

Task intake is NOT execution. Nothing here calls an LLM or an external
provider, and task text is always untrusted: it can populate advisory flags
but can never change identity, role, tenant, authority decision or data
scopes. The CORE-A1 authority pre-check remains authoritative for the
decision; this module only records what came in and what Finalis accepts.
"""
from __future__ import annotations

import hashlib
import json

ENVELOPE_VERSION = "finalis-task-envelope-v1"
CONTRACT_VERSION = "finalis-task-contract-v1"

SOURCE_CHANNELS = {
    "WEB", "API", "SLACK_NOT_IMPLEMENTED", "TEAMS_NOT_IMPLEMENTED",
    "EMAIL_NOT_IMPLEMENTED", "SCHEDULED_NOT_IMPLEMENTED",
    "PROACTIVE_NOT_IMPLEMENTED",
}

TASK_STATUSES = {
    "CREATED", "ACCEPTED", "BLOCKED", "NEEDS_CLARIFICATION",
    "WAITING_FOR_CONTEXT", "DRAFT_READY", "CANCELLED", "FAILED", "EXPIRED",
    "STALE", "COMPLETED_MANUAL", "NOT_IMPLEMENTED",
}

RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

# Data scopes that are ALWAYS forbidden — deny-by-default, never expandable by
# task text.
ALWAYS_FORBIDDEN_DATA_SCOPES = [
    "secrets", "tokens", "private_keys", "cross_tenant_data",
    "raw_evidence_content_without_permission",
    "customer_sensitive_data_without_permission", "payment_credentials",
    "oauth_tokens", "internal_provider_credentials", "hidden_system_prompts",
    "unapproved_external_sources",
]

# task_type -> mapping. proposed_action feeds the CORE-A1 authority pre-check.
TASK_TYPES: dict[str, dict] = {
    "case_summary": {
        "segment": "casework", "action": "draft_case_summary",
        "purpose_category": "CASEWORK", "risk": "LOW",
        "outputs": ["draft_summary"], "scopes": ["case_metadata"]},
    "case_blockers": {
        "segment": "casework", "action": "read_case_blockers",
        "purpose_category": "CASEWORK", "risk": "LOW",
        "outputs": ["read_only_summary"], "scopes": ["case_metadata"]},
    "customer_profile_summary": {
        "segment": "customer_support", "action": "customer_profile_summary",
        "purpose_category": "CUSTOMER_SUPPORT", "risk": "LOW",
        "outputs": ["draft_summary"],
        "scopes": ["customer_profile", "consent_status"]},
    "customer_reply_draft": {
        "segment": "customer_support", "action": "draft_customer_reply",
        "purpose_category": "CUSTOMER_SUPPORT", "risk": "MEDIUM",
        "outputs": ["draft_message"],
        "scopes": ["customer_profile", "consent_status", "case_metadata"]},
    "consent_status_check": {
        "segment": "customer_support", "action": "consent_status_check",
        "purpose_category": "CUSTOMER_SUPPORT", "risk": "LOW",
        "outputs": ["read_only_summary"], "scopes": ["consent_status"]},
    "memory_suggestion": {
        "segment": "casework", "action": "suggest_memory",
        "purpose_category": "CASEWORK", "risk": "MEDIUM",
        "outputs": ["draft_suggestion"],
        "scopes": ["customer_profile", "memory_summary"]},
    "merge_proposal": {
        "segment": "casework", "action": "propose_merge",
        "purpose_category": "CASEWORK", "risk": "HIGH",
        "outputs": ["approval_request"],
        "scopes": ["customer_profile"]},
    "evidence_report_request": {
        "segment": "evidence", "action": "share_evidence_report",
        "purpose_category": "EVIDENCE_VERIFICATION", "risk": "HIGH",
        "outputs": ["approval_request"],
        "scopes": ["evidence_report_metadata", "proof_report"]},
    "evidence_proof_explanation": {
        "segment": "evidence", "action": "evidence_proof_explanation",
        "purpose_category": "EVIDENCE_VERIFICATION", "risk": "MEDIUM",
        "outputs": ["draft_explanation"],
        "scopes": ["evidence_report_metadata", "proof_report"]},
    "quote_summary": {
        "segment": "sales", "action": "draft_quote_summary",
        "purpose_category": "SALES", "risk": "MEDIUM",
        "outputs": ["draft_summary"], "scopes": ["quote_metadata"]},
    "quote_readiness_check": {
        "segment": "sales", "action": "quote_readiness_check",
        "purpose_category": "SALES", "risk": "HIGH",
        "outputs": ["approval_request"],
        "scopes": ["quote_metadata", "case_metadata"]},
    "payment_followup_draft": {
        "segment": "finance", "action": "draft_payment_reminder",
        "purpose_category": "FINANCE", "risk": "HIGH",
        "outputs": ["draft_message"],
        "scopes": ["payment_status_summary", "quote_metadata"]},
    "project_status_summary": {
        "segment": "project_management", "action": "draft_project_status",
        "purpose_category": "PROJECT_MANAGEMENT", "risk": "LOW",
        "outputs": ["draft_summary"], "scopes": ["project_status"]},
    "operations_blocker_check": {
        "segment": "operations", "action": "operations_blocker_check",
        "purpose_category": "OPERATIONS", "risk": "LOW",
        "outputs": ["read_only_summary"], "scopes": ["project_status"]},
    "marketing_content_draft": {
        "segment": "marketing", "action": "draft_marketing_content",
        "purpose_category": "MARKETING", "risk": "MEDIUM",
        "outputs": ["draft_content"],
        "scopes": ["marketing_campaign_metadata"]},
    "marketing_campaign_summary": {
        "segment": "marketing", "action": "marketing_campaign_summary",
        "purpose_category": "MARKETING", "risk": "LOW",
        "outputs": ["read_only_summary"],
        "scopes": ["marketing_campaign_metadata"]},
    "hr_onboarding_checklist": {
        "segment": "hr_admin", "action": "hr_onboarding_checklist",
        "purpose_category": "HR_ADMIN", "risk": "MEDIUM",
        "outputs": ["draft_checklist"], "scopes": ["project_status"]},
    "it_access_review_summary": {
        "segment": "it_security", "action": "it_access_review_summary",
        "purpose_category": "IT_SECURITY", "risk": "HIGH",
        "outputs": ["approval_request"], "scopes": ["project_status"]},
    "field_service_visit_summary": {
        "segment": "field_service", "action": "field_service_visit_summary",
        "purpose_category": "FIELD_SERVICE", "risk": "MEDIUM",
        "outputs": ["draft_summary"], "scopes": ["case_metadata"]},
    "research_brief": {
        "segment": "research_reporting", "action": "draft_research_brief",
        "purpose_category": "RESEARCH_REPORTING", "risk": "MEDIUM",
        "outputs": ["draft_brief"], "scopes": ["research_sources"]},
    "compliance_gap_check": {
        "segment": "compliance", "action": "compliance_gap_check",
        "purpose_category": "COMPLIANCE", "risk": "HIGH",
        "outputs": ["approval_request"],
        "scopes": ["case_metadata", "contract_history"]},
    # A future-ready task type whose action is not implemented in CORE-A1 —
    # its authority pre-check returns NOT_IMPLEMENTED (fail-closed).
    "sop_change_proposal": {
        "segment": "operations", "action": "propose_sop_change",
        "purpose_category": "OPERATIONS", "risk": "MEDIUM",
        "outputs": ["approval_request"], "scopes": ["project_status"]},
}

# Task types that cannot be assembled without a subject reference.
SUBJECT_REQUIRED = {
    "case_summary", "case_blockers", "customer_reply_draft",
    "customer_profile_summary", "consent_status_check", "memory_suggestion",
    "merge_proposal", "evidence_report_request", "evidence_proof_explanation",
    "quote_summary", "quote_readiness_check", "payment_followup_draft",
}

HONESTY_LABELS = [
    "Task creation does not execute side effects.",
    "AI Employee can propose work but cannot bypass policy.",
    "Task text is treated as untrusted input.",
    "Task contract defines the accepted purpose, scope and boundaries.",
    "Input security flags are advisory; server-side authority decision "
    "remains authoritative.",
    "Risk level is advisory; server-side policy decision is authoritative.",
    "Sensitive actions require human approval.",
    "Consent checks are required before outreach.",
    "Evidence checks are required before proof claims.",
    "Tool Broker is not implemented in this mission.",
    "Run Ledger is not implemented in this mission.",
    "Slack intake is not implemented in this mission.",
    "Microsoft Teams intake is not implemented in this mission.",
    "Email intake is not implemented in this mission.",
    "Scheduled/proactive intake is not implemented in this mission.",
    "Server-side policy remains authoritative.",
    "This is not production autonomous execution.",
]

FORBIDDEN_SIDE_EFFECTS = [
    "send_customer_message", "execute_payment", "approve_quote",
    "override_consent", "rewrite_evidence", "delete_evidence",
    "sync_external_crm_write", "call_external_provider", "change_case_outcome",
]

# --- Untrusted-input detection (deterministic, advisory) -------------------
# substring (lowercased) -> input_security_flag
_FLAG_PATTERNS = [
    ("ignore previous", "PROMPT_INJECTION_ATTEMPT"),
    ("ignore all previous", "PROMPT_INJECTION_ATTEMPT"),
    ("ignore all instructions", "PROMPT_INJECTION_ATTEMPT"),
    ("disregard previous", "PROMPT_INJECTION_ATTEMPT"),
    ("change my role", "ROLE_ESCALATION_ATTEMPT"),
    ("make me owner", "ROLE_ESCALATION_ATTEMPT"),
    ("make ai employee admin", "ROLE_ESCALATION_ATTEMPT"),
    ("make me admin", "ROLE_ESCALATION_ATTEMPT"),
    ("disable policy", "POLICY_OVERRIDE_ATTEMPT"),
    ("disable the policy", "POLICY_OVERRIDE_ATTEMPT"),
    ("override policy", "POLICY_OVERRIDE_ATTEMPT"),
    ("bypass policy", "POLICY_OVERRIDE_ATTEMPT"),
    ("override consent", "CONSENT_OVERRIDE_ATTEMPT"),
    ("without consent", "CONSENT_OVERRIDE_ATTEMPT"),
    ("mark memory verified", "EVIDENCE_OVERRIDE_ATTEMPT"),
    ("mark verified", "EVIDENCE_OVERRIDE_ATTEMPT"),
    ("hide proof", "EVIDENCE_OVERRIDE_ATTEMPT"),
    ("hide the proof", "EVIDENCE_OVERRIDE_ATTEMPT"),
    ("delete evidence", "EVIDENCE_OVERRIDE_ATTEMPT"),
    ("without approval", "UNAPPROVED_SEND_ATTEMPT"),
    ("send this to customer", "UNAPPROVED_SEND_ATTEMPT"),
    ("call stripe", "EXTERNAL_PROVIDER_ATTEMPT"),
    ("external provider", "EXTERNAL_PROVIDER_ATTEMPT"),
    ("perform oauth", "OAUTH_ATTEMPT"),
    ("oauth now", "OAUTH_ATTEMPT"),
    ("legally valid", "LEGAL_VALIDITY_OVERCLAIM"),
    ("legal validity", "LEGAL_VALIDITY_OVERCLAIM"),
    ("production-ready", "PRODUCTION_READINESS_OVERCLAIM"),
    ("production ready", "PRODUCTION_READINESS_OVERCLAIM"),
    ("all tenants", "DATA_SCOPE_EXPANSION_ATTEMPT"),
    ("expand data scope", "DATA_SCOPE_EXPANSION_ATTEMPT"),
    ("include secrets", "DATA_SCOPE_EXPANSION_ATTEMPT"),
    ("remove forbidden", "DATA_SCOPE_EXPANSION_ATTEMPT"),
    ("mark this task completed", "TASK_COMPLETION_FORGERY_ATTEMPT"),
    ("mark task completed", "TASK_COMPLETION_FORGERY_ATTEMPT"),
]

# substring (lowercased) -> unsafe requested action (CORE-A1 forbidden name)
_UNSAFE_ACTION_PATTERNS = [
    ("approve the quote", "approve_quote"),
    ("approve quote", "approve_quote"),
    ("self approve", "self_approve_quote"),
    ("send this to customer", "send_customer_message"),
    ("mark memory verified", "verify_memory"),
    ("verify memory", "verify_memory"),
    ("delete evidence", "delete_evidence"),
    ("rewrite evidence", "rewrite_evidence"),
    ("sync to external crm", "sync_external_crm_write"),
    ("sync external", "sync_external_crm_write"),
    ("call stripe", "execute_payment"),
    ("execute payment", "execute_payment"),
    ("perform oauth", "perform_oauth_flow"),
    ("change case outcome", "change_case_outcome"),
    ("disable policy", "disable_policy"),
    ("make ai employee admin", "change_ai_permissions"),
    ("change my role", "change_ai_permissions"),
    ("mark production-ready", "claim_production_readiness"),
    ("all tenants", "access_cross_tenant"),
]


def detect_input_security_flags(*texts: str) -> list:
    blob = " ".join(t or "" for t in texts).lower()
    flags = []
    for needle, flag in _FLAG_PATTERNS:
        if needle in blob and flag not in flags:
            flags.append(flag)
    return flags or ["NONE"]


def detect_unsafe_requested_actions(*texts: str) -> list:
    blob = " ".join(t or "" for t in texts).lower()
    out = []
    for needle, action in _UNSAFE_ACTION_PATTERNS:
        if needle in blob and action not in out:
            out.append(action)
    return out


# --- Data scopes -----------------------------------------------------------
def derive_data_scopes(task_type: str) -> tuple:
    """Allowed scopes derive ONLY from the task type mapping; forbidden scopes
    always include the deny-by-default set. Task text can never expand these."""
    meta = TASK_TYPES.get(task_type, {})
    allowed = sorted(set(meta.get("scopes", [])))
    return allowed, list(ALWAYS_FORBIDDEN_DATA_SCOPES)


def classify_risk(task_type: str, unsafe_actions: list) -> tuple:
    """(risk_level, reason). A detected critical unsafe action raises the
    advisory risk to CRITICAL, but never changes the authority decision."""
    base = TASK_TYPES.get(task_type, {}).get("risk", "MEDIUM")
    if unsafe_actions:
        return "CRITICAL", ("task text requested unsafe action(s): "
                            + ", ".join(unsafe_actions))
    return base, f"default risk for task type '{task_type}'"


# --- Canonical JSON + hashing ----------------------------------------------
def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _sha(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def build_envelope(*, tenant_id, requester_user_id, assigned_ai_employee_id,
                   source_channel, source_thread_ref, source_message_ref,
                   task_type, segment, subject_type, subject_id, task_title,
                   task_description, priority, due_at, expires_at, task_purpose,
                   purpose_category, authority_decision, authority_reason,
                   risk_level, requires_human_approval, requires_consent_check,
                   requires_evidence_check, requires_tool_broker,
                   forbidden_side_effects, input_security_flags) -> dict:
    """Canonical task envelope — WHAT CAME IN. Deterministic; excludes
    task_id, timestamps and the hashes themselves."""
    return {
        "envelope_version": ENVELOPE_VERSION, "tenant_id": tenant_id,
        "requester_user_id": requester_user_id,
        "assigned_ai_employee_id": assigned_ai_employee_id,
        "source_channel": source_channel,
        "source_thread_ref": source_thread_ref,
        "source_message_ref": source_message_ref, "task_type": task_type,
        "segment": segment, "subject_type": subject_type,
        "subject_id": subject_id, "task_title": task_title,
        "task_description": task_description, "priority": priority,
        "due_at": due_at, "expires_at": expires_at,
        "task_purpose": task_purpose, "purpose_category": purpose_category,
        "authority_decision": authority_decision,
        "authority_reason": authority_reason, "risk_level": risk_level,
        "requires_human_approval": bool(requires_human_approval),
        "requires_consent_check": bool(requires_consent_check),
        "requires_evidence_check": bool(requires_evidence_check),
        "requires_tool_broker": bool(requires_tool_broker),
        "forbidden_side_effects": sorted(forbidden_side_effects),
        "input_security_flags": sorted(input_security_flags),
    }


def envelope_hash(envelope: dict) -> str:
    return _sha(envelope)


def build_contract(*, tenant_id, requester_user_id, assigned_ai_employee_id,
                   capability_snapshot_hash, task_type, segment, subject_type,
                   subject_id, task_purpose, purpose_category,
                   allowed_data_scopes, forbidden_data_scopes,
                   allowed_output_types, forbidden_side_effects,
                   authority_decision, authority_hard_fail,
                   requires_human_approval, requires_consent_check,
                   requires_evidence_check, requires_tool_broker,
                   requires_run_ledger, risk_level, risk_reason, expires_at,
                   stale_after, clarification_required,
                   clarification_questions) -> dict:
    """Canonical task contract — WHAT FINALIS ACCEPTS AND IS ALLOWED TO DO.
    Deterministic; excludes the contract hash itself and volatile ids/times
    beyond expires_at/stale_after (which are part of the accepted boundary)."""
    return {
        "contract_version": CONTRACT_VERSION, "tenant_id": tenant_id,
        "requester_user_id": requester_user_id,
        "assigned_ai_employee_id": assigned_ai_employee_id,
        "capability_snapshot_hash": capability_snapshot_hash,
        "task_type": task_type, "segment": segment,
        "subject_type": subject_type, "subject_id": subject_id,
        "task_purpose": task_purpose, "purpose_category": purpose_category,
        "allowed_data_scopes": sorted(allowed_data_scopes),
        "forbidden_data_scopes": sorted(forbidden_data_scopes),
        "allowed_output_types": sorted(allowed_output_types),
        "forbidden_side_effects": sorted(forbidden_side_effects),
        "authority_decision": authority_decision,
        "authority_hard_fail": bool(authority_hard_fail),
        "requires_human_approval": bool(requires_human_approval),
        "requires_consent_check": bool(requires_consent_check),
        "requires_evidence_check": bool(requires_evidence_check),
        "requires_tool_broker": bool(requires_tool_broker),
        "requires_run_ledger": bool(requires_run_ledger),
        "risk_level": risk_level, "risk_reason": risk_reason,
        "expires_at": expires_at, "stale_after": stale_after,
        "clarification_required": bool(clarification_required),
        "clarification_questions": list(clarification_questions),
        "honesty_labels": HONESTY_LABELS,
    }


def contract_hash(contract: dict) -> str:
    return _sha(contract)


def deduplication_key(*, tenant_id, requester_user_id, source_channel,
                      task_type, subject_type, subject_id, task_title) -> str:
    return _sha({"tenant_id": tenant_id, "requester_user_id": requester_user_id,
                 "source_channel": source_channel, "task_type": task_type,
                 "subject_type": subject_type, "subject_id": subject_id,
                 "task_title": task_title})

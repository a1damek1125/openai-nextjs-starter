"""Finalis AI Employee Authority Boundary (CORE-A1).

A deterministic, side-effect-free authority pre-check. Given a proposed
action type, segment and context, it returns exactly one decision on the
lattice:

  BLOCKED > HUMAN_REVIEW > APPROVAL_REQUIRED > ALLOWED_DRAFT_ONLY
          > READ_ONLY_ALLOWED   (plus NOT_IMPLEMENTED for unknown actions)

Hard-fail dominance: a BLOCKED / cross-tenant / forbidden decision can never
be upgraded, and no positive segment capability or score overrides it.
Nothing here executes anything and no external/LLM provider is called.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

DECISIONS = ["BLOCKED", "HUMAN_REVIEW", "APPROVAL_REQUIRED",
             "ALLOWED_DRAFT_ONLY", "READ_ONLY_ALLOWED", "NOT_IMPLEMENTED"]
LATTICE_ORDER = {d: i for i, d in enumerate(DECISIONS)}   # lower = stronger

RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

# --- Action-type matrix (deterministic) -----------------------------------
# Actions the AI employee may NEVER perform. Any of these -> BLOCKED hard_fail,
# regardless of tenant, role, segment or prompt text.
ALWAYS_FORBIDDEN = {
    "verify_memory", "mark_memory_verified", "execute_merge",
    "delete_customer", "delete_evidence", "rewrite_evidence",
    "overwrite_merkle_root", "override_consent", "imply_marketing_consent",
    "approve_quote", "self_approve_quote", "execute_payment",
    "change_case_outcome", "override_proof_algebra", "hide_proof_failure",
    "bypass_rbac", "access_cross_tenant", "call_external_provider",
    "sync_external_crm_write", "perform_oauth_flow",
    "launch_marketing_campaign", "claim_legal_validity",
    "claim_production_readiness", "override_policy", "disable_policy",
    "change_ai_permissions", "grant_admin", "escalate_role",
    "expand_data_scope",
}

# Actions allowed only behind explicit human approval (AI proposes only).
APPROVAL_REQUIRED_ACTIONS = {
    "send_customer_message", "change_consent_status", "propose_merge",
    "propose_memory_verification", "propose_consent_update",
    "propose_quote_approval", "propose_payment_action", "propose_case_outcome",
    "propose_external_sync", "share_evidence_report",
    "quote_readiness_check", "compliance_gap_check",
    "it_access_review_summary",
}

# Actions where the AI employee may prepare a DRAFT only — nothing is sent.
DRAFT_ONLY_ACTIONS = {
    "draft_case_summary", "draft_customer_reply", "draft_quote_summary",
    "draft_payment_reminder", "draft_project_status", "draft_marketing_content",
    "draft_research_brief", "draft_sop_suggestion", "suggest_memory",
    "generate_evidence_report", "evidence_proof_explanation",
    "case_summary", "customer_profile_summary", "research_brief",
    "marketing_content_draft", "hr_onboarding_checklist",
    "field_service_visit_summary",
}

# Read-only summaries/lookups (subject to the caller's own read permission).
READ_ONLY_ACTIONS = {
    "read_case_summary", "read_case_blockers", "read_customer_profile",
    "read_consent_status", "read_evidence_report", "read_proof_verdict",
    "read_quote", "read_payment_status", "read_project_status",
    "read_research_context", "read_contract_history", "read_promise_status",
    "consent_status_check", "project_status_summary",
    "operations_blocker_check", "quote_summary", "marketing_campaign_summary",
}

# Per-action downstream requirement hints (advisory; policy is authoritative).
_CONSENT_ACTIONS = {"send_customer_message", "change_consent_status",
                    "draft_customer_reply", "propose_consent_update",
                    "read_consent_status", "consent_status_check"}
_EVIDENCE_ACTIONS = {"generate_evidence_report", "share_evidence_report",
                     "read_evidence_report", "evidence_proof_explanation",
                     "read_proof_verdict"}
_TOOL_BROKER_ACTIONS = {"send_customer_message", "propose_external_sync",
                        "propose_payment_action", "share_evidence_report"}

_RISK = {"BLOCKED": "CRITICAL", "HUMAN_REVIEW": "HIGH",
         "APPROVAL_REQUIRED": "HIGH", "ALLOWED_DRAFT_ONLY": "MEDIUM",
         "READ_ONLY_ALLOWED": "LOW", "NOT_IMPLEMENTED": "MEDIUM"}


@dataclass
class AuthorityDecision:
    decision: str
    reason: str
    action_type: str = ""
    segment: str = ""
    object_type: str = ""
    object_id: str = ""
    hard_fail: bool = False
    required_approval: bool = False
    required_role: Optional[str] = None
    required_policy: list = field(default_factory=list)
    required_consent_check: bool = False
    required_evidence_check: bool = False
    required_tool_broker: bool = False
    risk_level: str = "LOW"
    honesty_labels: list = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "action_type": self.action_type, "segment": self.segment,
            "object_type": self.object_type, "object_id": self.object_id,
            "decision": self.decision, "hard_fail": self.hard_fail,
            "reason": self.reason, "required_approval": self.required_approval,
            "required_role": self.required_role,
            "required_policy": self.required_policy,
            "required_consent_check": self.required_consent_check,
            "required_evidence_check": self.required_evidence_check,
            "required_tool_broker": self.required_tool_broker,
            "risk_level": self.risk_level,
            "honesty_labels": self.honesty_labels,
        }


_DECISION_LABELS = [
    "AI Employee can propose work but cannot bypass policy.",
    "Server-side policy remains authoritative.",
    "AI-proposed action is not human-approved.",
    "Production autonomy is disabled.",
]


def _mk(decision, reason, action_type, segment, *, hard_fail=False,
        object_type="", object_id="") -> AuthorityDecision:
    return AuthorityDecision(
        decision=decision, reason=reason, action_type=action_type,
        segment=segment, object_type=object_type, object_id=object_id,
        hard_fail=hard_fail,
        required_approval=decision in ("APPROVAL_REQUIRED", "HUMAN_REVIEW"),
        required_consent_check=action_type in _CONSENT_ACTIONS,
        required_evidence_check=action_type in _EVIDENCE_ACTIONS,
        required_tool_broker=action_type in _TOOL_BROKER_ACTIONS,
        risk_level=_RISK[decision], honesty_labels=list(_DECISION_LABELS))


def evaluate_ai_employee_authority(*, employee, action_type: str,
                                   tenant_id: str, object_type: str = "",
                                   object_id: str = "", segment: str = "",
                                   subject_tenant_id: Optional[str] = None
                                   ) -> AuthorityDecision:
    """Pure, deterministic, side-effect-free authority pre-check.

    Precedence: identity active -> tenant boundary -> forbidden action ->
    segment capability -> action class. A prompt cannot change any of this.
    """
    a = action_type

    # 0. Identity must be active. Disabled/suspended cannot act; a flagged
    #    identity routes to human review.
    if employee.status in ("DISABLED", "SUSPENDED"):
        return _mk("BLOCKED",
                   f"AI employee status is {employee.status} — cannot act", a,
                   segment, hard_fail=True, object_type=object_type,
                   object_id=object_id)
    if employee.status == "REVIEW_REQUIRED":
        return _mk("HUMAN_REVIEW",
                   "AI employee identity requires human review before acting",
                   a, segment, object_type=object_type, object_id=object_id)

    # 1. Tenant boundary — nothing crosses it.
    if employee.tenant_id != tenant_id or (
            subject_tenant_id is not None and subject_tenant_id != tenant_id):
        return _mk("BLOCKED",
                   "cross-tenant access is not allowed for an AI employee", a,
                   segment, hard_fail=True, object_type=object_type,
                   object_id=object_id)

    # 2. Forbidden actions — hard boundary, no override, no risk trade-off.
    if a in ALWAYS_FORBIDDEN:
        return _mk("BLOCKED",
                   f"'{a}' is a forbidden AI-employee action (human-only or "
                   "never-permitted)", a, segment, hard_fail=True,
                   object_type=object_type, object_id=object_id)

    # 3. Segment capability (only enforced when a segment is named).
    if segment and segment not in employee.segment_capabilities:
        return _mk("BLOCKED",
                   f"AI employee is not enabled for segment '{segment}'", a,
                   segment, hard_fail=True, object_type=object_type,
                   object_id=object_id)

    # 4. Action class.
    if a in APPROVAL_REQUIRED_ACTIONS:
        return _mk("APPROVAL_REQUIRED",
                   f"'{a}' may be proposed but requires explicit human "
                   "approval", a, segment, object_type=object_type,
                   object_id=object_id)
    if a in DRAFT_ONLY_ACTIONS:
        return _mk("ALLOWED_DRAFT_ONLY",
                   f"'{a}' may prepare a draft only — nothing is sent or "
                   "committed", a, segment, object_type=object_type,
                   object_id=object_id)
    if a in READ_ONLY_ACTIONS:
        return _mk("READ_ONLY_ALLOWED",
                   f"'{a}' is a read-only summary (subject to the caller's "
                   "own read permission)", a, segment, object_type=object_type,
                   object_id=object_id)

    # 5. Unknown action type — never allowed by default (fail-closed).
    return _mk("NOT_IMPLEMENTED",
               f"action type '{a}' is not implemented and is not permitted "
               "by default", a, segment, object_type=object_type,
               object_id=object_id)

"""Finalis AI Employee Identity (CORE-A1).

A tenant-scoped, non-autonomous AI worker identity: which segments it may
operate in, what it is forbidden from doing, what needs human approval, and a
deterministic capability profile. Later AI-Employee modules (task intake, run
ledger, tool broker) must route every proposed action through this identity's
authority boundary.

No LLM runtime, no external providers, no production autonomy. The AI employee
can PROPOSE work and DRAFT outputs; it can never become an unrestricted
superuser. Server-side policy remains authoritative.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

IDENTITY_PROFILE_VERSION = "finalis-ai-employee-profile-v1"
IDENTITY_TYPE = "AI_EMPLOYEE"

# Segments the AI Employee OS is being prepared for (workers NOT implemented).
SEGMENTS = [
    "casework", "customer_support", "sales", "evidence", "compliance",
    "finance", "operations", "project_management", "marketing", "hr_admin",
    "it_security", "field_service", "research_reporting",
]

STATUSES = {"ACTIVE", "DISABLED", "SUSPENDED", "REVIEW_REQUIRED"}

HONESTY_LABELS = [
    "Finalis AI Employee is not a human user.",
    "AI Employee can propose work but cannot bypass policy.",
    "AI Employee cannot override consent.",
    "AI Employee cannot verify memory as human truth.",
    "AI Employee cannot merge customers without human approval.",
    "AI Employee cannot rewrite evidence.",
    "AI Employee cannot approve its own work.",
    "AI Employee cannot execute payments in this build.",
    "AI Employee cannot call external providers directly.",
    "Human approval is required for sensitive actions.",
    "Production autonomy is disabled.",
    "Server-side policy remains authoritative.",
    "This is not a production autonomous worker.",
]

# Immutable capability booleans — every dangerous capability is false, and no
# request (prompt or API) can flip them for an AI employee.
CAPABILITY_FLAGS = {
    "can_create_drafts": True, "can_create_tasks": True,
    "can_create_reports": True, "can_suggest_memory": True,
    "can_verify_memory": False, "can_merge_customers": False,
    "can_override_consent": False, "can_approve_quote": False,
    "can_self_approve_quote": False, "can_execute_payment": False,
    "can_change_case_outcome": False, "can_rewrite_evidence": False,
    "can_delete_evidence": False, "can_call_external_provider": False,
    "production_autonomy_enabled": False,
}


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _segment_capability(segment: str) -> dict:
    """Structured, deterministic per-segment capability descriptor. Draft/
    approval/forbidden lists reference the shared action-type matrix; segment
    workers are NOT implemented here."""
    return {
        "segment": segment, "enabled": True,
        "allowed_drafts": ["draft_case_summary", "draft_customer_reply",
                           "draft_quote_summary", "draft_project_status",
                           "draft_marketing_content", "draft_research_brief"],
        "approval_required": ["send_customer_message", "change_consent_status",
                             "propose_merge", "share_evidence_report"],
        "forbidden": ["override_consent", "rewrite_evidence",
                     "delete_evidence", "self_approve_quote",
                     "execute_payment", "call_external_provider"],
        "requires_future_tools": ["crm", "quote", "evidence", "consent"],
        "requires_future_policy": ["consent_policy", "evidence_policy",
                                  "quote_policy"],
    }


@dataclass
class AIEmployee:
    tenant_id: str
    display_name: str = "Finalis AI Employee"
    internal_name: str = "finalis-ai-employee"
    id: str = ""
    identity_type: str = IDENTITY_TYPE
    role: str = "ai_worker"
    segment_capabilities: list = field(default_factory=lambda: list(SEGMENTS))
    status: str = "ACTIVE"
    identity_version: int = 1
    profile_version: str = IDENTITY_PROFILE_VERSION
    human_supervisor_required: bool = True
    default_supervisor_role: str = "owner"
    created_by: str = "system"
    created_at: str = ""


def capability_profile(emp: AIEmployee) -> dict:
    """The full, deterministic capability description of an AI employee."""
    from .authority import (ALWAYS_FORBIDDEN, APPROVAL_REQUIRED_ACTIONS,
                           DRAFT_ONLY_ACTIONS, READ_ONLY_ACTIONS)
    return {
        "ai_employee_id": emp.id, "tenant_id": emp.tenant_id,
        "display_name": emp.display_name, "internal_name": emp.internal_name,
        "identity_type": emp.identity_type, "status": emp.status,
        "role": emp.role,
        "segment_capabilities": sorted(emp.segment_capabilities),
        "segment_capability_detail": [
            _segment_capability(s) for s in sorted(emp.segment_capabilities)],
        "allowed_action_types": sorted(READ_ONLY_ACTIONS | DRAFT_ONLY_ACTIONS),
        "read_only_action_types": sorted(READ_ONLY_ACTIONS),
        "draft_only_action_types": sorted(DRAFT_ONLY_ACTIONS),
        "approval_required_action_types": sorted(APPROVAL_REQUIRED_ACTIONS),
        "forbidden_action_types": sorted(ALWAYS_FORBIDDEN),
        "human_supervisor_required": emp.human_supervisor_required,
        "default_supervisor_role": emp.default_supervisor_role,
        "identity_version": emp.identity_version,
        "profile_version": emp.profile_version,
        **CAPABILITY_FLAGS,
    }


def capability_snapshot(emp: AIEmployee) -> dict:
    """Capability profile plus its deterministic hash — downstream missions
    store this so a task records what the employee could do at intake time."""
    profile = capability_profile(emp)
    snap = hashlib.sha256(_canonical(profile).encode("utf-8")).hexdigest()
    return {"capability_snapshot": profile,
            "capability_snapshot_hash": snap,
            "capability_snapshot_algorithm": "sha256",
            "honesty_labels": HONESTY_LABELS}


def capability_snapshot_hash(emp: AIEmployee) -> str:
    return capability_snapshot(emp)["capability_snapshot_hash"]


def employee_json(emp: AIEmployee) -> dict:
    """Tenant-safe profile response (no secrets, no internal paths)."""
    return {**capability_profile(emp), "honesty_labels": HONESTY_LABELS}

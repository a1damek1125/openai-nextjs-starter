"""EvidenceBundle + UpsellOpportunity — state changes always leave proof."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

EVIDENCE_REQUIRED_DECISIONS = {
    "close_won", "close_lost", "complete_case", "issue_invoice",
    "mark_payment_received", "schedule_fulfillment", "send_high_risk_message",
    "start_recovery_later", "create_upsell_opportunity", "reopen_final_case"}


class EvidenceError(Exception):
    pass


@dataclass
class EvidenceBundle:
    case_id: str
    tenant_id: str
    actor_type: str
    actor_id: str
    decision_type: str
    pre_state: dict[str, Any]
    post_state: dict[str, Any]
    input_facts: dict[str, Any]
    evidence_references: list[str]
    rule_or_playbook_version: str
    confidence: float
    action_gate_result: str
    human_approval_id: Optional[str] = None
    audit_event_id: Optional[str] = None
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


def record_decision(bundle: EvidenceBundle, audit) -> EvidenceBundle:
    """Validate + write the audit event. Raises on missing proof."""
    if bundle.decision_type in EVIDENCE_REQUIRED_DECISIONS:
        if not bundle.evidence_references and not bundle.human_approval_id:
            raise EvidenceError(
                f"{bundle.decision_type} requires evidence_references "
                "or a human approval")
    ev = audit.append(
        event_type="LIFECYCLE_VECTOR_UPDATED", actor=bundle.actor_id,
        case_id=bundle.case_id,
        payload={"decision_type": bundle.decision_type,
                 "pre_state": bundle.pre_state,
                 "post_state": bundle.post_state,
                 "evidence": bundle.evidence_references,
                 "confidence": bundle.confidence,
                 "gate": bundle.action_gate_result,
                 "playbook_version": bundle.rule_or_playbook_version})
    bundle.audit_event_id = ev.id
    return bundle


UPSELL_STATUSES = {"DETECTED", "READY", "WAITING_COOLDOWN",
                   "BLOCKED_BY_ISSUE", "HUMAN_REVIEW_REQUIRED", "CONTACTED",
                   "ACCEPTED", "REJECTED", "EXPIRED"}


@dataclass
class UpsellOpportunity:
    tenant_id: str
    customer_id: str
    source_case_id: str
    opportunity_type: str          # upsell | cross_sell | renewal
    reason: str
    recommended_offer: str
    confidence: float
    earliest_contact_at: str
    status: str = "DETECTED"
    requires_human_approval: bool = True
    evidence_reference_id: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def set_status(self, status: str) -> None:
        if status not in UPSELL_STATUSES:
            raise ValueError(f"unknown upsell status {status}")
        self.status = status

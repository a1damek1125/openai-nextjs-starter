"""Vertical Playbook contract + machine validation + the 5 base playbooks.

A playbook that fails validation CANNOT be activated (refused loudly).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .outcomes import REASON_TAXONOMY


class PlaybookValidationError(Exception):
    pass


@dataclass
class VerticalPlaybook:
    vertical_id: str
    name: str
    case_types: list[str]
    required_information: list[dict]      # [{key, weight, hard_required}]
    required_documents: list[str]
    optional_documents: list[str] = field(default_factory=list)
    invoice_required: bool = True
    payment_required: bool = True
    fulfillment_required: bool = True
    appointment_required: bool = False
    contract_required: bool = False
    completion_confirmation_required: bool = False
    human_approval_rules: list[str] = field(default_factory=lambda: [
        "issue_invoice", "mark_payment_received_manually", "apply_discount",
        "refund", "contract_language", "close_lost_high_value",
        "reopen_final_case"])
    allowed_ai_actions: list[str] = field(default_factory=lambda: [
        "ask_for_missing_info", "send_photo_request", "send_follow_up",
        "send_upload_link", "send_review_request", "schedule_reminder"])
    prohibited_ai_actions: list[str] = field(default_factory=lambda: [
        "legal_advice", "final_price_commitment_without_rules",
        "refund_without_human", "medical_advice"])
    loss_reason_taxonomy: list[str] = field(
        default_factory=lambda: sorted(REASON_TAXONOMY["LOST"]))
    recovery_rules: dict = field(default_factory=lambda: {
        "eligible_reasons": ["timing_later", "client_needs_budget",
                             "project_postponed", "seasonal_opportunity",
                             "contact_later_requested",
                             "client_comparing_offers"],
        "wake_days": [30, 60, 90], "requires_consent": True})
    upsell_rules: dict = field(default_factory=lambda: {
        "cooldown_days": 14, "blocked_by_complaint": True,
        "blocked_by_overdue_payment": True,
        "high_value_requires_human": True})
    post_sale_rules: dict = field(default_factory=lambda: {
        "thank_you": True, "review_request_after_completion": True,
        "checkin_days": 7})
    follow_up_cadence_hours: list[int] = field(
        default_factory=lambda: [24, 48, 72])
    max_follow_up_attempts: int = 3
    retention_policy_days: int = 730
    evidence_requirements: list[str] = field(default_factory=lambda: [
        "close_won", "close_lost", "complete_case", "issue_invoice",
        "mark_payment_received"])
    version: str = "1.0"


def validate_playbook(pb: VerticalPlaybook) -> list[str]:
    """Machine validation. Returns [] if valid; raises on activation attempt
    of an invalid playbook (see activate_playbook)."""
    errors: list[str] = []
    if not pb.vertical_id or not pb.name:
        errors.append("vertical_id and name are required")
    if not pb.case_types:
        errors.append("at least one case_type is required")
    if not pb.required_information:
        errors.append("required_information must not be empty")
    for item in pb.required_information:
        if "key" not in item or "weight" not in item:
            errors.append(f"required_information item malformed: {item}")
        elif not (0 < item["weight"] <= 1):
            errors.append(f"weight out of (0,1]: {item}")
    if not pb.loss_reason_taxonomy:
        errors.append("loss_reason_taxonomy is required (no silent losses)")
    unknown = set(pb.loss_reason_taxonomy) - REASON_TAXONOMY["LOST"]
    if unknown:
        errors.append(f"loss reasons outside global taxonomy: {unknown}")
    if pb.payment_required and not pb.invoice_required:
        errors.append("contradiction: payment_required without "
                      "invoice_required")
    if not pb.follow_up_cadence_hours:
        errors.append("follow_up_cadence_hours required")
    if pb.max_follow_up_attempts <= 0:
        errors.append("max_follow_up_attempts must be positive")
    if pb.max_follow_up_attempts > 10:
        errors.append("cadence could spam: max_follow_up_attempts > 10")
    if not pb.human_approval_rules:
        errors.append("human_approval_rules required")
    if not pb.prohibited_ai_actions:
        errors.append("prohibited_ai_actions required")
    if not pb.evidence_requirements:
        errors.append("evidence_requirements required")
    overlap = set(pb.allowed_ai_actions) & set(pb.prohibited_ai_actions)
    if overlap:
        errors.append(f"contradictory rule: actions both allowed and "
                      f"prohibited: {overlap}")
    if pb.recovery_rules.get("requires_consent") is None:
        errors.append("recovery_rules.requires_consent must be explicit")
    return errors


_ACTIVE: dict[str, VerticalPlaybook] = {}


def activate_playbook(pb: VerticalPlaybook) -> VerticalPlaybook:
    errors = validate_playbook(pb)
    if errors:
        raise PlaybookValidationError("; ".join(errors))
    _ACTIVE[pb.vertical_id] = pb
    return pb


# --- The five base playbooks ---------------------------------------------------
HVAC_HOME_SERVICES = VerticalPlaybook(
    vertical_id="hvac_home_services", name="HVAC / Home Services",
    case_types=["heat_pump_quote", "ac_install", "boiler_service",
                "emergency_repair"],
    required_information=[
        {"key": "client_contact", "weight": 0.9, "hard_required": True},
        {"key": "address", "weight": 0.9, "hard_required": True},
        {"key": "service_type", "weight": 0.9, "hard_required": True},
        {"key": "installation_photo", "weight": 0.7, "hard_required": False},
        {"key": "preferred_date", "weight": 0.5, "hard_required": False},
    ],
    required_documents=["installation_photo"],
    appointment_required=True, completion_confirmation_required=True,
    post_sale_rules={"thank_you": True,
                     "review_request_after_completion": True,
                     "checkin_days": 7, "maintenance_reminder_months": 12,
                     "seasonal_followup": "before_winter",
                     "service_plan_offer": True})

GENERIC_SERVICE = VerticalPlaybook(
    vertical_id="generic_service_business", name="Generic Service Business",
    case_types=["service_request"],
    required_information=[
        {"key": "client_contact", "weight": 0.9, "hard_required": True},
        {"key": "service_scope", "weight": 0.8, "hard_required": True}],
    required_documents=[])

PRODUCT_SALE = VerticalPlaybook(
    vertical_id="product_sale", name="Product Sale",
    case_types=["product_order"],
    required_information=[
        {"key": "client_contact", "weight": 0.9, "hard_required": True},
        {"key": "product_selection", "weight": 0.9, "hard_required": True},
        {"key": "delivery_address", "weight": 0.9, "hard_required": True}],
    required_documents=[], appointment_required=False,
    fulfillment_required=True)   # delivery required

B2B_SALES = VerticalPlaybook(
    vertical_id="b2b_sales", name="B2B Sales",
    case_types=["b2b_opportunity"],
    required_information=[
        {"key": "company_contact", "weight": 0.9, "hard_required": True},
        {"key": "decision_maker", "weight": 0.7, "hard_required": False},
        {"key": "requirements_scope", "weight": 0.8, "hard_required": True}],
    required_documents=["signed_contract"],
    contract_required=True, appointment_required=False)

PROPERTY_MANAGEMENT = VerticalPlaybook(
    vertical_id="property_management", name="Property Management",
    case_types=["tenant_issue", "preventive_maintenance"],
    required_information=[
        {"key": "tenant_contact", "weight": 0.9, "hard_required": True},
        {"key": "unit_address", "weight": 0.9, "hard_required": True},
        {"key": "issue_description", "weight": 0.8, "hard_required": True}],
    required_documents=[], invoice_required=False, payment_required=False,
    completion_confirmation_required=True)   # tenant must confirm

BASE_PLAYBOOKS = [HVAC_HOME_SERVICES, GENERIC_SERVICE, PRODUCT_SALE,
                  B2B_SALES, PROPERTY_MANAGEMENT]

"""Relationship Core domain models — local-first, deterministic."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


def _uuid() -> str:
    return str(uuid.uuid4())


PARTY_KINDS = {"person", "organization", "household"}
PARTY_ROLES = {"customer", "vendor", "partner", "supplier", "tenant",
               "owner", "installer", "prospect"}

CONTACT_POINT_TYPES = {"EMAIL", "PHONE", "MOBILE", "WHATSAPP", "ADDRESS",
                       "WEBSITE", "EXTERNAL_PROFILE"}

CONSENT_CHANNELS = {"EMAIL", "SMS", "WHATSAPP", "PHONE_CALL", "MARKETING",
                    "SERVICE_UPDATES", "DOCUMENT_REQUESTS"}
CONSENT_STATUSES = {"GRANTED", "DENIED", "REVOKED", "UNKNOWN"}

MEMORY_TYPES = {"VERIFIED_FACT", "CUSTOMER_PREFERENCE", "CUSTOMER_PROMISE",
                "FINALIS_PROMISE", "RISK_NOTE", "BILLING_NOTE",
                "SERVICE_HISTORY", "COMMUNICATION_SUMMARY",
                "DISPUTED_FACT", "STALE_FACT", "AI_SUGGESTED"}


# --- parties ---------------------------------------------------------------------
@dataclass
class PersonProfile:
    first_name: str = ""
    last_name: str = ""
    language: str = "pl"


@dataclass
class OrganizationProfile:
    legal_name: str = ""
    vat_id: str = ""
    domain: str = ""                    # company e-mail domain


@dataclass
class HouseholdProfile:
    label: str = ""                     # "Kowalski household"


@dataclass
class Address:
    street: str = ""
    city: str = ""
    postal_code: str = ""
    country: str = "PL"


@dataclass
class ContactPoint:
    kind: str                           # CONTACT_POINT_TYPES
    value: str
    label: str = ""
    verified: bool = False
    preferred: bool = False
    id: str = field(default_factory=_uuid)

    def __post_init__(self) -> None:
        if self.kind not in CONTACT_POINT_TYPES:
            raise ValueError(f"unknown contact point kind {self.kind}")
        if self.kind == "EMAIL":
            self.value = self.value.strip().lower()
        if self.kind in ("PHONE", "MOBILE", "WHATSAPP"):
            self.value = "".join(c for c in self.value
                                 if c.isdigit() or c == "+")


@dataclass
class ConsentRecord:
    tenant_id: str
    party_id: str
    channel: str                        # CONSENT_CHANNELS
    status: str = "UNKNOWN"             # CONSENT_STATUSES
    source: str = ""                    # where the consent came from
    recorded_by: str = "system"
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default_factory=_uuid)

    def __post_init__(self) -> None:
        if self.channel not in CONSENT_CHANNELS:
            raise ValueError(f"unknown consent channel {self.channel}")
        if self.status not in CONSENT_STATUSES:
            raise ValueError(f"unknown consent status {self.status}")


@dataclass
class Party:
    tenant_id: str
    kind: str                           # PARTY_KINDS
    display_name: str
    person: Optional[PersonProfile] = None
    organization: Optional[OrganizationProfile] = None
    household: Optional[HouseholdProfile] = None
    roles: set[str] = field(default_factory=lambda: {"customer"})
    contact_points: list[ContactPoint] = field(default_factory=list)
    addresses: list[Address] = field(default_factory=list)
    merged_into_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default_factory=_uuid)

    def __post_init__(self) -> None:
        if self.kind not in PARTY_KINDS:
            raise ValueError(f"unknown party kind {self.kind}")
        bad = self.roles - PARTY_ROLES
        if bad:
            raise ValueError(f"unknown roles {bad}")

    def contact(self, kind: str) -> Optional[str]:
        for cp in self.contact_points:
            if cp.kind == kind:
                return cp.value
        return None


@dataclass
class RelationshipRole:
    """Edge in the graph: party↔party or party↔case, with a role."""
    tenant_id: str
    from_id: str                        # party id
    to_id: str                          # party id / case id / quote id …
    to_kind: str = "party"              # party|case|quote|appointment|evidence
    role: str = "customer"              # member_of|payer|decision_maker…
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default_factory=_uuid)


# Typed link aliases (same edge shape, explicit intent).
@dataclass
class CustomerCaseLink(RelationshipRole):
    to_kind: str = "case"


@dataclass
class CustomerQuoteLink(RelationshipRole):
    to_kind: str = "quote"


@dataclass
class CustomerAppointmentLink(RelationshipRole):
    to_kind: str = "appointment"


@dataclass
class CustomerEvidenceLink(RelationshipRole):
    to_kind: str = "evidence"


@dataclass
class CustomerActivity:
    tenant_id: str
    party_id: str
    kind: str                           # call|message|visit|quote_sent|…
    summary: str
    case_id: Optional[str] = None
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default_factory=_uuid)


@dataclass
class CustomerPromise:
    tenant_id: str
    party_id: str
    promisor: str                       # "customer" | "finalis"
    what: str
    due_at: Optional[datetime] = None
    status: str = "open"                # open|kept|broken|withdrawn
    case_id: Optional[str] = None
    id: str = field(default_factory=_uuid)


@dataclass
class CustomerPreference:
    tenant_id: str
    party_id: str
    key: str                            # preferred_channel|call_window|…
    value: str
    source: str = "stated"              # stated|observed|ai_suggested
    id: str = field(default_factory=_uuid)


@dataclass
class CustomerFact:
    tenant_id: str
    party_id: str
    key: str
    value: str
    verified: bool = False
    verified_by: Optional[str] = None
    source: str = "unknown"
    id: str = field(default_factory=_uuid)


@dataclass
class CustomerMemoryItem:
    """Structured memory — never raw LLM text. AI suggestions stay
    AI_SUGGESTED until a human verifies them for a purpose."""
    tenant_id: str
    party_id: str
    memory_type: str                    # MEMORY_TYPES
    content: dict[str, Any]             # structured, not prose blobs
    source: str                         # human|ai_worker|document|system
    confidence: float = 0.5
    scope: str = "tenant"               # tenant|case:<id>
    sensitive: bool = False
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    verified_by: Optional[str] = None
    id: str = field(default_factory=_uuid)

    def __post_init__(self) -> None:
        if self.memory_type not in MEMORY_TYPES:
            raise ValueError(f"unknown memory type {self.memory_type}")


# --- external CRM mapping (adapters are OPTIONAL — never core) -----------------
CANONICAL_CRM_OBJECTS = {"Contact", "Company", "Deal", "Activity", "Note",
                         "Task", "PipelineStage", "CustomField"}


@dataclass
class ExternalCrmReference:
    tenant_id: str
    party_id: str
    provider: str                       # hubspot|salesforce|pipedrive|…
    object_kind: str                    # CANONICAL_CRM_OBJECTS
    external_id: str
    id: str = field(default_factory=_uuid)

    def __post_init__(self) -> None:
        if self.object_kind not in CANONICAL_CRM_OBJECTS:
            raise ValueError(f"unknown crm object {self.object_kind}")


@dataclass
class ExternalFieldMapping:
    provider: str
    canonical_field: str                # e.g. "email"
    external_field: str                 # e.g. "properties.email"
    source_of_truth: str = "finalis"    # finalis|external|newest
    sync_direction: str = "both"        # in|out|both|none


@dataclass
class ExternalSyncPolicy:
    tenant_id: str
    provider: str
    enabled: bool = False               # off by default — opt-in
    dry_run: bool = True                # dry-run first, always
    allow_import: bool = True
    allow_export: bool = False          # exporting is the risky direction
    sync_marketing_fields: bool = False
    field_mappings: list[ExternalFieldMapping] = field(default_factory=list)


@dataclass
class ExternalSyncCursor:
    tenant_id: str
    provider: str
    last_synced_at: Optional[datetime] = None
    cursor_token: str = ""


@dataclass
class ExternalSyncEvent:
    tenant_id: str
    provider: str
    direction: str                      # import|export|dry_run
    object_kind: str
    decision: str
    detail: dict[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default_factory=_uuid)


@dataclass
class ConflictResolutionDecision:
    field: str
    internal_value: str
    external_value: str
    resolution: str                     # keep_internal|take_external|review
    decided_by: str = "policy"
    id: str = field(default_factory=_uuid)


@dataclass
class MergeCandidate:
    tenant_id: str
    party_a_id: str
    party_b_id: str
    score: float
    verdict: str
    signals: list[str] = field(default_factory=list)
    id: str = field(default_factory=_uuid)


@dataclass
class MergeDecision:
    tenant_id: str
    surviving_party_id: str
    merged_party_ids: list[str]
    decided_by: str                     # a human — never "ai"/"system"
    reason: str = ""
    decided_at: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default_factory=_uuid)

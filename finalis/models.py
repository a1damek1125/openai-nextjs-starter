"""Core domain models — executable subset of docs/finalis-ai/04.

Dataclasses, not ORM: the scaffold proves logic, not persistence. Field names
match doc 04 so the production schema can be generated from the same shapes.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .state_machine import CaseState


def _uuid() -> str:
    return str(uuid.uuid4())


@dataclass
class Party:
    """Any actor in a case — client, company, technician, supplier, notary,
    lawyer, insurer (doc 04)."""
    tenant_id: str
    type: str
    display_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    preferred_channel: str = "phone"
    notes: str = ""
    id: str = field(default_factory=_uuid)


@dataclass
class EvidenceReference:
    source_type: str  # message | call_segment | document_region | web_source
    source_id: str
    locator: dict[str, Any]
    snippet: str
    confidence: float
    id: str = field(default_factory=_uuid)


@dataclass
class Promise:
    promisor: str          # party id/role making the promise
    what: str
    due_at: datetime
    importance: float      # [0,1]
    dependency_impact: float  # [0,1]
    status: str = "open"   # open | fulfilled | broken | waived
    evidence: Optional[EvidenceReference] = None
    id: str = field(default_factory=_uuid)


@dataclass
class MissingItem:
    field_key: str
    label: str
    weight: float          # w_i, business weight
    blocks_quote: bool = False
    status: str = "missing"  # missing | requested | received | waived
    id: str = field(default_factory=_uuid)


@dataclass
class ExtractedField:
    field_key: str
    field_value: Any
    page: Optional[int]
    ocr_q: float
    extraction_q: float
    source_q: float
    consistency_q: float
    verified_by_human: bool = False
    id: str = field(default_factory=_uuid)

    @property
    def confidence(self) -> float:
        """Evidence Confidence — docs/finalis-ai/05 §6 (multiplicative)."""
        return self.ocr_q * self.extraction_q * self.source_q * self.consistency_q


@dataclass
class Document:
    doc_type: str
    ocr_quality: float                       # [0,1]
    fields: list[ExtractedField] = field(default_factory=list)
    status: str = "received"  # received | processing | analyzed | needs_rescan
    id: str = field(default_factory=_uuid)


@dataclass
class Offer:
    origin: str            # ours | competitor | client_provided
    price: float
    axes: dict[str, float] = field(default_factory=dict)  # normalized [0,1] axis scores
    id: str = field(default_factory=_uuid)


@dataclass
class Source:
    """WebScout source record — docs/finalis-ai/04 `Source` (08 §5 contract)."""
    url: str
    source_type: str
    date_checked: str
    snippet: str
    trust_score: float     # [0,100], 05 §11
    relevance: float       # [0,1]
    confidence: float      # [0,1]
    id: str = field(default_factory=_uuid)


@dataclass
class HumanApproval:
    action_type: str
    context: dict[str, Any]
    recommended_option: str
    decision: Optional[str] = None   # approved | rejected | edited
    decided_by: Optional[str] = None
    id: str = field(default_factory=_uuid)


@dataclass
class Case:
    tenant_id: str
    state: CaseState = CaseState.NEW_CONTACT
    value_estimate: float = 0.0
    lead_score: float = 0.0
    risk_score: float = 0.0
    mis_score: float = 0.0
    stuck_score: float = 0.0
    escalation_score: float = 0.0
    autonomy_level: int = 3          # tenant/case setting, L1-L5
    autonomy_frozen_at: Optional[int] = None  # set to 2 in HUMAN_REVIEW_REQUIRED
    opted_out: bool = False
    next_best_action: Optional[dict[str, Any]] = None
    next_action_due_at: Optional[datetime] = None
    promises: list[Promise] = field(default_factory=list)
    missing_items: list[MissingItem] = field(default_factory=list)
    documents: list[Document] = field(default_factory=list)
    offers: list[Offer] = field(default_factory=list)
    approvals: list[HumanApproval] = field(default_factory=list)
    evidence: list[EvidenceReference] = field(default_factory=list)
    last_progress_at: Optional[datetime] = None
    id: str = field(default_factory=_uuid)

    @property
    def effective_autonomy(self) -> int:
        """13 §1: HUMAN_REVIEW_REQUIRED caps at L2; else the case setting."""
        if self.autonomy_frozen_at is not None:
            return min(self.autonomy_level, self.autonomy_frozen_at)
        return self.autonomy_level

    def is_active(self) -> bool:
        from .state_machine import ACTIVE_STATES
        return self.state in ACTIVE_STATES

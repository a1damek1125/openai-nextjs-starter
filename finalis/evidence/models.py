"""Evidence Trust Fabric domain models + lifecycle state machine."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


def _uuid() -> str:
    return str(uuid.uuid4())


# --- lifecycle -------------------------------------------------------------------
EVIDENCE_STATES = {
    "UPLOADED", "QUARANTINED", "SCAN_PENDING", "SCANNED_CLEAN",
    "SCAN_FAILED", "MALWARE_SUSPECTED", "PARSER_FAILED",
    "NEEDS_HUMAN_REVIEW", "ADMISSIBLE", "ADMISSIBLE_WITH_LIMITS",
    "REJECTED", "LEGAL_HOLD", "RETENTION_LOCKED", "INTEGRITY_FAILED",
    "DELETED_SOFT",
}

EVIDENCE_TRANSITIONS: dict[str, set[str]] = {
    "UPLOADED": {"QUARANTINED", "REJECTED", "INTEGRITY_FAILED"},
    "QUARANTINED": {"SCAN_PENDING", "REJECTED", "INTEGRITY_FAILED"},
    "SCAN_PENDING": {"SCANNED_CLEAN", "SCAN_FAILED", "MALWARE_SUSPECTED",
                     "INTEGRITY_FAILED"},
    "SCANNED_CLEAN": {"NEEDS_HUMAN_REVIEW", "ADMISSIBLE",
                      "ADMISSIBLE_WITH_LIMITS", "REJECTED", "PARSER_FAILED",
                      "INTEGRITY_FAILED"},
    "SCAN_FAILED": {"NEEDS_HUMAN_REVIEW", "REJECTED"},
    "MALWARE_SUSPECTED": {"REJECTED"},
    "PARSER_FAILED": {"NEEDS_HUMAN_REVIEW", "REJECTED"},
    "NEEDS_HUMAN_REVIEW": {"ADMISSIBLE", "ADMISSIBLE_WITH_LIMITS",
                           "REJECTED", "INTEGRITY_FAILED"},
    # A rejected file becomes usable ONLY through a new explicit review.
    "REJECTED": {"NEEDS_HUMAN_REVIEW"},
    "ADMISSIBLE": {"LEGAL_HOLD", "RETENTION_LOCKED", "INTEGRITY_FAILED",
                   "DELETED_SOFT", "NEEDS_HUMAN_REVIEW"},
    "ADMISSIBLE_WITH_LIMITS": {"LEGAL_HOLD", "RETENTION_LOCKED",
                               "INTEGRITY_FAILED", "DELETED_SOFT",
                               "NEEDS_HUMAN_REVIEW", "ADMISSIBLE"},
    "LEGAL_HOLD": {"ADMISSIBLE", "INTEGRITY_FAILED"},
    "RETENTION_LOCKED": {"ADMISSIBLE", "INTEGRITY_FAILED"},
    "INTEGRITY_FAILED": set(),          # terminal: blocks all usage
    "DELETED_SOFT": set(),              # terminal for decisions
}

# States that can never support a business decision, no matter the score.
UNUSABLE_STATES = {"UPLOADED", "QUARANTINED", "SCAN_PENDING", "SCAN_FAILED",
                   "MALWARE_SUSPECTED", "PARSER_FAILED", "REJECTED",
                   "INTEGRITY_FAILED", "DELETED_SOFT"}
ADMISSIBLE_STATES = {"ADMISSIBLE", "ADMISSIBLE_WITH_LIMITS", "LEGAL_HOLD",
                     "RETENTION_LOCKED"}


class IllegalEvidenceTransition(Exception):
    pass


def evidence_transition(ev: "EvidenceObject", to_state: str,
                        *, actor: str = "system",
                        reason: str = "") -> None:
    if to_state not in EVIDENCE_STATES:
        raise IllegalEvidenceTransition(f"unknown state {to_state}")
    if to_state not in EVIDENCE_TRANSITIONS[ev.state]:
        raise IllegalEvidenceTransition(
            f"{ev.state} -> {to_state} is not allowed")
    old = ev.state
    ev.state = to_state
    ev.chain.append_event(event_type="STATE_CHANGED", actor=actor,
                          payload={"from": old, "to": to_state,
                                   "reason": reason})


# --- file validation constants ------------------------------------------------
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic", "gif", "pdf",
                      "txt", "csv", "eml", "docx", "xlsx", "mp3", "wav",
                      "m4a", "mp4", "mov"}
DANGEROUS_EXTENSIONS = {"exe", "bat", "cmd", "sh", "js", "msi", "scr",
                        "com", "pif", "jar", "vbs", "ps1", "dll", "apk",
                        "html", "htm", "svg", "php", "py"}
ACTIVE_CONTENT_EXTENSIONS = {"pdf", "docx", "xlsx"}   # may embed scripts
MAX_SIZE_MB = 25

_MAGIC = [
    (b"\xff\xd8\xff", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF8", "image/gif"), (b"%PDF", "application/pdf"),
    (b"PK\x03\x04", "application/zip"),   # docx/xlsx are zip containers
    (b"RIFF", "image/webp"), (b"ID3", "audio/mpeg"),
]


def detect_mime(data: bytes) -> Optional[str]:
    for magic, mime in _MAGIC:
        if data[:len(magic)] == magic:
            return mime
    if data[:1024].replace(b"\r", b"").replace(b"\n", b"") \
            .replace(b"\t", b"").isascii() if data else False:
        return "text/plain"
    return None


# --- dataclasses -----------------------------------------------------------------
@dataclass
class EvidenceSource:
    kind: str = "client_upload_link"   # client_upload_link|staff|email|api
    identity_confidence: float = 0.5   # who really sent this?
    channel: str = "upload_link"
    historical_risk: float = 0.0


@dataclass
class EvidenceUploadContext:
    tenant_id: str
    case_id: str
    uploaded_by: str                    # user id, "client:<token-id>", …
    upload_token_valid: bool = True
    token_expired: bool = False


@dataclass
class EvidenceFileMetadata:
    original_filename: str              # METADATA ONLY — never a path
    declared_mime: str = ""
    detected_mime: Optional[str] = None
    extension: str = ""
    size_bytes: int = 0
    mime_mismatch: bool = False
    active_content: bool = False


@dataclass
class EvidenceStoragePointer:
    provider: str
    key: str                            # generated — never the filename
    is_mock: bool = True


@dataclass
class EvidenceIntegrityRecord:
    algorithm: str
    digest: str
    verified_at: Optional[datetime] = None
    valid: bool = True


@dataclass
class EvidenceScanResult:
    """SCAFFOLDED_ONLY placeholder — a real ClamAV/CDR provider replaces
    the mock verdict behind this same shape."""
    provider: str = "scanner-mock"
    is_mock: bool = True
    status: str = "NOT_SCANNED"         # NOT_SCANNED|CLEAN|SUSPICIOUS|ERROR
    detail: str = ""


@dataclass
class EvidenceDerivative:
    kind: str                           # safe_text|thumbnail|redacted_text
    storage: Optional[EvidenceStoragePointer] = None
    text: str = ""
    id: str = field(default_factory=_uuid)


@dataclass
class ChainEvent:
    event_type: str
    actor: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    hash_prev: str = ""
    hash_self: str = ""
    id: str = field(default_factory=_uuid)


class EvidenceChainOfCustody:
    """Per-evidence tamper-evident hash chain (audit-style)."""
    GENESIS = "0" * 64

    def __init__(self) -> None:
        self.events: list[ChainEvent] = []

    def _digest(self, ev: ChainEvent) -> str:
        body = json.dumps({"t": ev.event_type, "a": ev.actor,
                           "p": ev.payload, "at": str(ev.created_at),
                           "prev": ev.hash_prev}, sort_keys=True,
                          default=str)
        return hashlib.sha256(body.encode()).hexdigest()

    def append_event(self, *, event_type: str, actor: str,
                     payload: Optional[dict] = None) -> ChainEvent:
        prev = self.events[-1].hash_self if self.events else self.GENESIS
        ev = ChainEvent(event_type=event_type, actor=actor,
                        payload=payload or {}, hash_prev=prev)
        ev.hash_self = self._digest(ev)
        self.events.append(ev)
        return ev

    def verify(self) -> bool:
        prev = self.GENESIS
        for ev in self.events:
            if ev.hash_prev != prev or self._digest(ev) != ev.hash_self:
                return False
            prev = ev.hash_self
        return True


@dataclass
class EvidenceAccessEvent:
    tenant_id: str
    evidence_id: str
    actor_kind: str                     # human|ai_worker
    actor_id: str
    purpose: str
    decision: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default_factory=_uuid)


@dataclass
class LegalHoldRecord:
    tenant_id: str
    evidence_id: str
    reason: str
    placed_by: str
    released_at: Optional[datetime] = None
    id: str = field(default_factory=_uuid)


@dataclass
class RetentionDecision:
    decision: str
    reasons: list[str] = field(default_factory=list)


@dataclass
class EvidenceAdmissibilityDecision:
    decision: str
    reasons: list[str] = field(default_factory=list)
    hard_blockers: list[str] = field(default_factory=list)


@dataclass
class AIFileAccessDecision:
    decision: str
    reasons: list[str] = field(default_factory=list)


@dataclass
class EvidenceUntrustedDataMarker:
    """Sticky provenance: content from outside stays untrusted no matter
    how many times it is saved and reread inside Finalis."""
    origin: str                          # client_upload_link|email|api|…
    reason: str = "external content is untrusted by default"
    marked_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EvidenceSymbol:
    """Opaque handle to untrusted content (DualView-inspired, own
    implementation): agents pass symbols around; only gated derivations
    of the content — never the raw text — travel with them."""
    evidence_id: str
    kind: str = "document_text"
    trusted: bool = False                # storage never launders trust
    human_verified_for: Optional[str] = None   # narrow factual purpose
    marker: EvidenceUntrustedDataMarker = field(
        default_factory=lambda: EvidenceUntrustedDataMarker(
            origin="unknown"))
    id: str = field(default_factory=_uuid)


@dataclass
class EvidenceFactSet:
    """Facts derived from a symbol, with confidence — the ONLY form in
    which document content may influence a decision."""
    symbol_ids: list[str] = field(default_factory=list)
    amounts: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    confidence: float = 0.0
    untrusted: bool = True
    id: str = field(default_factory=_uuid)


@dataclass
class ExtractedFacts:
    """What a document may contribute: FACTS. There is deliberately no
    field for commands/instructions/actions — structurally impossible."""
    amounts: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    mentions: list[str] = field(default_factory=list)
    injection_risk: float = 0.0
    suppressed_instruction_count: int = 0


@dataclass
class EvidenceObject:
    tenant_id: str
    case_id: str
    evidence_type: str                  # payment_proof|fulfillment_photo|…
    meta: EvidenceFileMetadata
    source: EvidenceSource
    uploaded_by: str
    state: str = "UPLOADED"
    storage: Optional[EvidenceStoragePointer] = None
    integrity: Optional[EvidenceIntegrityRecord] = None
    scan: EvidenceScanResult = field(default_factory=EvidenceScanResult)
    derivatives: list[EvidenceDerivative] = field(default_factory=list)
    chain: EvidenceChainOfCustody = field(
        default_factory=EvidenceChainOfCustody)
    sensitivity: str = "normal"         # normal|sensitive|legal
    injection_risk: float = 0.0
    symbols: list[EvidenceSymbol] = field(default_factory=list)
    parser_kind: str = "OCR_NOT_RUN"    # future document-intelligence hook
    human_verified: bool = False
    legal_hold: bool = False
    retention_until: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default_factory=_uuid)

    @property
    def usable_for_decisions(self) -> bool:
        return self.state in ADMISSIBLE_STATES


@dataclass
class EvidenceDecisionContract:
    """The record a critical decision must produce: which evidence was
    used, which was rejected, which facts, and why it was allowed."""
    decision_type: str
    tenant_id: str
    case_id: str
    actor: str
    evidence_ids: list[str] = field(default_factory=list)
    admissible_ids: list[str] = field(default_factory=list)
    rejected_ids: list[str] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)
    trust_summary: float = 0.0
    hard_blockers: list[str] = field(default_factory=list)
    ai_access_level: str = "none"
    human_verified: bool = False
    final_decision: str = "BLOCKED"     # ALLOWED|BLOCKED|REVIEW
    audit_event_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default_factory=_uuid)

"""Confidence-gated document intake — executable form of docs/finalis-ai/07.

Mock OCR: the scaffold consumes pre-computed OCR fixtures (JSON) instead of
running an engine, but the GATING LOGIC is real — the acceptance rule under
test is: "never silently rely on low-confidence OCR for critical decisions."
Low confidence has exactly three exits: abstain, request re-scan, human review.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .audit import AuditLog
from .models import Case, Document, ExtractedField

Outcome = Literal["accepted", "abstained", "rescan_requested", "human_review"]

THETA_CONF = 0.6          # 05 §6 default
QUALITY_GATE = 0.35       # below this raw scan quality → immediate re-scan ask


@dataclass
class FieldDecision:
    field: ExtractedField
    outcome: Outcome
    reason: str


def ingest_document(case: Case, doc: Document, audit: AuditLog,
                    *, critical_fields: set[str] | None = None
                    ) -> list[FieldDecision]:
    """Apply the confidence gate to every extracted field.

    - quality below QUALITY_GATE → whole doc needs_rescan, nothing accepted.
    - field confidence >= θ_conf → accepted (evidence-linked).
    - below θ_conf and critical (feeds quote/payment/legal) → human review.
    - below θ_conf and non-critical → abstain (stored as unverified, unused).
    """
    critical = critical_fields or set()
    decisions: list[FieldDecision] = []

    if doc.ocr_quality < QUALITY_GATE:
        doc.status = "needs_rescan"
        audit.append(event_type="document.needs_rescan", actor="ai",
                     case_id=case.id,
                     payload={"doc_id": doc.id, "ocr_quality": doc.ocr_quality})
        return [FieldDecision(f, "rescan_requested", "scan_quality_below_gate")
                for f in doc.fields]

    for f in doc.fields:
        conf = f.confidence
        if conf >= THETA_CONF:
            decisions.append(FieldDecision(f, "accepted", f"conf={conf:.2f}"))
        elif f.field_key in critical:
            decisions.append(FieldDecision(f, "human_review",
                                           f"critical+lowconf={conf:.2f}"))
            audit.append(event_type="approval.requested", actor="ai",
                         case_id=case.id,
                         payload={"field": f.field_key, "confidence": conf})
        else:
            decisions.append(FieldDecision(f, "abstained",
                                           f"lowconf={conf:.2f}"))
    doc.status = "analyzed"
    case.documents.append(doc)
    audit.append(event_type="document.analysis_completed", actor="ai",
                 case_id=case.id,
                 payload={"doc_id": doc.id,
                          "accepted": sum(1 for d in decisions
                                          if d.outcome == "accepted"),
                          "gated": sum(1 for d in decisions
                                       if d.outcome != "accepted")})
    return decisions
